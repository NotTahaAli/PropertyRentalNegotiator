# STATUS

## Branch state (Owner A) — merged to main

`k9-roleplay` + `k10-report` both merged into `main` (fast-forward, no
conflicts, `main` was untouched since `k9-roleplay` branched — nothing
new landed from B/C to reconcile). Pushed.

Full mock demo path verified end-to-end **in browser, by the user** (not
just code-traced): `/intake` (voice/skip → docs optional → confirm) →
`/calls/[spec_id]` → call all 4 dealers round 1 (3 done+quote, Stonewaller
declined) → round 2 on all (Firm-but-Fair's leverage concession renders:
100,000 rent, commission waived, cites the 65,000 competing offer) →
"View report" enables only once every dealer is terminal → `/report/
[spec_id]` (Firm #1, Lowballer rank 3 + flagged not omitted, Stonewaller
shown declined separately, recommendation cites the right line) →
citation click lands on `/calls/[spec_id]?call=4&line=4`, correct line
highlighted → 375px (all three pages, no horizontal scroll, RankedTable's
stacked-card layout holds) → print preview on `/report` (buttons hidden,
readable on white). All eight steps passed.

**Done vs mock-verified-only** — be precise about this distinction:
- **Done** (works regardless of backend state): all frontend UI/state
  logic above — round tracking, round cap, mock content, citation
  linking/highlighting, report ranking/flagging logic, responsive/print
  CSS. This is real, tested code, not a demo trick.
- **Mock-verified-only** (untested against real backend, will need a
  real pass before the actual demo): everything above only ran with
  `NEXT_PUBLIC_USE_MOCKS=true`. Real-mode has never been clicked through
  — blocked on the open items below.

**Still open (not this session's to fix):**
- **C:** CORS blocking real-mode verification (roleplay call start and
  general API calls from the deployed frontend origin) — nothing in
  real mode can be smoke-tested until this is resolved.
- **B:** bridge-mode audio overlap (two legs' audio talking over each
  other) — bridge mode remains the demo fallback path, roleplay is
  primary, but bridge should still work for the K5 fallback story.
- **C:** K11 red-flag engine incorrectly flags Upseller (should only be
  Lowballer per the 30%+-under-benchmark rule — Upseller is *above*
  market, flagging it is backwards).

## K10 Report UI (Owner A) — done on `k10-report` branch (merged to main)

`GET /report/{spec_id}` doesn't exist on the backend yet (K10 gen is C's
half, still "Not started" per the plan doc) — built the mock to master
plan §304/§406/§414/§415: ranked by `total_first_year`, flags with reasons,
recommended deal, plain-language why, `[call N, line M]` citations,
recording links. `lib/types.ts` adds `ReportRow`/`Report`, reusing
`Quote`/`CallOutcome`/`Persona` as-is — no forking. `lib/api.ts` adds
`getReport()`; 404/down surfaces the same clean-error pattern K9 uses for
`dealersError`.

Mock snapshot (`MOCK_REPORT` in `mocks.ts`) is the final-round-per-dealer
state of the 2-round demo: Firm-but-Fair rank 1 at the round-2 leveraged
1,460,000 (leverage story: cites Lowballer's real 65,000/mo round-1 quote,
trims rent 110k→100k, waives commission), Upseller rank 2 at its actual
total, Lowballer rank 3 — flagged (reused `Quote.flagged`/`flag_reason`,
no parallel lookup table) and explicitly ranked *last* despite the lowest
headline number, not omitted. Stonewaller: `rank: null`, shown separately
as declined (round 1 — a dealer who already said the unit's rented doesn't
get redialed, so it never reaches round 2 in this snapshot).

Citation integrity: table and recommendation used to risk citing two
different `[call N, line M]` guesses. Fixed at the type level — `Report`
has no separate citation field; `RecommendationBlock` looks up the
recommended row and reads `call_number`/`citation_line` off *it*, so the
two can't drift apart structurally, not just by convention.

K9 addition (`app/calls/[spec_id]/page.tsx`): reads `?call=&line=` from a
citation click, maps `call` (1-based) to `MOCK_DEALERS[call-1]`, selects
that dealer, and highlights the line in `TranscriptStream` (new
`highlightLine` prop, scroll+pulse). The synchronous "seed this dealer as
already-done" behavior (`useCallCenter.seedMockCompleted`) is gated
`if (!USE_MOCKS) return` — real mode only selects/highlights against
whatever real data actually exists; it never fabricates a completed call.
Components: `components/report/{RankedTable,FlagChip,RecommendationBlock,
CitationLink,PriceCell}.tsx`, all new, all under 200 lines. `app/report/`
layout mirrors `calls/layout.tsx` (Protected-wrapped). Print: `print:`
Tailwind variants on the report layout/header (white bg, hide nav).

Verified: `tsc --noEmit`, `eslint .`, `next build` clean (`ƒ
/report/[spec_id]` present). Not yet done: browser click-through
(citation round-trip, 375px, print-preview) — next session should smoke
test before merge. Assumption flagged: the `call` number → dealer mapping
is mock-only (`MOCK_DEALERS` index); real mode has no backend-assigned
call numbering yet, that's C's K10-gen territory whenever it ships.

## K9 roleplay panel (Owner A) — done on `k9-roleplay` branch (merged to
main; `call-center-ui` was already merged to main for K9 v1)

Roleplay promoted from fallback placeholder to primary demo call path (bridge
is broken; roleplay is what judges see live). `lib/characterCards.ts` (4
scripted persona cards + a `human` fallback card, sourced strictly from
`vertical.json` persona_prompts — no absolute PKR figures invented, config
only gives ratios/qualitative rules) + `CharacterCard.tsx` + `RoleplaySession.tsx`
(real: `ConversationProvider`/`useConversation` from `@elevenlabs/react`,
mirrors K8 VoiceIntake's inline pattern — no separate SDK primitive existed to
reuse, flagged and built fresh; mock: static placeholder, no separate
"simulate" button needed since `useCallCenter`'s existing mock timer path
already auto-completes on click regardless of the roleplay toggle).

`useCallCenter.ts`: added `roleplay: Record<dealerId,bool>` + `setRoleplay`,
extracted `pollUntilDone` (shared by bridge's post-POST poll and roleplay's
post-disconnect poll — same backend statuses either way), added
`startRoleplay`/`finishRoleplaySession`. `DealerCard`'s "Answer as dealer"
toggle now drives real state instead of a local dead-end placeholder; bridge
mode's `noBridgeAgent` (persona `human`) check untouched for bridge, bypassed
for roleplay since a human is on the line either way. `CallStatusPanel` grows
a two-column branch (character card + session controls) while
idle/calling/live and roleplay is on; falls through to the existing
transcript/quote/audio render, unmodified, once done/failed — bridge mode's
render path in that file is untouched.

Confirmed: starting a roleplay call on a dealer with an existing completed
bridge-mode quote creates a new call row at round+1 (same `nextRound()` path
bridge already uses) — both calls/quotes stay visible independently, nothing
overwritten.

Also found `@elevenlabs/react` in `package.json`/lockfile but missing from
`node_modules` (tsc failed on it before any of this work) — ran `npm ci` to
resync from the lockfile, no version change.

Verified: `tsc --noEmit`, `eslint .`, `next build` all clean (`ƒ
/calls/[spec_id]` present). Not yet done: browser click-through (real voice
connect needs real agent IDs + mic; mock click-through untested this pass —
next session should smoke-test `/calls/spec_mock_001` with roleplay toggled
on for one dealer before merge).

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
