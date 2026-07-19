# TODO

Cross-component integration gaps that are blocked right now on secrets, live
external calls, or an unbuilt K-component — not on missing understanding of
the code. Update this file in the same commit as whatever resolves or adds
an item; delete resolved items instead of checking them off.

## Blocked: frontend K8 → backend wiring

- **`/calls/[spec_id]` route** — doesn't exist yet; K9 Call Center UI not
  started.

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
  `source: "cached"`.

## Blocked: K5 dealer persona doesn't verbally reply to relayed audio

Live-tested against real ElevenLabs agents. Connection-health bug is fixed;
conversational-reply bug is not.

- **Fixed along the way** (three real bugs live testing caught, unit tests
  couldn't): `start_call` needed `async def` (bare `asyncio.create_task` has
  no event loop in FastAPI's sync-endpoint threadpool); dealer personas
  needed `platform_settings.overrides` enabling the `first_message` override
  (ElevenLabs rejects unpermitted per-conversation overrides); the suppressed
  `first_message` must be a single space `" "`, not `""` — empty string
  never closes the agent's own turn, so it never starts listening for
  `user_audio_chunk` at all. All three fixed and regression-tested.

- **Still open:** even with the connection verified healthy (dealer leg
  pings normally, its own `" "` turn is recorded), the `firm` persona never
  produced a spoken reply to the Negotiator's relayed audio in a patient
  30-second live probe. Isolated via separate live experiments: text
  `user_message` to the same suppressed-init agent replies instantly and
  correctly (rules out prompt/LLM/turn-state); real-time-paced small-frame
  audio relay instead of one large burst made no difference (rules out
  chunk-size/pacing); swapping WebSocket connection order made no difference
  (rules out connection order); swapping which agent speaks first vs waits
  made no difference (rules out agent-specific config). Leading theory:
  ElevenLabs' server-side VAD/ASR may not process relayed TTS-output audio
  the same way it processes real microphone input, even though both report
  `pcm_16000`. Their docs don't cover ASR-input format specifics enough to
  confirm — would need ElevenLabs support or substantially more live-credit
  spend on trial-and-error. Revisit after K4 lands (persona prompts get
  tuned then anyway); don't re-attempt without a concrete new hypothesis —
  four separate live experiments already ruled out the cheap explanations.
  **New decisive diagnostic now wired (no credit spent yet):** the
  conversation WebSocket emits `vad_score` server events — the server-side
  voice-activity score of the audio *sent to* that leg. `bridge.relay_loop`
  now records them per leg and `run_bridge` prints one
  `call <id> vad peaks: {...}` line at call end. On the next live bridge
  probe, read that line in Render logs: dealer-leg peak ≈ 0 confirms the
  VAD/relayed-TTS-audio theory (then escalate to ElevenLabs support with
  that evidence); a high peak refutes it and moves suspicion downstream to
  ASR/turn-taking.

- **Live voice intake click-through** — voice path fully wired
  (`set_spec_field` client tool + `end_call` live on the Estimator,
  `VoiceIntake.tsx` on `@elevenlabs/react`), but nobody has run a real
  mic conversation through it yet. Needs a human: start interview, answer,
  watch fields fill, confirm, verify auto-hangup. Spends ~2 min of credits.

## Resolved

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
