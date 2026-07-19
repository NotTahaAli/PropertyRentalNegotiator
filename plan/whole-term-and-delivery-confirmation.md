# Whole-Term Cost + Delivery-Date Confirmation — Design Plan

## Context

Today the entire app compares dealers on a **single key: `total_first_year`**
(`api._total_first_year`). Two client-relevant facts are captured but never used
to compare or recommend:

1. The **annual growth rate** (`annual_increment_pct` in the shop-rental
   vertical) — logged on every quote, spoken by personas, but **never
   compounded**. A dealer with a cheap first year and a steep yearly increment
   can outrank a dealer who's flat — over a multi-year term the ranking is
   backwards.
2. The client's **delivery/occupancy deadline** (`move_in` in shop rental) — a
   required spec field that reaches the negotiator prompt, but **no dealer
   persona is told it, no quote field records the dealer's confirmed availability,
   and the report never checks it.** A dealer who can't deliver in time can still
   be recommended #1 on price alone.

**Goal.** Make quotes and the ranked report reason over the **whole engagement
term** (primary) as well as the first year (secondary), and make the client's
deadline a hard part of the negotiation: the counterparty must be told it, must
confirm a delivery date, and one who can't meet it (or never confirmed it) is
gated below those who can.

**Stay vertical-agnostic.** The thing being negotiated (shop rent, car repair, …)
and its term/deadline are **config, not code**. This feature must not hardcode
`rent` / `lease` / `move_in`. The field *names* live in new `vertical.json` keys;
only the generic cost mechanics live in code. Proven swappable by
`auto_repair_pk.json` (no term, deadline = `needed_by`).

**Two mechanics decisions (locked):**
- **Deadline gate:** counterparties who miss or don't confirm the client's
  deadline rank *below* all who meet it; among meeters, cheapest whole-term cost
  wins. (Same shape as the existing "flagged never #1" rule.)
- **Term math:** the primary recurring amount compounds by the growth rate each
  period; secondary recurring amounts stay flat; one-time fees counted once.

## Non-goals

- No LLM-written recommendation prose — the template stays deterministic (locked
  honesty guardrail). Every figure comes from `quotes` rows.
- No fully config-driven fee-semantics engine. The existing per-fee arithmetic in
  `_total_first_year` (which fees are monthly vs one-time, advance = months×rent)
  is the current vertical's and **stays as-is** — this feature only generalizes
  the *term horizon*, *growth rate*, and *deadline* field names. A generic
  periodic/one-time fee model is deferred until a vertical actually needs
  different mechanics (YAGNI).
- No spec-edit path exists, so a stored term total can't go stale — store it
  rather than re-derive on every read.
- No new red-flag rule for late delivery — the deadline is a ranking gate +
  report warning, not the fraud-oriented red-flag engine.

---

## Config generalization (`vertical.json` + `VerticalConfig`)

Three new **optional** keys on `VerticalConfig` (`vertical.py`), all default
`None` so verticals that omit them degrade cleanly:

| key | shop_rental | auto_repair | meaning |
| --- | --- | --- | --- |
| `duration_field` | `"lease_years"` | *(unset)* | spec field giving the number of periods to sum cost over |
| `increment_field` | `"annual_increment_pct"` | *(unset)* | the fee that is an annual % growth on the primary recurring amount |
| `deadline_field` | `"move_in"` | `"needed_by"` | spec field the counterparty must confirm a delivery date against |

No literal `"lease_years"` / `"move_in"` / `"annual_increment_pct"` strings in
`report.py` / `api.py` / `tools.py` — all read through these config keys.

## Whole-term cost

New generic helper `_total_over_term(body, periods, growth_pct)` in `api.py`,
next to `_total_first_year`:

```python
def _total_over_term(body: QuoteCreate, periods: float | None, growth_pct: float | None) -> float:
    n = max(1, round(periods or 1))
    g = (growth_pct or 0) / 100
    rent = body.monthly_rent
    maint = body.maintenance or 0
    other = sum(body.other_fees.values()) if body.other_fees else 0
    primary_recurring = sum(12 * rent * (1 + g) ** y for y in range(n))  # compounds
    return (
        primary_recurring
        + n * 12 * maint                 # secondary recurring: flat
        + (body.advance_months or 0) * rent   # one-time
        + (body.commission or 0)         # one-time
        + other                          # one-time
    )
```

- `periods` = `spec_json.get(config.duration_field)` when set, else `None` → `n=1`.
- `growth_pct` = the quote fee named by `config.increment_field`, read via
  `body.model_dump().get(config.increment_field)` (None when unset).
- For a vertical with no `duration_field` / `increment_field` (e.g. auto repair)
  → `n=1, g=0` → term total ≈ first-year total, so the new primary key degrades
  cleanly and stays swappable.
- Stored on the quote row as **`total_term`** (new nullable column) alongside
  `total_first_year`. Ranking reads `total_term`, falling back to
  `total_first_year` when null.

## The deadline gate

- New quote field **`available_from`** (nullable ISO date, `YYYY-MM-DD`) — the
  date the counterparty confirms delivery. Generic across verticals (shop
  handover / repair completion). This is what "confirmed it in his quote" means.
