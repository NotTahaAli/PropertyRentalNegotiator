# TODO

Cross-component integration gaps that are blocked right now on secrets, live
external calls, or an unbuilt K-component — not on missing understanding of
the code. Update this file in the same commit as whatever resolves or adds
an item; delete resolved items instead of checking them off.

## Blocked: frontend K8 → backend wiring

- **Role-play widget embed in DealerCard** — the "Answer as dealer" toggle
  on `/calls/[spec_id]` renders a placeholder only. Backend roleplay mode
  (`POST /calls/start` with `mode: "roleplay"`) already returns
  `negotiator_agent_id` + `dynamic_variables`; the frontend never consumes
  them. Wire the same `@elevenlabs/react` `ConversationProvider` +
  `useConversation` pattern K8's `VoiceIntake.tsx` proved, passing the
  dynamic variables at session start. This is the K5-fallback demo path —
  the demo must never depend on the bridge working, so this gap still
  matters even now that the bridge persona-reply bug is fixed.

- **Post-call webhook: live delivery unverified** — backend endpoint
  `POST /webhooks/post-call` is built and HMAC-verified;
  `ELEVENLABS_WEBHOOK_SECRET` is now set locally (presence-checked
  2026-07-19) and the dashboard webhook exists. Still to confirm: the same
  secret is set on Render, and one real agent call actually lands a signed
  event at `https://negotiator-backend.onrender.com/webhooks/post-call`
  (transcript + outcome written to the `calls` row).

## Resolved: make_agents re-run (dealer-first flip + negotiator end_call)

- **Done 2026-07-19** — `uv run python -m app.make_agents` re-run live:
  negotiator now carries the first_message override permission (dealer
  answers first) and the `end_call` system tool + tightened closing prompt
  (fixes the infinite goodbye loop after the 3:00 cap was removed). Live
  bridge call re-check pending to confirm the negotiator actually hangs up.

## Open: manual click-throughs

