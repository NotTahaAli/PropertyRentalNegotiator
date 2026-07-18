# STATUS

## K8 — Intake UI (Owner A)

**Done, mock-first, `NEXT_PUBLIC_USE_MOCKS=true`:**
- 3-step intake flow at `/intake` (Voice → Docs → Confirm), single page, `useReducer` state.
- `lib/types.ts` — `JobSpec` mirrors `backend/config/vertical.json` spec_schema exactly, including `budget_monthly_rent` (required number, was missing from the original K8 plan draft — added after reading K1).
- Merge/provenance rules: `area_sqft`, `frontage_ft`, `current_rent` — doc wins over voice. Everything else (`location`, `floor`, `business_type`, `lease_years`, `parking`, `move_in`, `budget_monthly_rent`) — voice wins over doc. Manual edit always wins. Implemented as a priority-rank function in `app/intake/page.tsx`.
- Voice step: ElevenLabs Convai widget wrapper (`components/intake/VoiceIntake.tsx`), listens for `convai-message` events with `tool_name === "set_spec_field"`. Falls back to a "Simulate voice completion" button since the real K3 tool-call event shape isn't confirmed yet.
- Docs step: drag-drop upload, 2 slots (rent agreement / requirements), calls `parseDoc()` mock.
- Confirm step: editable form, source badges (voice/doc/manual/unset), required-field validation with scroll-to-first-invalid.
- Theme: night console colors + Bricolage Grotesque/Instrument Sans/IBM Plex Mono, done via Tailwind v4 `@theme` block in `globals.css` (repo has no `tailwind.config.ts` — Tailwind v4 is CSS-first config, differs from the original K8 plan draft which assumed a config file).
- `npx tsc --noEmit` and `npm run lint` both clean.

**What's mocked (needs real values before the 12–2 PM integration window):**
- `POST /parse` and `POST /specs` — see `lib/api.ts`, mock responses in `lib/mocks.ts`.
- ElevenLabs Estimator agent id — `.env.local` has a placeholder (`NEXT_PUBLIC_ELEVENLABS_ESTIMATOR_AGENT_ID`).
- `/calls/[spec_id]` route (K9) doesn't exist yet — confirmed submit correctly 404s there today, expected.

**Needed from B/C:**
- Real `NEXT_PUBLIC_ELEVENLABS_ESTIMATOR_AGENT_ID` once K3 runs.
- Confirm `POST /parse` returns `{ kind, partial_spec, raw_text_preview }` shape (`ParsedDoc` in `lib/types.ts`).
- Confirm `POST /specs` returns `{ spec_id, dealers_seeded }` (`IntakeSubmitResponse`).
- Confirm the real Estimator tool-call event name/shape for `set_spec_field` so `VoiceIntake.tsx`'s listener isn't guessing.

**Open question flagged, not yet resolved:** merge-priority group for `location` — neither the original K8 plan nor the K1-reconciliation instruction specified it. Defaulted to voice-wins (matches the plan's own `MOCK_SPEC._source.location: "voice"` example). Flag if doc should win instead.