- `meets_deadline(row, client_deadline)` is True iff the client has a deadline
  (`spec_json.get(config.deadline_field)`), the quote has `available_from`, and
  `available_from <= client_deadline`. A **null `available_from` counts as a
  miss** ("did not confirm") — this enforces the "ensure the dealer confirmed it"
  requirement.
- When `config.deadline_field` is unset or the spec has no such date, the gate is
  inert — nobody is demoted.

## New ranking sort key (`report.build_report`)

```python
key = (
    bool(quote.get("flagged")),        # locked: flagged never #1
    not meets_deadline,                # gate: misses/unconfirmed below meeters
    term_total,                        # primary cost key (was total_first_year)
    quote["total_first_year"],         # tiebreak / secondary
)
```

Order: clean+meets (by term cost) → clean+misses → flagged+meets →
flagged+misses. Keeps "flagged never #1" as the outermost gate, applies the
deadline gate among clean quotes, then ranks by whole-term cost. If no clean
quote meets the deadline, the best clean-but-late quote is still recommended with
a loud warning.

## Recommendation text (`report._recommendation_text`, still a template)

- Lead with term cost: `"{dealer} offers the best verified deal at {term_total}
  over the full {n}-year term (first year {first_year}) {citation}."` (noun
  "term" is generic; no vertical wording baked in).
- Deadline clause on the top pick: `"confirmed delivery by your target date of
  {deadline}."` or `"did NOT confirm delivery by your target date of {deadline} —
  verify before committing."`
- Runner-up saving computed on `total_term`, not first-year.
- Cheaper-but-flagged callouts compare `total_term`.
- Non-binding note unchanged.

## Counterparty awareness (personas can confirm/miss the date)

- `_dealer_dynamic_variables` (`api.py`) gains two vars, read via config:
  - `deadline` — the client's target date (`spec_json.get(config.deadline_field)`).
  - `dealer_available_from` — a **computed** ISO date the persona delivers on (no
    LLM date arithmetic). Default = the client `deadline`; the **upseller**
    persona is offset ~6 weeks later so the gate is demonstrable live. Reused
    verbatim from the dealer's own prior quote on follow-up rounds (sticky, like
    `asking_rent`).
- Persona prompts (`vertical.json`) get one availability line each referencing
  `{{dealer_available_from}}` / the deadline var.

## Negotiator behavior (`vertical.json` `negotiator_prompt` — per-vertical text)

