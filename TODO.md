# TODO

Cross-component integration gaps that are blocked right now on secrets, live
external calls, or an unbuilt K-component — not on missing understanding of
the code. Update this file in the same commit as whatever resolves or adds
an item; delete resolved items instead of checking them off.

## Blocked: frontend K8 → backend wiring

- **`POST /parse`** — `frontend/lib/api.ts:parseDoc()` calls `${BASE}/parse`
  when `NEXT_PUBLIC_USE_MOCKS=false`, but no `/parse` route exists on the
  backend (K6 doc parser not started). Unblocks when K6 ships an endpoint
  returning `{kind, partial_spec, raw_text_preview}` (see `ParsedDoc` in
  `frontend/lib/types.ts`).

- **`POST /specs`** — the real endpoint exists; auth is now wired (K13
  frontend done on `auth-ui`: login/signup + Bearer token attached in
  `frontend/lib/api.ts`), but two shape gaps still block going live:
  1. Request shape: frontend sends a flat `JobSpec`; backend's `SpecCreate`
     expects `{vertical, status, spec_json, benchmark_json?, confirmed?}` —
     the spec needs wrapping into `spec_json`.
  2. Response shape: frontend expects `{spec_id, dealers_seeded}` back;
     `create_spec` returns the full spec row and does not seed dealers —
     dealer seeding today is a standalone script (`backend/src/app/seed.py`),
     not tied to spec creation.
  Unblocks when someone decides whether dealer-seeding-on-create becomes
  real backend behavior or stays a separate frontend-side call after
  `/specs` succeeds (the frontend adapter in `lib/api.ts` can wrap/unwrap
  either way).

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
