# STATUS

## K13 — Auth UI (Owner A) — done on `auth-ui` branch

- Supabase Auth via supabase-js directly (per C's K13 design spec — anon key, no FastAPI auth routes). New dep: `@supabase/supabase-js`.
- `/login` + `/signup` (email+password), signup handles the email-confirmation-required case. Logged-in visitors to auth pages bounce to `/intake`; `/login?next=` honored.
- `/intake` wrapped in a client-side `Protected` guard (session lives in supabase-js localStorage — middleware can't see it; guard is reusable for `/calls` and `/report`).
- Nav shows account email + sign out when logged in (intake + landing).
- `lib/api.ts`: `parseDoc`/`submitSpec` attach `Authorization: Bearer <token>` when `NEXT_PUBLIC_USE_MOCKS=false`. Mock mode simulates a session (`demo@negotiator.pk`) — full intake flow works with zero Supabase config.
- Verified: `tsc`/`eslint`/`next build` clean; mock-mode flow renders with session; anon key probed live against Supabase Auth (responds correctly). Full browser signup→login→intake click-through still pending a human.
- Env: `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` in `.env.local` (real values) and `.env.example` (placeholders).

## K8 — Intake UI (Owner A)

Done (mock mode), redesigned by A. Real-endpoint swap checklist updated for auth:
- `/specs` is live (K2) and now requires Bearer token — handled by K13 work above. Swap = set `NEXT_PUBLIC_USE_MOCKS=false` + log in.
- `/parse` still doesn't exist (K6) — parse stays mocked until then.
- No `PATCH /specs` (C's documented gap) — confirm currently POSTs a fresh spec.

## Blocked on B/C

- **B:** real `NEXT_PUBLIC_ELEVENLABS_ESTIMATOR_AGENT_ID` (`agents.generated.json` isn't in the repo) + confirmation of the Estimator `set_spec_field` tool-call event shape for `VoiceIntake.tsx`.
- **C:** is Supabase email confirmation ON or OFF? (Both handled; OFF = smoother demo.)
- **C:** `/parse` endpoint (K6).
