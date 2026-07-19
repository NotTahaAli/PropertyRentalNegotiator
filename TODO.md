# TODO

Cross-component integration gaps that are blocked right now on secrets, live
external calls, or an unbuilt K-component — not on missing understanding of
the code. Update this file in the same commit as whatever resolves or adds
an item; delete resolved items instead of checking them off.

## Blocked: frontend K8 → backend wiring

- **Dealer seeding on spec create** — `POST /specs` is now fully wired from
  the frontend (auth token + shape adapter in `frontend/lib/api.ts`: wraps
  the flat `JobSpec` into `spec_json`, unwraps the returned row into
  `{spec_id, dealers_seeded}`). But `create_spec` does not seed dealers —
  seeding is still the standalone `backend/src/app/seed.py` script, so the
  adapter reports `dealers_seeded: 0`. Open decision: seed-on-create in the
  backend, or a separate frontend call after `/specs` succeeds. K9 needs
  dealers to exist to show anything.

- **Real `set_spec_field` tool-call event shape** —
  `frontend/components/intake/VoiceIntake.tsx` guesses the Convai widget
  event shape and falls back to a manual "Simulate voice completion"
  button. Confirming the real shape needs a live conversation against the
  deployed Estimator agent — same live-agent blocker as above, plus it
  spends ElevenLabs conversation credits.

- **`/calls/[spec_id]` route** — doesn't exist yet; K9 Call Center UI not
  started.

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

## Resolved

- K4 live wiring: `TOOLS_WEBHOOK_SECRET` set locally + on Render, live
  `make_agents` re-run done (header + `dealer_id` param registered). All 4
  deployed endpoints live-verified against real Supabase rows: no header →
  401; benchmark fallback scaled correctly; lowball → `confirm_then_flag` +
  scope question; `log_quote` wrote a real row (`total_first_year` 2,940,000,
  unflagged); `get_leverage` returned it to the other dealer and correctly
  hid the quoting dealer's own bid. Test rows cleaned up after. Note: data
  tables were empty (K2 seed data gone, likely during the K13 `user_id`
  migration) — re-run `seed.py` before the next live call test.
- Transcript webhook (`api.py` `/calls/{id}/transcript`) still unauthenticated
  — separate mechanism (ElevenLabs post-call HMAC webhook, dashboard-side),
  unchanged by K4; keep on the list until wired.

- Merge priority for `location` in the K8 intake merge logic: confirmed
  voice-wins (matches the existing code and mock data, no change needed).
- `OPENAI_API_KEY` set on Render (and Supabase env vars on Vercel). Deployed
  `/parse` live-verified: 401 without token; sample PDF returns only stated
  fields; blank image returns empty spec.
- Real Estimator agent id: obtained from the live make_agents run, now in
  `frontend/.env.local` (public id, not a secret). Backend deployed to
  https://negotiator-backend.onrender.com (`/health` 200, `/specs` 401
  without token — auth gate live).
