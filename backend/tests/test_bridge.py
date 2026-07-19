import asyncio
import base64
import json
import struct
import wave
import io

from app import bridge


class FakeWebSocket:
    def __init__(self, messages=None):
        self._messages = list(messages or [])
        self.sent = []

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def send(self, message):
        self.sent.append(message)


def _pcm16(*samples: int) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


def _unpack_wav(wav_bytes: bytes) -> list[int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
        frames = w.readframes(w.getnframes())
    return list(struct.unpack(f"<{len(frames) // 2}h", frames))


def test_mix_pcm_sums_and_clips():
    neg = _pcm16(100, 20000, -20000)
    dealer = _pcm16(50, 20000, -20000)

    wav_bytes = bridge.mix_pcm(neg, dealer)

    assert _unpack_wav(wav_bytes) == [150, 32767, -32768]


def test_mix_pcm_handles_unequal_lengths():
    neg = _pcm16(100, 200, 300)
    dealer = _pcm16(10)

    wav_bytes = bridge.mix_pcm(neg, dealer)

    assert _unpack_wav(wav_bytes) == [110, 200, 300]


def test_accumulate_transcript_labels_two_speakers_and_dedupes():
    events = [
        ("negotiator", "agent_response", "Hello, calling about a shop."),
        ("negotiator", "user_transcript", "Hello, calling about a shop."),
        ("dealer", "agent_response", "Yes hello."),
        ("dealer", "user_transcript", "Yes hello."),
    ]

    transcript = bridge.accumulate_transcript(events)

    assert transcript == [
        {"line": 1, "speaker": "negotiator", "text": "Hello, calling about a shop."},
        {"line": 2, "speaker": "dealer", "text": "Yes hello."},
    ]


def test_accumulate_transcript_fills_gap_when_agent_response_missing():
    events = [
        ("dealer", "user_transcript", "Only heard via the other leg's ASR."),
    ]

    transcript = bridge.accumulate_transcript(events)

    assert transcript == [
        {"line": 1, "speaker": "dealer", "text": "Only heard via the other leg's ASR."},
    ]


def test_derive_outcome_quote_when_dealer_states_a_number():
    transcript = [
        {"line": 1, "speaker": "negotiator", "text": "What's the rent?"},
        {"line": 2, "speaker": "dealer", "text": "It's 150000 per month."},
    ]

    assert bridge.derive_outcome(transcript) == "quote"


def test_derive_outcome_declined_when_dealer_declines():
    transcript = [
        {"line": 1, "speaker": "dealer", "text": "Sorry, not interested in renting right now."},
    ]

    assert bridge.derive_outcome(transcript) == "declined"


def test_derive_outcome_callback_default():
    transcript = [
        {"line": 1, "speaker": "dealer", "text": "Let me check and call you back."},
    ]

    assert bridge.derive_outcome(transcript) == "callback"


def test_derive_outcome_callback_when_transcript_empty():
    assert bridge.derive_outcome([]) == "callback"


def test_relay_forwards_audio_to_other_leg():
    audio_b64 = base64.b64encode(b"\x01\x00\x02\x00").decode()
    src = FakeWebSocket(
        [json.dumps({"type": "audio", "audio_event": {"audio_base_64": audio_b64, "event_id": 1}})]
    )
    dst = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-1")

    asyncio.run(bridge.relay_loop(src, dst, "negotiator", sink))

    assert len(dst.sent) == 1
    assert json.loads(dst.sent[0]) == {"user_audio_chunk": audio_b64}


def test_relay_answers_ping_with_pong_on_same_leg():
    src = FakeWebSocket(
        [json.dumps({"type": "ping", "ping_event": {"event_id": 42, "ping_ms": 50}})]
    )
    dst = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-1")

    asyncio.run(bridge.relay_loop(src, dst, "negotiator", sink))

    assert len(src.sent) == 1
    assert json.loads(src.sent[0]) == {"type": "pong", "event_id": 42}
    assert dst.sent == []


def test_relay_buffers_pcm_for_mix():
    raw_pcm = b"\x01\x00\x02\x00"
    audio_b64 = base64.b64encode(raw_pcm).decode()
    src = FakeWebSocket(
        [json.dumps({"type": "audio", "audio_event": {"audio_base_64": audio_b64, "event_id": 1}})]
    )
    dst = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-1")

    asyncio.run(bridge.relay_loop(src, dst, "negotiator", sink))

    assert bytes(sink.pcm["negotiator"]) == raw_pcm


def test_relay_records_vad_scores_per_leg():
    src = FakeWebSocket(
        [
            json.dumps({"type": "vad_score", "vad_score_event": {"vad_score": 0.1}}),
            json.dumps({"type": "vad_score", "vad_score_event": {"vad_score": 0.9}}),
        ]
    )
    dst = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-1")

    asyncio.run(bridge.relay_loop(src, dst, "dealer", sink))

    assert sink.vad_scores["dealer"] == [0.1, 0.9]
    assert sink.vad_scores["negotiator"] == []
    assert dst.sent == []


def test_relay_records_agent_response_and_swaps_speaker_for_user_transcript():
    src = FakeWebSocket(
        [
            json.dumps(
                {"type": "agent_response", "agent_response_event": {"agent_response": "hi", "event_id": 1}}
            ),
            json.dumps(
                {
                    "type": "user_transcript",
                    "user_transcription_event": {"user_transcript": "hello back", "event_id": 2},
                }
            ),
        ]
    )
    dst = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-1")

    asyncio.run(bridge.relay_loop(src, dst, "negotiator", sink))

    assert sink.events == [
        ("negotiator", "agent_response", "hi"),
        ("dealer", "user_transcript", "hello back"),
    ]


class _FakeConnect:
    def __init__(self, ws):
        self.ws = ws

    async def __aenter__(self):
        return self.ws

    async def __aexit__(self, *exc):
        return False


class _BoomConnect:
    async def __aenter__(self):
        raise ConnectionError("boom")

    async def __aexit__(self, *exc):
        return False


class _HangingWebSocket(FakeWebSocket):
    async def __anext__(self):
        await asyncio.Event().wait()


def test_run_bridge_writes_terminal_outcome_on_normal_close(monkeypatch):
    neg_ws = FakeWebSocket(
        [
            json.dumps(
                {
                    "type": "agent_response",
                    "agent_response_event": {"agent_response": "hi, rent is 100000", "event_id": 1},
                }
            )
        ]
    )
    deal_ws = FakeWebSocket(
        [
            json.dumps(
                {
                    "type": "agent_response",
                    "agent_response_event": {"agent_response": "sure, 100000 works", "event_id": 1},
                }
            )
        ]
    )
    monkeypatch.setattr(
        bridge, "_connect", lambda agent_id: _FakeConnect(neg_ws if agent_id == "agent-neg" else deal_ws)
    )
    updates = []
    monkeypatch.setattr(bridge.crud, "update_call", lambda call_id, fields: updates.append((call_id, fields)))
    monkeypatch.setattr(bridge.storage, "upload_recording", lambda call_id, wav: f"{call_id}.wav")

    asyncio.run(
        bridge.run_bridge("call-1", "spec-1", "dealer-1", "agent-neg", "agent-deal", {"x": 1})
    )

    assert len(updates) == 1
    call_id, fields = updates[0]
    assert call_id == "call-1"
    assert fields["status"] == "completed"
    assert fields["outcome"] == "quote"
    assert fields["recording_url"] == "call-1.wav"
    assert fields["transcript_json"] == [
        {"line": 1, "speaker": "negotiator", "text": "hi, rent is 100000"},
        {"line": 2, "speaker": "dealer", "text": "sure, 100000 works"},
    ]


def test_run_bridge_writes_failed_on_exception(monkeypatch):
    monkeypatch.setattr(bridge, "_connect", lambda agent_id: _BoomConnect())
    updates = []
    monkeypatch.setattr(bridge.crud, "update_call", lambda call_id, fields: updates.append((call_id, fields)))
    monkeypatch.setattr(bridge.storage, "upload_recording", lambda call_id, wav: None)

    asyncio.run(bridge.run_bridge("call-2", "spec-1", "dealer-1", "agent-neg", "agent-deal", {}))

    assert len(updates) == 1
    call_id, fields = updates[0]
    assert call_id == "call-2"
    assert fields["status"] == "failed"
    assert fields["outcome"] == "failed"


def test_dealer_init_suppresses_first_message_with_a_space_not_empty_string():
    # Live-verified against the real ElevenLabs API: an empty-string first_message
    # override never closes the agent's own turn (it never starts listening for
    # user_audio_chunk afterward). A single space closes the turn normally.
    msg = json.loads(bridge._dealer_init())

    assert msg["conversation_config_override"]["agent"]["first_message"] == " "


def test_run_bridge_respects_max_duration(monkeypatch):
    monkeypatch.setattr(bridge, "MAX_CALL_SECONDS", 0.05)
    neg_ws = _HangingWebSocket()
    deal_ws = _HangingWebSocket()
    monkeypatch.setattr(
        bridge, "_connect", lambda agent_id: _FakeConnect(neg_ws if agent_id == "agent-neg" else deal_ws)
    )
    updates = []
    monkeypatch.setattr(bridge.crud, "update_call", lambda call_id, fields: updates.append((call_id, fields)))
    monkeypatch.setattr(bridge.storage, "upload_recording", lambda call_id, wav: None)

    asyncio.run(bridge.run_bridge("call-3", "spec-1", "dealer-1", "agent-neg", "agent-deal", {}))

    assert len(updates) == 1
    call_id, fields = updates[0]
    assert call_id == "call-3"
    assert fields["status"] == "completed"
    assert fields["outcome"] == "callback"
