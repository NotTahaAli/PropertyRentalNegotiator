# TODO

Cross-component integration gaps that are blocked right now on secrets, live
external calls, or an unbuilt K-component — not on missing understanding of
the code. Update this file in the same commit as whatever resolves or adds
an item; delete resolved items instead of checking them off.

## Blocked: frontend K8 → backend wiring

- **`POST /parse`** — backend route now live (K6, `backend/src/app/parse.py`),
  verified against real OpenAI. Remaining blocker: the endpoint requires a
  Supabase JWT but `frontend/lib/api.ts:parseDoc()` sends no Authorization
  header — there is no client-side session to read a token from until K13
  frontend (login) exists. Unblocks with K13 frontend: add the bearer header
  to `parseDoc`. Backend also needs `OPENAI_API_KEY` set on Render at deploy.

- **`POST /specs`** — the real endpoint exists but three things block wiring
  it live, not one:
  1. Auth: it requires a Supabase JWT (`Depends(get_current_user_id)`);
     the frontend has no login/signup flow yet (K13 frontend not started),
     so it has no token to send.
  2. Request shape: frontend sends a flat `JobSpec`; backend's `SpecCreate`
     expects `{vertical, status, spec_json, benchmark_json?, confirmed?}` —
     the spec needs wrapping into `spec_json`.
  3. Response shape: frontend expects `{spec_id, dealers_seeded}` back;
     `create_spec` returns the full spec row and does not seed dealers —
     dealer seeding today is a standalone script (`backend/src/app/seed.py`),
     not tied to spec creation.
  Unblocks when K13 frontend (login) exists, and someone decides whether
  dealer-seeding-on-create becomes real backend behavior or stays a
  separate frontend-side call after `/specs` succeeds.

- **Real ElevenLabs Estimator agent id** — `frontend/.env.local`'s
  `NEXT_PUBLIC_ELEVENLABS_ESTIMATOR_AGENT_ID` is a placeholder. Getting a
  real one means running `cd backend && uv run python -m app.make_agents`
  against a real `ELEVENLABS_API_KEY` — a live write against the ElevenLabs
  account, using a key that lives in `backend/.env`. Not run automatically;
  run it yourself and paste the `estimator` id from the printed manifest
  into `frontend/.env.local`. Ask if you'd like it run for you instead.

- **Real `set_spec_field` tool-call event shape** —
  `frontend/components/intake/VoiceIntake.tsx` guesses the Convai widget
  event shape and falls back to a manual "Simulate voice completion"
  button. Confirming the real shape needs a live conversation against the
  deployed Estimator agent — same live-agent blocker as above, plus it
  spends ElevenLabs conversation credits.

- **`/calls/[spec_id]` route** — doesn't exist yet; K9 Call Center UI not
  started.

## Resolved

- Merge priority for `location` in the K8 intake merge logic: confirmed
  voice-wins (matches the existing code and mock data, no change needed).
