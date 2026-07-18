# STATUS

## K9 — Call Center UI (Owner A) — IN PROGRESS on `call-center-ui` branch

Build order: ① types+mocks+api ✓ → ② useCallCenter hook ✓ (state machine
approved by A) → ③ components ✓ (`components/calls/`: StateBadge, DealerCard,
TranscriptStream, AudioPlayer, QuoteChip, CallStatusPanel) → ④ page ✓
(`app/calls/[spec_id]/page.tsx` + `app/calls/layout.tsx`, auth-guarded, same
nav pattern) → ⑤ verify + docs — **IN PROGRESS, resume here.**

⑤ checkpoint — done so far: `tsc` clean, `eslint` clean (after removing an
unused eslint-disable in AudioPlayer), `next build` clean (route
`ƒ /calls/[spec_id]` present). Still to do, in order:
1. Browser/dev-server smoke test of `/calls/spec_mock_001` in mock mode:
   Call all → statuses walk (calling 2s → live → transcript streams → done)
   → stonewaller shows Declined chip (no quote), other three show QuoteChip
   + audio player; per-dealer retry from failed; 375px layout check.
2. If smoke passes: mark K9 done in CLAUDE.md table + HTML plan tile/row
   (same commit), fold this section's assumptions into the K9-done note.
3. Commit remaining work + push `call-center-ui`, then merge to main on A's
   go (same flow as auth-ui).
Roleplay widget embed + live-audio WS player remain out of v1 (assumptions
2/3 below). Timeout hint: ticker caps at 3:00, shows "call timed out?" when
live past 180s (backend MAX_CALL_SECONDS).

Assumptions made while B slept:
1. No live transcript text exists backend-side — text lands complete in
   `transcript_json` at call end; UI polls `GET /calls/{id}` every 2s. Mock
   streams lines on a timer for the demo. Swap point if B adds a text WS:
   `runRealCall` internals in `useCallCenter.ts` only.
2. Live-audio WS (`/calls/{id}/stream`, base64 PCM-16k) exists but is NOT
   wired into K9 v1 — needs an AudioWorklet PCM player, deferred.
3. Roleplay = embed the negotiator agent (human answers as dealer) using
   `/calls/start` mode=roleplay response; UI ships a placeholder panel until
   the widget dynamic-variables attribute is verified.
4. UI state "calling" is client-only (POST in flight); backend statuses are
   only running/completed/failed.
5. Real-mode dealer list renders empty until the dealer-seeding decision (C).
6. Backend transcript line numbers are 1-based contiguous (verified in
   `bridge.accumulate_transcript`) — mock matches; K10 citations safe.

For the humans:
- **B:** `POST /calls/{id}/transcript` (roleplay post-call webhook) is
  unauthenticated — your flagged open security item; needs the shared
  webhook secret once the real ElevenLabs payload is verified.
- **C:** decision needed on dealer seeding per spec — until then, real-mode
  `/calls/[spec_id]` shows an empty dealer list, blocking real-mode demo of
  K9. (Mock demo unaffected.)

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
