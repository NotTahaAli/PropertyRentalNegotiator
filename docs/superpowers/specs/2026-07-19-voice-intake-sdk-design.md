# Voice intake: real wiring via @elevenlabs/react (2026-07-19)

## Problem

Estimator agent was created with zero tools. Three symptoms: agent goes silent
after the confirmation summary (prompt says "end the call" but no `end_call`
tool exists), spec fields never fill (no `set_spec_field` tool exists; the
widget listeners in `VoiceIntake.tsx` were guessed event names that never
fire), and the widget shows default "Need help?" text.

## Decision (approved)

Drop the `<elevenlabs-convai>` widget. Use `@elevenlabs/react`
`useConversation` — native `clientTools` + `onDisconnect`, own UI.

## Backend

- `agent_factory.build_client_tool_schemas(config)` — one client tool
  `set_spec_field`: optional typed parameter per `spec_schema` field
  (number/string/boolean; enum values and date format in the description),
  `expects_response: false`. Agent records fields as the client answers,
  one or several per call.
- `AgentDef.end_call: bool` — estimator gets the `end_call` system tool via
  `prompt.built_in_tools`.
- `make_agents` upserts client tools (no secret header — they run in the
  browser) and sets `built_in_tools` when `end_call` is set.
- `vertical.json` estimator prompt: call `set_spec_field` after every answer;
  after the client confirms the summary, thank them and end the call.

## Frontend

- Add `@elevenlabs/react`. Rewrite `VoiceIntake.tsx`: delete widget embed,
  `Script` tag, guessed listeners, JSX declaration.
- `useConversation` with `clientTools.set_spec_field` (iterate params →
  `onField`) and `onDisconnect` → `onCallEnded`.
- Own Start/End interview buttons + status line from `status`/`isSpeaking`.
  Mock "Simulate voice completion" button stays.

## Properties

- Fields stream in per answer — manual hang-up loses nothing.
- Both hang-up paths (agent `end_call`, user button) hit `onDisconnect`.
- Mic denied / connection error → dim error text; "Continue to documents"
  remains the fallback path.

## Verify

Backend: pytest on new factory schemas. Live: re-run `make_agents`, one short
call — fields fill during call, call auto-ends after confirm.