- **Report page real-mode check** — `GET /report/{spec_id}` now exists and the
  page calls it for real, but it has only ever rendered `MOCK_REPORT` in a
  browser. Needs one spec with completed calls: confirm ranking order matches
  `total_first_year`, a flagged quote sorts last rather than #1, "Re-check
  flags" round-trips, and a citation click lands on the right dealer's
  transcript line. **Watch the citation mapping specifically:** `call_number`
  is now assigned by the backend (spec's calls ordered by `started_at`) while
  the mock still numbers by `MOCK_DEALERS` index — they agree by construction
  in the demo but are different mechanisms, so a citation landing on the wrong
  dealer in real mode points here first.


- **Live-audio player + stereo recording browser check** — `LiveAudio.tsx`
  (leg-tagged WS stream, Web Audio, panned L/R, per-leg mute) and the new
  time-aligned stereo recording are unit-tested + build-clean but not yet
  heard in a browser. Needs one real bridge call on `/calls/[spec_id]`:
  confirm both voices audible live while the call runs, then replay the
  recording and confirm negotiator left / dealer right with no overlap
  (live playback now serializes both legs on one shared cursor — same
  no-overlap guarantee as the recording), that the dealer speaks first,
  and that transcript lines appear live during the call (streamed on the
  same WS, replaced by the final numbered transcript at completion).
  If the browser blocks autoplay, clicking either mute button unlocks it.
  Same call also verifies the new half-duplex turn-taking gate
  (`bridge.TurnGate` + `turn_sender`): agents should no longer talk over
  each other live — one voice at a time, short pause when a held leg takes
  the floor. Also click "End call" mid-call once: the bridge should finalize
  early (recording + transcript + outcome land on the row). Unit-tested only
  so far.

- **Live voice intake click-through** — voice path fully wired
  (`set_spec_field` client tool + `end_call` live on the Estimator,
  `VoiceIntake.tsx` on `@elevenlabs/react`), but nobody has run a real
  mic conversation through it yet. Needs a human: start interview, answer,
  watch fields fill, confirm, verify auto-hangup. Spends ~2 min of credits.

## Open: partial quotes can understate a bid

- **`get_leverage` and the report can both be misled by a partial quote row.**
  Since `log_quote` upserts, a row exists the moment the first number lands. Its
  `total_first_year` is computed from whatever fields have arrived, so a
  rent-only row is strictly *cheaper* than the same dealer's completed quote
  (40,000 rent: partial 480,000 vs complete 636,000). `get_leverage` sorts
  ascending and returns the lowest 3, so a half-finished quote can be served to
  another dealer as the best competing bid, and can rank #1 in the report.
  Not a fabrication — the number is real — but it is understated, and the
  negotiator would be citing it as if it were a full offer. Fix would be to skip
  quotes missing the fee fields in `get_leverage`/report ranking. Deliberately
  not done yet: it lands in `tools.py`, which is being actively edited.

## Resolved

- **Real quotes reported as "no numbers committed"** — `derive_outcome`
  classified a call by regex-scanning the dealer's transcript lines for a
  complete number token. A real haggle is piecemeal ("forty" / "two months" /
  "one month commission"), so no single line matched and calls that produced a
  full itemised quote came back as `callback`, showing "Dealer asked for a
  callback — no numbers committed" in the UI. Outcome now reads the **quotes
  table** as ground truth (`bridge.has_logged_quote`) and only falls back to the
  text scan when no quote was logged. Applied at all three finalize points: the
  bridge, the post-call webhook (the roleplay path), and the orphaned-call
  recovery in `POST /calls/{id}/end`. The report and `useCallCenter` also prefer
  a real quote row over a stored outcome, so rows written before this fix
  display correctly too. Fallback scan additionally learned the "40k" shorthand,
  and decline now beats an incidental number.

- **K10 report generator** — `GET /report/{spec_id}` built
  (`backend/src/app/report.py`, `backend/tests/test_report.py`, 20 tests). The
  report UI had been shipping against `MOCK_REPORT` with nothing behind it.
  Flagged quotes sort last and can never rank #1 but are never hidden;
  `recommendation_text` is templated rather than model-written, on the same
  honesty-guardrail reasoning as `get_leverage`.
- **Red-flag false positive** — `no_written_quote` fired on `binding=None`
  because the rule checked `not binding` and `QuoteCreate.binding` defaulted to
  `False`. Every quote logged without the field came back flagged, so
  above-market dealers wore the same badge as suspiciously-cheap ones, which
  inverts what the badge means to a user. `binding` is now tri-state and the
  rule fires only on explicit `False`. Safe because the `log_quote` tool schema
  already lists `binding` as required, so the agent path always sets it. Three
  existing tests encoded the old behaviour and were rewritten, not deleted.
- **CORS / boot fragility** — `main.py` read `os.environ["CORS_ORIGINS"]`, so a
  missing env var was an import-time `KeyError` that took the whole service down
  rather than serving with a default. Now defaults to localhost and adds an
  `allow_origin_regex` for `*.vercel.app`, since preview deploys get a new
  subdomain per push and can't be enumerated in an allowlist. `render.yaml` was
  also missing `CORS_ORIGINS`, `OPENAI_API_KEY`, `TAVILY_API_KEY` and
  `ELEVENLABS_WEBHOOK_SECRET` entirely — all four now declared there, so they
  stop being things somebody has to remember in the Render dashboard.
- **K11 reflag had no UI caller** — "Re-check flags" button now on the report
  page (`lib/api.ts` `reflagSpec` + `app/report/[spec_id]/page.tsx`).

- K7 live verification: `TAVILY_API_KEY` now set locally + on Render,
  live-verified 2026-07-19 (probe user `k7-live-verify@gmail.com`, test
  specs cleaned up after). Dealer discovery works both local and deployed:
  `POST /specs` ("Gulberg Lahore") inserted 4 real tavily dealer rows
  (`persona="human"`), and the K11 hardening held live — no duplicates, no
  blanks, no portal/directory junk. Benchmark extraction returns None on
  this query: Tavily snippets are Zameen listing-index pages (counts, no
  per-sqft figures), so the never-guess extractor correctly nulls out and
  `get_benchmark` serves the config fallback (`source: "fallback"`) — the
  designed fail-soft path, not a bug; `source: "cached"` only happens when
  search snippets actually state a range. Also fixed `benchmark_query` typo
  in `vertical.json` ("rentn" -> "rent"); didn't change the outcome.
- `make_agents` re-run for K4/K7 prompt+schema changes (`binding` required
  in `log_quote` schema, written-quote + friction-handling prompt updates):
  user re-ran `uv run python -m app.make_agents` with live keys 2026-07-19;
  deployed agents/tools now carry current config.
- K5 dealer-persona-never-replies bug: root cause was missing trailing
  silence. ElevenLabs' server-side turn detection only commits a user turn
  after it hears silence *audio* following speech; the bridge relayed TTS
  bursts then went quiet, so the receiving agent's ASR never finalized the
  utterance (no `user_transcript`, no reply — and no `vad_score` events at
  all, so the earlier vad-peaks diagnostic was moot). Proven by a
  discriminating single-leg live probe: identical speech burst got zero
  response without trailing silence, full transcript + reply with it. Fix:
  `bridge.silence_feeder` streams 250ms silence chunks to each leg whenever
  no real audio was relayed to it in the last 250ms (open-mic emulation);
  feeder audio is never recorded/published and doesn't reset the silence
  watchdog. Live-verified end-to-end: real 75s bridge call produced a
  20-line multi-turn negotiation (lowballer quoted rent/advance/commission,
  negotiator enforced the written-agreement rule and declined). Earlier
  connection-health fixes (async `start_call`, `platform_settings.overrides`
  for `first_message`, suppressed first message `" "` not `""`) remain in
  place and regression-tested.
- Voice intake wiring (was "Real `set_spec_field` tool-call event shape"):
  widget dropped for `@elevenlabs/react` `ConversationProvider` +
  `useConversation` (v1.10 requires the provider). Estimator now has a
  `set_spec_field` client tool (typed param per spec field) and the
  `end_call` system tool; prompt instructs both. `make_agents` upserts
  client tools (no secret header) and sets `built_in_tools` — server
  quirks found live: entries need an extra `"type": "system"`
  discriminator, and the field must be omitted (not null) when unused.
  Live-verified via agent/tool GET; mic click-through still pending (above).
- K4 live wiring: `TOOLS_WEBHOOK_SECRET` set locally + on Render, live
  `make_agents` re-run done (header + `dealer_id` param registered). All 4
  deployed endpoints live-verified against real Supabase rows: no header →
  401; benchmark fallback scaled correctly; lowball → `confirm_then_flag` +
  scope question; `log_quote` wrote a real row (`total_first_year` 2,940,000,
  unflagged); `get_leverage` returned it to the other dealer and correctly
  hid the quoting dealer's own bid. Test rows cleaned up after. Note: data
  tables were empty (K2 seed data gone, likely during the K13 `user_id`
  migration) — re-run `seed.py` before the next live call test.
- Dealer seeding on spec create: `POST /specs` now seeds one dealer per
  `vertical.json` persona via `seed.seed_dealers` (shared with the
  `seed.py` script) and returns `dealers_seeded`; the frontend adapter
  passes the real count through. K9 unblocked on data.
- Transcript webhook auth: the unauthenticated custom-shape
  `/calls/{id}/transcript` endpoint is gone, replaced by
  `POST /webhooks/post-call` verifying the real ElevenLabs
  `ElevenLabs-Signature` HMAC via the `elevenlabs` SDK
  (`webhooks.construct_event`, 30-min timestamp tolerance, fail-closed
  without the secret). Dashboard-side wiring still pending (item above).

- Merge priority for `location` in the K8 intake merge logic: confirmed
  voice-wins (matches the existing code and mock data, no change needed).
- `OPENAI_API_KEY` set on Render (and Supabase env vars on Vercel). Deployed
  `/parse` live-verified: 401 without token; sample PDF returns only stated
  fields; blank image returns empty spec.
- Real Estimator agent id: obtained from the live make_agents run, now in
  `frontend/.env.local` (public id, not a secret). Backend deployed to
  https://negotiator-backend.onrender.com (`/health` 200, `/specs` 401
  without token — auth gate live).