Add two instructions (in the shop-rental config's own prompt text):
1. State the client's target date, ask the dealer to confirm delivery by then,
   and log the confirmed date as `available_from` on `log_quote`.
2. Optimize for **lowest whole-term cost over `{{lease_years}}` years**, not just
   the first year — push the growth rate down explicitly, since it compounds.

---

## Files to change

**Backend — cost + gate (the core):**
- `backend/src/app/vertical.py` — add optional `duration_field`,
  `increment_field`, `deadline_field` to `VerticalConfig`.
- `backend/src/app/api.py` — add `_total_over_term`; add `available_from` to
  `QuoteCreate`; compute+store `total_term` in `POST /quotes` (load spec via call
  for the duration/growth values); add `deadline` + `dealer_available_from` to
  `_dealer_dynamic_variables` (incl. sticky reuse from prior quote), all via
  config keys.
- `backend/src/app/tools.py` — `log_quote`: compute+store `total_term` (spec
  already loaded), pass `available_from` through; `get_leverage`: sort by
  `total_term` (fallback `total_first_year`), add it to payload.
- `backend/src/app/report.py` — load spec; per-row `total_term`, `available_from`,
  `meets_deadline` (all via config keys); new sort key; reworked
  `_recommendation_text`; add fields to `_report_row` output.
- `backend/src/app/agent_factory.py` — add `available_from` param to the
  `log_quote` tool schema (string, "YYYY-MM-DD; the date the dealer confirms
  delivery/handover"). Prompt text lives in `vertical.json`.
- **New migration** `backend/supabase/migrations/<ts>_quotes_term_and_availability.sql`:
  `alter table quotes add column total_term numeric;` +
  `add column available_from date;` (both nullable, additive).

**Config:**
- `backend/config/vertical.json` — `duration_field: "lease_years"`,
  `increment_field: "annual_increment_pct"`, `deadline_field: "move_in"`;
  negotiator + 4 persona prompts updated per above.
- `backend/config/auto_repair_pk.json` — `deadline_field: "needed_by"` (no
  `duration_field`/`increment_field` → term cost = first-year cost). Must still
  validate; persona/negotiator prompt edits optional.
- **Re-run `uv run python -m app.make_agents`** — required for the prompt + tool
  schema changes to reach ElevenLabs (live only; tests don't need it). Note in
  `TODO.md`.

**Frontend (show term cost primary, first-year secondary, delivery status):**
- `frontend/lib/types.ts` — `Quote` gains `total_term`, `available_from`; report
  row gains `total_term`, `meets_deadline`, `available_from`.
- `frontend/components/report/RankedTable.tsx` — term total primary column,
  first-year secondary; delivery-date badge (met / late / unconfirmed).
- `frontend/app/report/[spec_id]/page.tsx` — header "ranked by total term cost".
- `frontend/components/calls/QuoteChip.tsx`, `DealerCard.tsx` — surface term total
  (flows in via stored `total_term`).
- `frontend/lib/mocks.ts` — mock quotes get `total_term`, `available_from`
  (include one late/unconfirmed dealer so mock mode demos the gate).

**Repo bookkeeping (same commit as the work — locked repo rule):**
- Update `CLAUDE.md` status table (K4/K10 rows + schema block), `TODO.md`
  (make_agents re-run, live verify), and the plan HTML status tile.

---

## Acceptance criteria

1. **Term-primary ranking.** Given two clean quotes where first-year order and
   whole-term order disagree (different growth rate), the report ranks by
   whole-term cost.
2. **Term math correct.** For `monthly_rent=200000, maintenance=5000, advance=2,
   commission=100000, annual_increment_pct=10, lease_years=3`, `total_term` =
   200k×12×(1+1.1+1.21) + 5k×12×3 + 400k + 100k = `7,944,000 + 180,000 + 400,000 +
   100,000 = 8,624,000`. First year stays `2,960,000`.
3. **Deadline gate.** Cheaper-term quote whose `available_from` is after the
   client's deadline (or null) ranks below every on-time dealer.
4. **Unconfirmed = miss.** A quote with no `available_from` is treated as not
   meeting the deadline and the recommendation warns "did not confirm".
5. **Flagged still never #1**, even when it's the only quote meeting the deadline.
6. **Gate + term inert without config.** A vertical with no `deadline_field`
   ranks without demotion; with no `duration_field` term cost = first-year cost.
7. **Counterparty is told the date.** `_dealer_dynamic_variables` returns
   `deadline` and `dealer_available_from`; `available_from` is sticky across
   rounds.
8. **Recommendation prose** states term total, first-year figure, and deadline
   confirmation status of the top pick, each with a `[call N, line M]` citation —
   no figure absent from a `quotes` row.
9. **Swappable.** `auto_repair_pk.json` validates against `VerticalConfig` and
   drives the agent factory unchanged.
10. **All existing backend tests pass** after updating first-year-primacy
    assertions to term-primary ordering.

## Test plan (TDD — test first, watch it fail, then implement)

`backend/tests/test_report.py`
- `test_ranks_by_total_term_not_first_year` (AC1)
- `test_meets_deadline_ranks_above_cheaper_miss` (AC3)
- `test_unconfirmed_deadline_treated_as_miss_and_warned` (AC4)
- `test_flagged_never_first_even_if_only_one_meets_deadline` (AC5)
- `test_gate_and_term_inert_when_config_unset` (AC6)
- `test_recommendation_states_term_first_year_and_deadline` (AC8)
- update existing first-year-primacy + multi-property + `only_figures_that_exist`
  assertions to term-primary numbers.

`backend/tests/test_tools.py`
- `test_log_quote_computes_total_term` (AC2, exact 8,624,000)
- `test_log_quote_stores_available_from`
- `test_get_leverage_sorts_by_total_term`
- keep the existing `total_first_year == 2960000` assertions unchanged.

`backend/tests/test_api.py`
- `test_dealer_vars_include_deadline_and_available_from` (AC7)
- `test_available_from_sticky_across_rounds` (AC7)

`backend/tests/test_agent_factory.py`
- `test_log_quote_schema_has_available_from`
- `test_negotiator_prompt_mentions_deadline_and_term` (loose contains)

`backend/tests/test_vertical.py`
- `test_term_config_keys_optional_default_none`
- keep `test_second_vertical_config_swaps_cleanly` green (add `deadline_field` to
  `auto_repair_pk.json`).

Migration is additive/nullable — re-seed covers it, no data-migration test.

## Verification (end-to-end)

1. `cd backend && uv run pytest` — all green (currently 265; expect +~10).
2. **Mock mode, browser** (no keys): intake a spec with a deadline + duration →
   run calls → open the report. Confirm: ranked by term total (primary column),
   first year shown secondary, a late/unconfirmed dealer sits below on-time
   dealers with a delivery badge, and the recommendation prose names the term
   total + delivery status.
3. **Live (optional, needs keys):** re-run `uv run python -m app.make_agents`,
   run one bridge call. Confirm the negotiator states the target date, the persona
   confirms delivery, and `available_from` + `total_term` land on the quote row.

## Rollout order

1. Config keys + migration + `QuoteCreate.available_from` + `_total_over_term` +
   write-path (`log_quote`, `POST /quotes`) — `test_tools` first (TDD).
2. `report.py` sort key + `_recommendation_text` + `_report_row` — `test_report`
   first.
3. Dealer vars (`deadline`, `dealer_available_from`, sticky) — `test_api`.
4. `agent_factory` tool schema + `vertical.json` prompts + `auto_repair_pk.json`
   — `test_agent_factory` / `test_vertical`.
5. Frontend + mocks.
6. Repo bookkeeping (CLAUDE.md / TODO.md / plan HTML), `make_agents` re-run.
