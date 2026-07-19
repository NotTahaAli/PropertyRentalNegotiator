# Full-leverage get_leverage + client call-history view — design

Date: 2026-07-19. Scope: two related trust/visibility improvements —
(1) client can see the transcript of every call to every dealer, not just the
latest round; (2) the Negotiator agent sees its complete current leverage
picture (all logged quotes, not top-3-competitors-only) and knows which quote
is its own.

## Part 1 — `get_leverage` tool: full leverage + self-awareness

**Decision: widen the tool's return shape and raise the cap, without
touching the honesty guardrail** (only real logged `quotes` rows are ever
returned — this changes *how much* of that real data reaches the agent, not
its source).

Current behavior (`backend/src/app/tools.py` `get_leverage`,
`backend/src/app/agent_factory.py` schema): top-3 cheapest non-flagged
quotes from *other* dealers only; calling dealer's own quotes and any
flagged quotes are dropped entirely. Own-quote awareness today only reaches
the agent as prose in `prior_call_summary` (last round only).

New shape — single flat list, each item gains two tags:

```json
{
  "dealer": "...", "property": "...", "monthly_rent": 0, "advance_months": 0,
  "commission": 0, "maintenance": 0, "total_first_year": 0,
  "is_current_dealer": true,
  "flagged": false
}
```

Selection rule:
- All of the calling dealer's own quotes (`is_current_dealer: true`) —
  always included, not counted against any cap. Usually one row, more if the
  dealer has quoted several properties.
- Up to 5 competitor quotes (`is_current_dealer: false`), sorted ascending
  by `total_first_year`. Previously-excluded flagged quotes are now included
  in this pool and sort (tagged `flagged: true`) rather than dropped — the
  agent is told to weigh a flagged quote as less certain, not to ignore it.

Empty spec (no quotes anywhere) still returns `[]`, unchanged.

**Prompt change** (`backend/config/vertical.json` `negotiator_prompt`, via
`agent_factory.py`): strengthen "may use get_leverage... cite them" to
proactive language — call `get_leverage` during the negotiation (not only
once), actively cite the cheapest `is_current_dealer: false` quote to press
for a discount, and use the `is_current_dealer: true` entry to recognize its
own prior number so it never mistakes its own quote for a rival's. Honesty
guardrail sentence ("no knowledge of any competing offer beyond what
get_leverage actually returns... fabricating leverage is not allowed under
any circumstance") stays verbatim.

**Testing**: extend `backend/tests/test_tools.py` for the new shape —
own-dealer quote always present untagged by the cap, flagged quote included
and tagged, cap holds at 5 competitors when more than 5 exist, empty case
unchanged. `make_agents` re-run required for the prompt change to go live
(already a standing TODO pattern in this repo — add this to `TODO.md`).

## Part 2 — Client call-history view (all rounds, all dealers)

**Decision: frontend-only change; no new backend endpoint.**
`GET /calls?spec_id=` (`backend/src/app/api.py`) already returns every call
row for the spec, including `transcript_json`, for every dealer and every
round. The gap is purely in frontend state: `frontend/lib/useCallCenter.ts`
collapses calls into `latestByDealer` (one call per dealer, overwriting
older rounds), so older transcripts are fetched then discarded.

Change: keep an array of calls per dealer (ascending by round) instead of a
single latest call. `frontend/components/calls/DealerCard.tsx` gains a
collapsible "Call history" list — round #, outcome badge, timestamp per
entry; expanding a row renders that round's transcript via the existing
`TranscriptStream` component (reused unmodified, just pointed at a specific
past call's `transcript_json` instead of only the live/latest one).

**Side-effect fix, same root cause**: `frontend/app/report/[spec_id]`'s
`[call N, line M]` citation links (`CitationLink.tsx` → calls page
`?call=N&line=M`) currently only resolve if the cited round is still the
latest for that dealer — older-round citations silently fail to scroll/
highlight. Since all rounds are now retained in state, the query-param
handler in `frontend/app/calls/[spec_id]/page.tsx` is updated to search
across all of that dealer's rounds for the matching call, not just the
latest. No separate spec item — same data structure fix.

**Testing**: UI-only change. Verified by hand in browser per this project's
UI-change rule (call two rounds against one dealer, confirm both transcripts
browsable; click an older-round citation link from the report page and
confirm it resolves). No new frontend test framework introduced.

## Out of scope

- No change to `check_redflag` / `get_benchmark` / `log_quote` / red-flag
  rules themselves.
- No change to who can see what — existing spec-ownership JWT gating on
  `GET /calls` already covers this; the client only ever sees their own
  spec's calls.
- No transcript editing/redaction UI.
