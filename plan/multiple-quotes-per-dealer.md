# Multiple Quotes per Dealer — Design & Implementation Guide

## Context

Today the whole stack assumes **one effective quote per dealer**. A single
Pakistani property dealer, though, often has several matching shops. We want to:

1. Let one dealer produce **multiple quotes** — one per property.
2. Tag each quote with a **property identifier** (Shop Number / unit / floor).
3. **Follow up on a specific property** in round 2 (scoped call), not just the dealer.

The one-quote assumption is baked into four places (confirmed by exploration):

- **`log_quote` upsert key = `call_id`** ([backend/src/app/tools.py:103-136](backend/src/app/tools.py#L103-L136)). A second `log_quote` in the same call *merges into* the first row, so two shops quoted in one call collapse to one.
- **Report collapses to one row per dealer** ([backend/src/app/report.py:90-117](backend/src/app/report.py#L90-L117)): picks the dealer's latest quoted call, then `call_quotes[-1]`.
- **Frontend reads `listQuotes(callId)[0]`** — only the first quote ([frontend/lib/useCallCenter.ts:151,172,239](frontend/lib/useCallCenter.ts#L151)).

> **Reconciled with `c48b653`** ("derive call outcome from logged quotes, not transcript prose", pulled after this plan was drafted). Two ripples, both folded in below: report row `outcome` is now `"quote" if quote else (call.get("outcome") or "failed")` ([report.py:109-115](backend/src/app/report.py#L109)), and `useCallCenter` derives `outcome` from the fetched quote in two places. No conflict with the new outcome logic or the added tests — call-level outcome (`has_logged_quote`) stays true when a call has ≥1 quote row, and each report row already derives its own outcome from *its* quote's presence, so per-property rows are correct for free.
- **`get_leverage` output is keyed by dealer name** ([backend/src/app/tools.py:159](backend/src/app/tools.py#L159)) — two shops from one dealer are indistinguishable.

**No property-identifier field exists anywhere** (DB, `QuoteCreate`, tool schemas, TS types). The `quotes` table has no `created_at`; "latest" ordering is positional over call order.

Already multi-quote-safe (no change needed): `crud.list_quotes` (generic filter), `evaluate_red_flags` (per-quote, stateless — [tools.py:54-100](backend/src/app/tools.py#L54-L100)), `POST /specs/{id}/reflag` (per-quote loop — [api.py:159-185](backend/src/app/api.py#L159-L185)), `get_leverage` collection loop (walks all quotes — [tools.py:148-154](backend/src/app/tools.py#L148-L154)).

**Chosen scope:** full stack + demo, with per-property scoped round-2.

### The one design primitive

Add a single nullable free-text column **`quotes.property_ref`** (e.g. `"Shop 4, Ground Floor"`). It becomes:

- the discriminator in `log_quote`'s upsert key: **`(call_id, property_ref)`**;
- the grouping key in the report: **`(dealer_id, property_ref)`**, latest quote per group wins;
- the follow-up target: round-2 call carries `focus_property_ref` into the negotiator agent via a dynamic variable.

No separate `properties` table (YAGNI — a text tag matches "Shop Number etc."). Empty string and `NULL` are normalized to the same "no identifier" bucket, so **single-property dealers behave exactly as today** — full backward compatibility is the correctness anchor for every phase.

---

## Process note

Follow the repo skills: **TDD** (write the failing test first each phase), **caveman** commits, **ponytail** (smallest diff that holds). Frontend: this is a modified Next.js — read `frontend/node_modules/next/dist/docs/` before writing frontend code (per [frontend/AGENTS.md](frontend/AGENTS.md)). Keep the CLAUDE.md K-table + `docs/negotiator-implementation-plan.html` status in sync in the same commit if this lands as new work.

---

## Phase 1 — Data model + `log_quote` upsert key

**Goal:** capture multiple quotes per call, discriminated by `property_ref`; single-property flow unchanged.

### 1a. Migration
New file `backend/supabase/migrations/<timestamp>_quotes_property_ref.sql`:

```sql
alter table quotes add column property_ref text;
```

No unique constraint (partial/None quotes coexist), no new index (demo scale). After applying, **re-seed** — migrations have wiped seed data before (`seed.py`; see K4 note in CLAUDE.md).

### 1b. Model
[api.py:71-87](backend/src/app/api.py#L71) `QuoteCreate`: add `property_ref: Optional[str] = None`. Read paths return raw Supabase dicts, so the new column flows through automatically. `_total_first_year` unaffected.

### 1c. Upsert key
[tools.py:108-116](backend/src/app/tools.py#L108) — change the `existing` lookup from "first quote on the call" to "quote on the call with the **same** `property_ref`", normalizing `""`→`None`:

```python
def _norm(ref):  # "" and None are the same "no identifier" bucket
    return ref or None

existing = next(
    (q for q in crud.list_quotes(call_id=body.call_id)
     if _norm(q.get("property_ref")) == _norm(body.property_ref)),
    None,
)
```

Rest of the merge block ([tools.py:111-116](backend/src/app/tools.py#L111)) is unchanged — it keeps existing non-None fields and sticky `binding`. Because match is on `property_ref`, the merged `property_ref` is stable.

**Ceiling (document with a `ponytail:` comment):** if the agent logs a partial quote with no `property_ref` and *then* reveals the shop number on a later call, the partial (None bucket) orphans and a new row is created. Mitigated by prompt guidance (Phase 3) telling the agent to establish the identifier *first* when there is more than one shop. Acceptable for demo scale.

### 1d. Tests first — [backend/tests/test_tools.py](backend/tests/test_tools.py)
- `log_quote` twice on one call with **different** `property_ref` → **two** rows.
- `log_quote` twice with the **same** `property_ref` → **one** row, merged.
- `log_quote` twice with **no** `property_ref` (both) → **one** row (back-compat; existing behavior).
- Partial-then-complete with the same `property_ref` still merges (earlier fields kept).

---

## Phase 2 — Report: per-property rows

**Goal:** rank per property, not per dealer; recommendation points at a specific property; single-property specs rank identically to today.

### 2a. Grouping ([report.py:89-135](backend/src/app/report.py#L89))
Replace the per-dealer collapse (lines 90-117) with per-`(dealer, property_ref)`. Calls are already sorted ascending ([report.py:80](backend/src/app/report.py#L80)), so a dict overwrite keeps the **latest** quote per property:

```python
for dealer in dealers:
    dealer_calls = [c for c in calls if c["dealer_id"] == dealer["id"]]
    if not dealer_calls:
        continue

    # latest quote per property across all this dealer's calls
    latest_by_prop: dict[str | None, tuple[dict, dict]] = {}
    for c in dealer_calls:
        for q in quotes_by_call.get(c["id"], []):
            latest_by_prop[q.get("property_ref") or None] = (c, q)

    if not latest_by_prop:
        call = dealer_calls[-1]  # never quoted: one declined/failed row, as before
        rows.append(_report_row(dealer, call, None, call_number))
        continue

    for _prop, (call, quote) in latest_by_prop.items():
        rows.append(_report_row(dealer, call, quote, call_number))
```

Extract the row-dict build ([report.py:104-117](backend/src/app/report.py#L104)) into `_report_row(dealer, call, quote, call_number)` — **preserve the current outcome expression verbatim** (`"outcome": "quote" if quote else (call.get("outcome") or "failed")`, updated by `c48b653`) so a per-property row with a quote reads `"quote"` and a no-quote row keeps its stored/failed outcome — and add two fields:

- `"property_ref": (quote or {}).get("property_ref")`
- `"row_id": f'{dealer["id"]}:{(quote or {}).get("property_ref") or ""}'` — stable unique id for the frontend key and for pinpointing the recommendation.

### 2b. Ranking + recommendation
Ranking ([report.py:119-127](backend/src/app/report.py#L119)) is unchanged — it already ranks every row that has a quote. The recommended row is still `ranked[0]`, but it is now a **property**, so return its `row_id`:

- Output ([report.py:130-135](backend/src/app/report.py#L130)): add `"recommended_row_id": recommended["row_id"] if recommended else None`. Keep `recommended_dealer_id` (points at the recommended row's dealer) for back-compat.
- `_recommendation_text` ([report.py:138-193](backend/src/app/report.py#L138)): where it names a dealer, add the property when present. One helper:
  ```python
  def _dealer_label(row):
      ref = row.get("property_ref")
      return f'{row["dealer_name"]} (shop {ref})' if ref else row["dealer_name"]
  ```
  Use it for `top`, `runner_up`, and `cheaper_flagged` names. Prose still deterministic and citation-backed — **do not** introduce any LLM pass (honesty guardrail).

### 2b tests first — [backend/tests/test_report.py](backend/tests/test_report.py)
Reuse the existing `_wire`/`_dealer`/`_call`/`_quote` helpers (add a `property_ref` kwarg to `_quote`).
- One dealer, two shops (two `property_ref`s) → **two** ranked rows, distinct `row_id`, both cited.
- Latest quote per property wins across rounds (round-2 revision of shop A doesn't erase shop B's round-1 quote).
- `recommended_row_id` names the specific cheapest property; `recommended_dealer_id` = that property's dealer.
- **Back-compat:** existing single-quote-per-dealer tests still pass (adjust only for the two new fields).

---

## Phase 3 — Agent tooling + prompts

### 3a. `log_quote` schema — [agent_factory.py:68-89](backend/src/app/agent_factory.py#L68)
Add a **non-required** `property_ref` string param (keep `required = monthly_rent, call_id, dealer_id`):

> `property_ref` — "Identifier of the specific shop/unit this quote is for (e.g. 'Shop 4, Ground Floor'). Pass the same value on every log_quote update for that shop. Omit entirely if the dealer has only one matching property."

### 3b. `get_leverage` output — [tools.py:155-162](backend/src/app/tools.py#L155)
Add `"property": q.get("property_ref")` to each returned row so two shops from one dealer are distinguishable. Exclusion stays by `dealer_id` (a dealer isn't leveraged against their own other shop). Reflect `property` in the `get_leverage` schema description if it enumerates output fields.

### 3c. Negotiator prompt — [config/vertical.json:101](backend/config/vertical.json#L101) (`negotiator_prompt`)
Add two short clauses (keep the rest verbatim):

- **Multiple properties:** "If the dealer has more than one matching shop, ask for a property identifier (shop number, floor, or unit) for each, and pass it as `property_ref` on every `log_quote` for that shop so quotes don't collide. Establish the identifier before logging numbers. Get an itemised quote per shop worth pursuing — don't let the dealer blur several shops into one vague figure."
- **Scoped follow-up:** "If `focus_property` is set ({{focus_property}}), you are following up specifically on that shop — negotiate that one property, reference it by name, and pass its identifier as `property_ref` on every `log_quote`."

Apply the analogous (generic, non-fee-specific) lines to [config/auto_repair_pk.json](backend/config/auto_repair_pk.json)'s `negotiator_prompt` so the second vertical keeps parity.

### 3d. Demo persona (optional but wanted for live demo) — [config/vertical.json:113](backend/config/vertical.json#L113) (`upseller`)
Extend the upseller so it can, when asked, give an itemised quote for **each** of two shops with distinct shop numbers. Mock mode (Phase 5) covers the demo regardless, so this is only needed for a live agent-to-agent demo.

**Re-run the agent factory** after 3a/3c/3d so ElevenLabs tool + prompt configs update (`make_agents.py`; needs live keys — a human step).

---

## Phase 4 — Scoped round-2 (`focus_property`)

**Goal:** a follow-up call can target one property; the negotiator agent receives the identifier.

### 4a. Request + dynamic variable — [api.py:64-68](backend/src/app/api.py#L64), [api.py:256-264](backend/src/app/api.py#L256)
- `CallStartRequest`: add `focus_property_ref: Optional[str] = None`.
- `_dynamic_variables(spec, call_id, dealer_id, focus_property_ref="")`: always include `"focus_property": focus_property_ref or ""`. **Always present** (empty default) so the prompt's `{{focus_property}}` template always resolves — a missing dynamic variable can break the ElevenLabs conversation.
- `start_call` ([api.py:292](backend/src/app/api.py#L292)): pass `body.focus_property_ref` into `_dynamic_variables`. Both bridge and roleplay already forward `dynamic_vars` to the negotiator ([bridge.py:281](backend/src/app/bridge.py#L281), roleplay response [api.py:294-299](backend/src/app/api.py#L294)) — no bridge changes.

**Ceiling (`ponytail:` comment):** only the property *name* is injected, not its prior figures — the agent re-confirms the number on the call and `get_leverage` supplies competing bids. Add prior-quote injection only if follow-ups feel context-blind in testing.

### 4a tests first — [backend/tests/test_api.py](backend/tests/test_api.py)
- `start_call` (roleplay) with `focus_property_ref="Shop 4"` → `dynamic_variables["focus_property"] == "Shop 4"`.
- `start_call` with no `focus_property_ref` → `dynamic_variables["focus_property"] == ""` (present, empty). Existing start-call tests still pass.

---

## Phase 5 — Frontend (full stack + demo)

Read `frontend/node_modules/next/dist/docs/` first. TS types drive most of this.

### 5a. Types — [frontend/lib/types.ts](frontend/lib/types.ts)
- `Quote` ([types.ts:133](frontend/lib/types.ts#L133)): add `property_ref?: string | null`.
- `ReportRow` ([types.ts:172](frontend/lib/types.ts#L172)): add `property_ref?: string | null` and `row_id: string`.
- `Report` ([types.ts:187](frontend/lib/types.ts#L187)): add `recommended_row_id: string | null`.
- `startCall` request type / `CallStartResponse` unchanged except the new optional request field.

### 5b. Call state holds an array — [frontend/lib/useCallCenter.ts](frontend/lib/useCallCenter.ts)
- `DealerCallState`: replace `quote?: Quote | null` with `quotes: Quote[]` (default `[]`).
- Read full arrays, not `[0]`: [line 151](frontend/lib/useCallCenter.ts#L151) (live poll), [172](frontend/lib/useCallCenter.ts#L172) (completed), [239](frontend/lib/useCallCenter.ts#L239) (hydrate) → `const qs = await listQuotes(callId); patch(dealerId, { quotes: qs })`. Keep the "don't clobber on fetch error" guard (only patch when the fetch succeeded).
- **Outcome derivation (added by `c48b653`) now reads the single `quote`** in two spots — convert both to `qs.length > 0`: the completed patch (`outcome: quote ? "quote" : call.outcome ?? "callback"`, ~[line 180](frontend/lib/useCallCenter.ts#L180)) and the hydrate patch (`quote ? "quote" : c.outcome ?? "callback"`, ~[line 250](frontend/lib/useCallCenter.ts#L250)) → `qs.length > 0 ? "quote" : …`.
- `hangUp` mock branch ([line 378-383](frontend/lib/useCallCenter.ts#L378)) and mock completion ([line 116-121](frontend/lib/useCallCenter.ts#L116), [327-334](frontend/lib/useCallCenter.ts#L327)): set `quotes` (array) instead of `quote`.
- New `followUp(dealerId, propertyRef)`: like `call`, but at `nextRound(dealerId)` and passing `focusPropertyRef`. Extend `runRealCall`/`startRoleplay`/`runMockCall` to accept an optional `focusPropertyRef` and thread it into `startCall`.

### 5c. `startCall` API — [frontend/lib/api.ts](frontend/lib/api.ts)
Add optional `focusPropertyRef?: string` → include as `focus_property_ref` in the POST body when set.

### 5d. Quote display — [frontend/components/calls/QuoteChip.tsx:18](frontend/components/calls/QuoteChip.tsx#L18)
Header text: `quote.property_ref ?? "Logged quote"`.

### 5e. Render multiple quotes
- **Calls page panel** ([frontend/app/calls/[spec_id]/page.tsx:146-161](frontend/app/calls/[spec_id]/page.tsx#L146)): map `stateFor(selectedDealer.id).quotes` to a list of `<QuoteChip>` (empty-state when none). Add a per-property **"Follow up"** button when the call is `done` and `round < MAX_ROUNDS`, calling `followUp(dealerId, quote.property_ref ?? "")`.
- **DealerCard** ([frontend/components/calls/DealerCard.tsx:30,88](frontend/components/calls/DealerCard.tsx#L30)): the done-summary reads a single `quote`. Change to summarize `quotes` — e.g. "N quotes · cheapest PKR …" (min `total_first_year`), or just count when >1. Keep the flagged badge if **any** quote is flagged.
- **CallStatusPanel** ([frontend/components/calls/CallStatusPanel.tsx:78](frontend/components/calls/CallStatusPanel.tsx#L78)): its `quote` is only used to gate the outcome label — switch to `quotes.length > 0`.

### 5f. Report UI
- **RankedTable** ([frontend/components/report/RankedTable.tsx:19,16](frontend/components/report/RankedTable.tsx#L19)): `key={row.row_id}`; `recommended = row.row_id === recommendedRowId` (thread `recommended_row_id` from the page instead of `recommendedDealerId`). Show `row.property_ref` as a small label under `dealer_name` when present.
- **RecommendationBlock**: locate the recommended row by `recommended_row_id` (not `recommended_dealer_id`) so a dealer with two shops highlights the right one. Use the property in the heading when present.
- Report page ([frontend/app/report/[spec_id]/](frontend/app/report/[spec_id]/)): pass `recommended_row_id` down.

### 5g. Mock demo data — [frontend/lib/mocks.ts](frontend/lib/mocks.ts)
Make one persona (e.g. `upseller`) return **two** quotes with distinct `property_ref` ("Shop 2", "Shop 7") so multi-quote render, per-property follow-up, and per-property ranking are all demoable in mock mode. `MOCK_QUOTES` value for that persona becomes a `Quote[]`; `runMockCall`/`seedMockCompleted` set `quotes` accordingly; add both rows to `MOCK_REPORT` with `row_id`/`property_ref` and set `recommended_row_id`.

---

## Acceptance criteria

**Backend**
- [ ] `log_quote` on one call with two distinct `property_ref` values creates **two** quote rows; same `property_ref` (or both omitted) keeps **one** merged row.
- [ ] Migration adds `quotes.property_ref` (nullable); existing rows read back with `property_ref = null`.
- [ ] A dealer with two shops appears as **two ranked rows** in `GET /report`, each with distinct `row_id`, correct per-property `total_first_year`, and a resolvable `[call N, line M]` citation.
- [ ] `recommended_row_id` identifies the single cheapest clean property; a flagged property still never ranks #1 and is never dropped.
- [ ] `get_leverage` output rows include `property`, distinguishing two shops of one dealer.
- [ ] `start_call` with `focus_property_ref` puts `focus_property` in the negotiator's `dynamic_variables`; without it, `focus_property` is present and empty.
- [ ] `POST /specs/{id}/reflag` flags/unflags each property's quote independently (already per-quote — add a 2-property regression test).
- [ ] **Back-compat:** every pre-existing backend test passes (adjusted only for the two additive report fields). `cd backend && uv run pytest` — no new failures beyond the 4 known `socksio` env failures.

**Frontend (mock mode)**
- [ ] A dealer that logs two quotes shows **two** `QuoteChip`s, each headed by its `property_ref`.
- [ ] Each property has a **"Follow up"** button that starts a scoped round-2 call (round increments, `focus_property_ref` sent).
- [ ] Report lists per-property rows with no React key collision; the recommended property is highlighted (not both rows of that dealer).
- [ ] Citation deep-link from a per-property row lands on the correct call/line.
- [ ] Single-property dealers look and behave exactly as before.

---

## Verification

**Backend (authoritative):**
```
cd backend && uv run pytest
```
All new phase tests green; only the 4 known `socksio` `POST /webhooks/post-call` failures remain. Apply the migration to the live Supabase project and re-run `seed.py`. For a live agent check, re-run `make_agents.py` (needs keys) so the updated `log_quote` schema + prompts deploy, then run one bridge/roleplay call against the demo persona and confirm two `property_ref`-tagged quote rows land.

**Frontend (mock mode, no test framework in repo):**
```
cd frontend && NEXT_PUBLIC_USE_MOCKS=true npm run dev   # then typecheck/build
```
Click through: call the multi-shop persona → see two labeled quote chips → "Follow up" on one shop (round 2, scoped) → open the report → two per-property rows, correct recommendation highlight, citation round-trip. Confirm a single-property persona is unchanged. Run the production build/typecheck to catch type breakage from the `quote`→`quotes` rename.

**Files touched (map):** migration + `tools.py`, `api.py`, `report.py`, `agent_factory.py`, `config/vertical.json`, `config/auto_repair_pk.json`; tests `test_tools.py`, `test_report.py`, `test_api.py`; frontend `types.ts`, `useCallCenter.ts`, `api.ts`, `mocks.ts`, `QuoteChip.tsx`, `DealerCard.tsx`, `CallStatusPanel.tsx`, `RankedTable.tsx`, `RecommendationBlock`, calls + report pages.
