# TODO

Cross-component integration gaps that are blocked right now on secrets, live
external calls, or an unbuilt K-component — not on missing understanding of
the code. Update this file in the same commit as whatever resolves or adds
an item; delete resolved items instead of checking them off.

## Open: demo assets (K12)

- Golden call recordings, submission video, and written submission answers
  are not started — these need a human with live keys and a mic, no code
  blocks them. Everything else in K1–K13 is code-complete and live-verified.

## Resolved: 2026-07-19 live verification pass

All items previously tracked here as "pending live verification" are done:
`log_call_status` confirmed for every outcome in the taxonomy (`quote`,
`final_quote`, `vague_quote`, `callback` with a real `callback_at`,
`declined`); persona anchor figures confirmed spoken live by all 4 personas;
persona `end_call` confirmed not to cut a real negotiation short; decline
auto-block confirmed against real Supabase rows and picked up by the
frontend poll; negotiator `first_message` override + dealer-answers-first
confirmed live; call-history + citation deep-link, report ranking/flagging/
citation, live-audio player + stereo recording, half-duplex turn-taking, and
voice intake mic click-through all confirmed in a real authenticated
browser session; `get_leverage` competitor-citation behavior confirmed
(negotiator cited a competing quote mid-negotiation); Render redeploy of the
current `tools.py`/`get_leverage` shape confirmed serving.

## Resolved

- **Post-call webhook never fired for roleplay calls** — workspace-level
  webhook was registered and enabled (confirmed in the ElevenLabs dashboard:
  URL, ID, enabled toggle all correct) but the negotiator agent still had
  post-call webhooks off at the **agent level** — ElevenLabs supports
  enabling webhooks at both workspace and individual-agent scope, and only
  the workspace one had ever been touched. No code in this repo controls
  that agent-level setting (`agent_factory.py`/`make_agents.py` have nothing
  webhook-related for it — it's dashboard-only). Enabled it on the negotiator
  agent in the dashboard; roleplay call now completes and lands
  transcript/outcome via `POST /webhooks/post-call` as designed.
- **Follow-up calls could make a real quote silently disappear** — two
  compounding issues, both in the "don't repeat a stale number" area.
  (1) Prompt told the negotiator "Do not ask them to repeat these terms" for
  a dealer's prior quote and to just push for an improvement — meaning a
  follow-up call could end without ever calling `log_quote` again for a
  property nobody re-confirmed. (2) The frontend then compounded it:
  `DealerCallState.quotes` was always set to *only* whatever the current
  round's own `listQuotes(callId)` returned — live, on completion, and even
  on page-reload hydration — so a round that didn't re-touch a property made
  that property's last known quote vanish from the UI, even though the row
  was still safely in Supabase (rounds never share a `call_id`, so nothing
  was ever actually deleted). Fixed both: `api._prior_call_summary` now
  tells the negotiator to confirm the prior quote is still accurate every
  follow-up call and log it again either way (same numbers if confirmed,
  updated numbers if not) — `backend/tests/test_api.py`. Frontend
  `useCallCenter.ts` now upserts fresh quotes onto existing ones by
  `property_ref` (`mergeQuotesByProperty`) at all three write sites (live
  poll, round completion, and initial hydration merged across *every* round,
  not just the latest) instead of replacing the array wholesale.
- **2026-07-19 deploy round** — Supabase migrations pushed (`dealers.status`,
  `calls.callback_at`/`callback_note`) and confirmed up to date; `make_agents`
  re-run live, carrying this session's `get_leverage` reshape, required
  `property_ref`, the 5th webhook tool (`log_call_status`), and the
  dynamic-variable id-binding fix out to the live ElevenLabs agents.
- **Role-play widget embed** — turned out already done, not a placeholder;
  this TODO item was stale. `RoleplaySession.tsx` is fully wired to
  `@elevenlabs/react` (`ConversationProvider` + `useConversation`, same
  pattern as K8's `VoiceIntake.tsx`), consuming the `negotiator_agent_id` +
  `dynamic_variables` that `POST /calls/start` (`mode: "roleplay"`) returns.
  Only shows a "voice available when wired" placeholder under `USE_MOCKS` or
  a missing agent id — both deliberate fallbacks, not stub states.
- **Follow-up calls had no memory of the dealer** — two separate faults, both
  fixed together because fixing either alone looks worse than fixing neither.
  (1) The negotiator received no prior-call context, so it reopened every
  follow-up cold and asked for a quote it already had. `_dynamic_variables` now
  carries `round_number` and a `prior_call_summary` built from this dealer's own
  last quote plus the tail of the last transcript. (2) `_dealer_dynamic_variables`
  regenerated the persona's numbers from its band on *every* call, so a dealer
  who said 151,000 in round 1 said something else in round 2. It now reuses the
  dealer's own last logged quote verbatim and tells the persona to stand by it.
  Scoped strictly to the dealer's own history — other dealers' bids remain
  exclusively behind `get_leverage`, per the honesty guardrail; there is a test
  asserting other dealers' calls are excluded.
- **UI asserted "no numbers committed" about calls it knew nothing about** — when
  the backend recorded no outcome (call never finalized, or the post-call webhook
  never landed) the frontend defaulted to `callback`, whose label claims the
  dealer committed no numbers. It now leaves the outcome undefined and shows
  "Call ended — outcome not recorded yet". This is the likely explanation for the
  screenshot where a dealer clearly quoted 151,000 and the chip still said no
  numbers: the outcome was null, not wrong.
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
  Live-verified via agent/tool GET and a real mic click-through.
- K4 live wiring: `TOOLS_WEBHOOK_SECRET` set locally + on Render, live
  `make_agents` re-run done (header + `dealer_id` param registered). All 4
  deployed endpoints live-verified against real Supabase rows: no header →
  401; benchmark fallback scaled correctly; lowball → `confirm_then_flag` +
  scope question; `log_quote` wrote a real row (`total_first_year` 2,940,000,
  unflagged); `get_leverage` returned it to the other dealer and correctly
  hid the quoting dealer's own bid. Test rows cleaned up after.
- Dealer seeding on spec create: `POST /specs` now seeds one dealer per
  `vertical.json` persona via `seed.seed_dealers` (shared with the
  `seed.py` script) and returns `dealers_seeded`; the frontend adapter
  passes the real count through. K9 unblocked on data.
- Transcript webhook auth: the unauthenticated custom-shape
  `/calls/{id}/transcript` endpoint is gone, replaced by
  `POST /webhooks/post-call` verifying the real ElevenLabs
  `ElevenLabs-Signature` HMAC via the `elevenlabs` SDK
  (`webhooks.construct_event`, 30-min timestamp tolerance, fail-closed
  without the secret).
- Merge priority for `location` in the K8 intake merge logic: confirmed
  voice-wins (matches the existing code and mock data, no change needed).
- `OPENAI_API_KEY` set on Render (and Supabase env vars on Vercel). Deployed
  `/parse` live-verified: 401 without token; sample PDF returns only stated
  fields; blank image returns empty spec.
- Real Estimator agent id: obtained from the live make_agents run, now in
  `frontend/.env.local` (public id, not a secret). Backend deployed to
  https://negotiator-backend.onrender.com (`/health` 200, `/specs` 401
  without token — auth gate live).
