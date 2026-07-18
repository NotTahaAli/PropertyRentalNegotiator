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

## Resolved

- Merge priority for `location` in the K8 intake merge logic: confirmed
  voice-wins (matches the existing code and mock data, no change needed).
- Real Estimator agent id: obtained from the live make_agents run, now in
  `frontend/.env.local` (public id, not a secret). Backend deployed to
  https://negotiator-backend.onrender.com (`/health` 200, `/specs` 401
  without token — auth gate live).
