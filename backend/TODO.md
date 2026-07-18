# TODO

## K5 — dealer persona doesn't verbally reply to relayed audio (open)

**Status:** unresolved. Connection-health bug is fixed; conversational-reply bug is not.

**Context:** `bridge.py`'s dealer leg suppresses the persona agent's own greeting via
`conversation_config_override.agent.first_message` so the Negotiator speaks first. Two
related bugs were found and fixed via live testing against real ElevenLabs agents:

1. `start_call` had to become `async def` — bare `asyncio.create_task()` has no running
   event loop inside FastAPI's sync-endpoint threadpool. Fixed, regression-tested.
2. Dealer persona agents needed `platform_settings.overrides` enabling the `first_message`
   override (ElevenLabs rejects unpermitted per-conversation overrides with a 1008 policy
   violation). Fixed in `agent_factory.py`/`make_agents.py`, pushed live.
3. The suppressed `first_message` must be a single space `" "`, not `""` — an empty string
   never closes the agent's own turn, so it never starts listening for `user_audio_chunk`
   at all (confirmed dead: no ping, no response, indefinitely). Fixed in `bridge._dealer_init()`.

**What's still broken:** even with the connection verified healthy after fix #3 (dealer
leg pings normally, its own `" "` turn is recorded in the transcript), the `firm` persona
never produced a spoken reply to the Negotiator's relayed greeting audio — tested with a
patient 30-second live probe, well past any reasonable model-latency window.

**Isolated via live testing (each a separate real ElevenLabs connection):**
- Text `user_message` sent directly to the same suppressed-init agent → instant, correct,
  in-character reply every time. Rules out: prompt content, LLM, turn-state-after-suppression.
- Real-time-paced small-frame audio relay (20ms frames, matching natural TTS playback
  cadence) instead of one large burst → same silence. Rules out: chunk-size/pacing.
- Swapped which leg opens the WebSocket first → same result. Rules out: connection order.
- Swapped which agent gets the "speaks first" vs "waits for audio" role → same result
  (whichever agent is in "wait for audio" mode never replies to real audio, regardless of
  which specific agent it is). Rules out: agent-specific config elsewhere.

**Leading theory (unconfirmed):** ElevenLabs' server-side VAD/ASR may not process relayed
TTS-output audio (`audio_event.audio_base_64`) the same way it processes genuine microphone
input, even though both are labeled `pcm_16000` in `conversation_initiation_metadata`. Their
API docs don't cover ASR-input format specifics (chunk framing, required silence markers,
whether output audio is bit-compatible with expected input audio) — would need ElevenLabs
support or substantially more live-credit spend on trial-and-error to confirm.

**Recommended next step:** revisit after K4 (tool webhooks) lands — that's when persona
prompts get tuned anyway per the plan's own "prompt QA" task, and by then it'll be clear
whether this is a persona-tuning issue or a genuine relay/protocol problem worth escalating
to ElevenLabs directly. Don't re-attempt live diagnosis before then without a concrete new
hypothesis — four separate live experiments already ruled out the cheap explanations.
