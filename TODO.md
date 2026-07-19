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

- **`make_agents` re-run needed for K4/K7 prompt+schema changes** —
  `log_quote` now requires `binding` in its tool schema, and the negotiator
  prompt gained the always-ask-for-a-written-quote instruction plus friction
  handling (interruptions, vague answers, callback commitments). Deployed
  ElevenLabs agents/tools still carry the old config until
  `uv run python -m app.make_agents` is re-run with live keys.

- **Post-call webhook dashboard wiring** — backend endpoint
  `POST /webhooks/post-call` is built and HMAC-verified (fail-closed on env
  `ELEVENLABS_WEBHOOK_SECRET`; extracts `call_id` from the conversation's
  dynamic variables, maps the transcript, derives outcome). Remaining steps
  are dashboard-side: create the post-call webhook in the ElevenLabs
  dashboard pointing at
  `https://negotiator-backend.onrender.com/webhooks/post-call`, then set the
  generated secret as `ELEVENLABS_WEBHOOK_SECRET` locally and on Render.

## Blocked: K7 live verification

- **`TAVILY_API_KEY` not set anywhere** — K7 benchmark fetch + dealer
  discovery fail soft (null benchmark, no discovered dealers) until the key
  is set locally and on Render. Then live-verify: `POST /specs` with a real
  location (e.g. "Gulberg Lahore"), check the Supabase row's
  `benchmark_json` has `{per_sqft_low, per_sqft_high}`, tavily dealer rows
  exist (`persona="human"`), and `POST /tools/get_benchmark` returns
  `source: "cached"`. Same run also live-verifies the K11 discovery
  hardening: no duplicate dealer names, no blank names, no portal/directory
  junk (Zameen/OLX/Graana) among the inserted rows.

## Blocked: K11 reflag has no UI caller

- **`POST /specs/{id}/reflag` is curl-only** — endpoint is live (JWT +
  ownership, re-runs `evaluate_red_flags` on all of a spec's quotes, may
  unflag) but nothing in the frontend calls it. Natural caller is the K10
  report page ("Re-check flags" before ranking) — wire a `lib/api.ts`
  wrapper + button there when K10 exists. Until then:
  `curl -X POST -H "Authorization: Bearer $JWT" .../specs/$SPEC_ID/reflag`.

## Open: manual click-throughs

- **Live-audio player + stereo recording browser check** — `LiveAudio.tsx`
  (leg-tagged WS stream, Web Audio, panned L/R, per-leg mute) and the new
  time-aligned stereo recording are unit-tested + build-clean but not yet
  heard in a browser. Needs one real bridge call on `/calls/[spec_id]`:
  confirm both voices audible live while the call runs, then replay the
  recording and confirm negotiator left / dealer right with no overlap.
  If the browser blocks autoplay, clicking either mute button unlocks it.

- **Live voice intake click-through** — voice path fully wired
  (`set_spec_field` client tool + `end_call` live on the Estimator,
  `VoiceIntake.tsx` on `@elevenlabs/react`), but nobody has run a real
  mic conversation through it yet. Needs a human: start interview, answer,
  watch fields fill, confirm, verify auto-hangup. Spends ~2 min of credits.

## Resolved

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
