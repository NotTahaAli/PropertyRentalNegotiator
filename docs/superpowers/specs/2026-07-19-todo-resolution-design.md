# TODO.md resolution — design

Date: 2026-07-19. Scope: resolve the resolvable TODO.md items. Session was
autonomous; decisions taken with lazy defaults, documented here for review.

## Item 1 — dealer seeding on spec create

**Decision: seed-on-create in the backend** (option A).

Options weighed:
- **A. Backend seeds in `POST /specs`** — one round-trip, atomic from the
  frontend's view, K9 unblocked, `frontend/lib/api.ts` adapter already
  expects a `dealers_seeded` count. Picked.
- B. Separate frontend call after `/specs` succeeds — extra wiring, second
  failure mode, no benefit.
- C. Leave until K9 — blocks the demo path for no reason.

Implementation: extract the persona loop from `seed.py` into
`seed_dealers(spec_id) -> list[dict]` (one dealer per
`vertical.json` persona, `source="auto"` vs `"seed"` distinction not needed —
keep `"seed"`). `api.py create_spec` calls it after insert and returns
`{**spec_row, "dealers_seeded": n}`. `seed.py` script reuses the same
function. Frontend `submitSpec` reads `row.dealers_seeded ?? 0`.

## Item 2 — transcript webhook auth

**Decision: replace the custom unauthenticated `/calls/{id}/transcript`
endpoint with a real ElevenLabs post-call webhook endpoint,
`POST /webhooks/post-call`, HMAC-verified** (option A).

Options weighed:
- **A. Real post-call webhook endpoint** — ElevenLabs signs webhooks with
  `ElevenLabs-Signature: t=<ts>,v0=<hmac_sha256(f"{t}.{body}")>`; the
  installed `elevenlabs` SDK ships `webhooks.construct_event(rawBody,
  sig_header, secret)` which verifies signature + 30-min timestamp
  tolerance. The real payload is `{type: "post_call_transcription", data:
  {...}}` with `data.conversation_initiation_client_data.dynamic_variables`
  — which already carries our `call_id` (set at `/calls/start`). Picked.
- B. Bolt a shared secret onto the existing custom-shape endpoint — payload
  shape doesn't match what ElevenLabs actually sends, so it could never be
  wired to the dashboard; dead code with a lock on it.
- C. Leave — item stays forever.

Implementation: new `webhooks_router` in `api.py`. Raw body via `Request`;
verify with SDK against env `ELEVENLABS_WEBHOOK_SECRET` (fail-closed: unset
secret → 401, same posture as `TOOLS_WEBHOOK_SECRET`). Map
`data.transcript` (`role: agent|user`, skip null/empty messages) to our
`[{line, speaker, text}]` shape — `agent` → `negotiator`, `user` → `dealer`
(roleplay: the human plays the dealer). Outcome via existing
`bridge.derive_outcome`. Events without our `call_id` in dynamic variables
are acked `{"status": "ignored"}` (200) so ElevenLabs doesn't retry-hammer.
Old endpoint + `TranscriptWebhook` model deleted (nothing calls them: K9
unbuilt, bridge writes via `crud` directly).

Remaining user-side step (stays in TODO): generate the webhook secret in the
ElevenLabs dashboard, point it at
`https://negotiator-backend.onrender.com/webhooks/post-call`, set
`ELEVENLABS_WEBHOOK_SECRET` locally + on Render.

## Item 3 — K5 persona no-reply: new diagnostic (no credit spend now)

TODO says don't re-attempt without a concrete new hypothesis. Found a cheap
decisive diagnostic instead of a fix: the conversation WebSocket emits
`vad_score` server events (server-side voice-activity score of the *input*
audio on that leg). `bridge.relay_loop` currently drops them. Change:
collect per-leg VAD scores on the sink, print one peak-per-leg line at call
end. Next live probe then answers the open question directly — dealer-leg
peak ≈ 0 confirms "server VAD doesn't register relayed TTS audio as
speech"; peak high means VAD fires and the problem is downstream
(ASR/turn-taking). TODO updated to point at this.

## Not resolvable now (stay in TODO)

- `/calls/[spec_id]` route — that's K9 itself.
- Live voice-intake mic click-through — needs a human with a microphone.

## Testing

- `test_api.py`: create-spec seeds dealers + returns count (crud mocked);
  existing create-spec tests patched for the new `create_dealer` calls;
  webhook tests replace the old transcript test — valid signature writes the
  call, bad signature 401, missing env secret 401, missing call_id acked
  as ignored.
- `test_bridge.py`: `relay_loop` records `vad_score` events per leg.
