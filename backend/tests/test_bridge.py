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


def _unpack_wav(wav_bytes: bytes) -> tuple[list[int], list[int]]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        assert w.getnchannels() == 2
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
        frames = w.readframes(w.getnframes())
    samples = struct.unpack(f"<{len(frames) // 2}h", frames)
    return list(samples[0::2]), list(samples[1::2])


def test_stereo_wav_puts_negotiator_left_dealer_right():
    neg = _pcm16(100, 200, 300)
    dealer = _pcm16(-1, -2, -3)

    left, right = _unpack_wav(bridge.stereo_wav(neg, dealer))

    assert left == [100, 200, 300]
    assert right == [-1, -2, -3]


def test_stereo_wav_pads_unequal_lengths_with_silence():
    neg = _pcm16(100, 200, 300)
    dealer = _pcm16(10)

    left, right = _unpack_wav(bridge.stereo_wav(neg, dealer))

    assert left == [100, 200, 300]
    assert right == [10, 0, 0]


def test_add_audio_pads_both_legs_on_turn_switch():
    sink = bridge.CallSink(call_id="call-1")
    sink.start = __import__("time").monotonic() + 100  # future: wall clock never pads in test

    sink.add_audio("negotiator", _pcm16(1, 2, 3))
    sink.add_audio("negotiator", _pcm16(4))  # same turn: contiguous
    sink.add_audio("dealer", _pcm16(9))  # turn switch: dealer starts after negotiator ends

    assert bytes(sink.pcm["negotiator"]) == _pcm16(1, 2, 3, 4)
    assert bytes(sink.pcm["dealer"]) == _pcm16(0, 0, 0, 0, 9)


def test_add_audio_turns_never_overlap_in_stereo_output():
    sink = bridge.CallSink(call_id="call-1")
    sink.start = __import__("time").monotonic() + 100

    sink.add_audio("negotiator", _pcm16(1, 1))
    sink.add_audio("dealer", _pcm16(2, 2))
    sink.add_audio("negotiator", _pcm16(3, 3))

    left, right = _unpack_wav(
        bridge.stereo_wav(bytes(sink.pcm["negotiator"]), bytes(sink.pcm["dealer"]))
    )
    # at every frame at most one leg is non-silent
    assert all(l == 0 or r == 0 for l, r in zip(left, right))
    assert left == [1, 1, 0, 0, 3, 3]
    assert right == [0, 0, 2, 2, 0, 0]


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


def test_derive_outcome_ignores_small_incidental_numbers():
    # "call me at 3pm" or "shop number 12" is not a quote
    transcript = [
        {"line": 1, "speaker": "dealer", "text": "Come to shop number 12, call me at 3pm."},
    ]

    assert bridge.derive_outcome(transcript) == "callback"


def test_derive_outcome_quote_with_comma_separated_amount():
    transcript = [
        {"line": 1, "speaker": "dealer", "text": "Rent is 85,000 per month."},
    ]

    assert bridge.derive_outcome(transcript) == "quote"


def test_derive_outcome_quote_with_spelled_out_thousand():
    transcript = [
        {"line": 1, "speaker": "dealer", "text": "The monthly rent is twenty thousand rupees."},
    ]
    assert bridge.derive_outcome(transcript) == "quote"


def test_derive_outcome_quote_with_spelled_out_lakh():
    transcript = [
        {"line": 1, "speaker": "dealer", "text": "It will cost one lakh fifty per month."},
    ]
    assert bridge.derive_outcome(transcript) == "quote"


def test_derive_outcome_ignores_plural_thousands_of():
    transcript = [
        {"line": 1, "speaker": "dealer", "text": "Thousands of customers pass by daily."},
    ]
    assert bridge.derive_outcome(transcript) == "callback"


def test_derive_outcome_ignores_lac_inside_other_words():
    transcript = [
        {"line": 1, "speaker": "dealer", "text": "This place is great, I will call you back."},
    ]
    assert bridge.derive_outcome(transcript) == "callback"


def test_derive_outcome_callback_when_transcript_empty():
    assert bridge.derive_outcome([]) == "callback"


def test_relay_enqueues_audio_for_turn_sender():
    audio_b64 = base64.b64encode(b"\x01\x00\x02\x00").decode()
    src = FakeWebSocket(
        [json.dumps({"type": "audio", "audio_event": {"audio_base_64": audio_b64, "event_id": 1}})]
    )
    sink = bridge.CallSink(call_id="call-1")

    async def scenario():
        queue = asyncio.Queue()
        await bridge.relay_loop(src, "negotiator", sink, queue)
        return queue.get_nowait(), queue.empty()

    chunk, _ = asyncio.run(scenario())
    assert chunk == audio_b64
    # nothing forwarded, recorded, or published until the turn sender takes it
    assert bytes(sink.pcm["negotiator"]) == b""
    assert sink.last_sent == {"negotiator": 0.0, "dealer": 0.0}


def test_relay_answers_ping_with_pong_on_same_leg():
    src = FakeWebSocket(
        [json.dumps({"type": "ping", "ping_event": {"event_id": 42, "ping_ms": 50}})]
    )
    sink = bridge.CallSink(call_id="call-1")

    async def scenario():
        await bridge.relay_loop(src, "negotiator", sink, asyncio.Queue())

    asyncio.run(scenario())

    assert len(src.sent) == 1
    assert json.loads(src.sent[0]) == {"type": "pong", "event_id": 42}


def test_relay_publishes_live_transcript_lines():
    from app import live

    src = FakeWebSocket(
        [
            json.dumps(
                {"type": "agent_response", "agent_response_event": {"agent_response": "hi", "event_id": 1}}
            )
        ]
    )
    sink = bridge.CallSink(call_id="call-pub-t")

    async def scenario():
        queue = live.subscribe("call-pub-t")
        try:
            await bridge.relay_loop(src, "negotiator", sink, asyncio.Queue())
            return queue.get_nowait()
        finally:
            live.unsubscribe("call-pub-t", queue)

    msg = asyncio.run(scenario())
    assert json.loads(msg) == {"leg": "negotiator", "text": "hi"}


def test_relay_records_vad_scores_per_leg():
    src = FakeWebSocket(
        [
            json.dumps({"type": "vad_score", "vad_score_event": {"vad_score": 0.1}}),
            json.dumps({"type": "vad_score", "vad_score_event": {"vad_score": 0.9}}),
        ]
    )
    sink = bridge.CallSink(call_id="call-1")

    async def scenario():
        await bridge.relay_loop(src, "dealer", sink, asyncio.Queue())

    asyncio.run(scenario())

    assert sink.vad_scores["dealer"] == [0.1, 0.9]
    assert sink.vad_scores["negotiator"] == []


def _run_sender_briefly(dst, leg, chunks, sink, gate, seconds):
    async def scenario():
        queue = asyncio.Queue()
        for chunk in chunks:
            queue.put_nowait(chunk)
        task = asyncio.ensure_future(bridge.turn_sender(dst, leg, queue, sink, gate))
        await asyncio.sleep(seconds)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())


def test_turn_sender_forwards_when_floor_is_free():
    audio_b64 = base64.b64encode(b"\x01\x00\x02\x00").decode()
    dst = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-1")
    sink.start = __import__("time").monotonic() + 100

    _run_sender_briefly(dst, "negotiator", [audio_b64], sink, bridge.TurnGate(), seconds=0.05)

    assert json.loads(dst.sent[0]) == {"user_audio_chunk": audio_b64}
    assert bytes(sink.pcm["negotiator"]) == b"\x01\x00\x02\x00"
    assert sink.last_sent["dealer"] > 0.0
    assert sink.last_sent["negotiator"] == 0.0


def test_turn_sender_publishes_leg_tagged_audio():
    from app import live

    audio_b64 = base64.b64encode(b"\x01\x00").decode()
    dst = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-pub")

    async def scenario():
        sub = live.subscribe("call-pub")
        try:
            queue = asyncio.Queue()
            queue.put_nowait(audio_b64)
            task = asyncio.ensure_future(
                bridge.turn_sender(dst, "dealer", queue, sink, bridge.TurnGate())
            )
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return sub.get_nowait()
        finally:
            live.unsubscribe("call-pub", sub)

    msg = asyncio.run(scenario())
    assert json.loads(msg) == {"leg": "dealer", "audio": audio_b64}


def test_turn_sender_holds_audio_while_other_leg_speaks(monkeypatch):
    monkeypatch.setattr(bridge, "TURN_GAP_SECONDS", 10)  # negotiator never yields
    audio_b64 = base64.b64encode(b"\x01\x00").decode()
    dst = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-1")
    gate = bridge.TurnGate()
    assert gate.try_acquire("negotiator")

    _run_sender_briefly(dst, "dealer", [audio_b64], sink, gate, seconds=0.2)

    assert dst.sent == []
    assert bytes(sink.pcm["dealer"]) == b""


def test_turn_sender_resumes_after_backoff_once_floor_frees(monkeypatch):
    import time as _time

    monkeypatch.setattr(bridge.random, "uniform", lambda lo, hi: 0.1)
    audio_b64 = base64.b64encode(b"\x01\x00").decode()

    class TimedWebSocket(FakeWebSocket):
        async def send(self, message):
            self.sent.append((message, _time.monotonic()))

    dst = TimedWebSocket()
    sink = bridge.CallSink(call_id="call-1")
    sink.start = _time.monotonic() + 100
    gate = bridge.TurnGate()
    assert gate.try_acquire("negotiator")

    async def scenario():
        queue = asyncio.Queue()
        queue.put_nowait(audio_b64)
        task = asyncio.ensure_future(bridge.turn_sender(dst, "dealer", queue, sink, gate))
        await asyncio.sleep(0.05)
        release_ts = _time.monotonic()
        gate.release("negotiator")
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return release_ts

    release_ts = asyncio.run(scenario())

    assert len(dst.sent) == 1
    message, sent_ts = dst.sent[0]
    assert json.loads(message) == {"user_audio_chunk": audio_b64}
    # interrupted leg waits its random backoff after the floor frees before speaking
    assert sent_ts - release_ts >= 0.09


def test_turn_senders_never_overlap_in_recording(monkeypatch):
    monkeypatch.setattr(bridge, "TURN_GAP_SECONDS", 0.05)
    monkeypatch.setattr(bridge.random, "uniform", lambda lo, hi: 0.02)
    neg_chunks = [base64.b64encode(_pcm16(1, 1)).decode()] * 2
    deal_chunks = [base64.b64encode(_pcm16(2, 2)).decode()] * 2
    sink = bridge.CallSink(call_id="call-1")
    sink.start = __import__("time").monotonic() + 100
    gate = bridge.TurnGate()

    async def scenario():
        neg_q, deal_q = asyncio.Queue(), asyncio.Queue()
        for c in neg_chunks:
            neg_q.put_nowait(c)
        for c in deal_chunks:
            deal_q.put_nowait(c)
        tasks = [
            asyncio.ensure_future(
                bridge.turn_sender(FakeWebSocket(), "negotiator", neg_q, sink, gate)
            ),
            asyncio.ensure_future(bridge.turn_sender(FakeWebSocket(), "dealer", deal_q, sink, gate)),
        ]
        await asyncio.sleep(0.5)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(scenario())

    left, right = _unpack_wav(
        bridge.stereo_wav(bytes(sink.pcm["negotiator"]), bytes(sink.pcm["dealer"]))
    )
    assert sum(left) == 4  # both legs got all their audio out
    assert sum(right) == 8
    # at every frame at most one leg is speaking
    assert all(l == 0 or r == 0 for l, r in zip(left, right))


def test_turn_sender_stops_when_socket_closes():
    import websockets

    class ClosedWebSocket(FakeWebSocket):
        async def send(self, message):
            raise websockets.exceptions.ConnectionClosedOK(None, None)

    sink = bridge.CallSink(call_id="call-1")

    async def scenario():
        queue = asyncio.Queue()
        queue.put_nowait(base64.b64encode(b"\x01\x00").decode())
        await asyncio.wait_for(
            bridge.turn_sender(ClosedWebSocket(), "dealer", queue, sink, bridge.TurnGate()),
            timeout=2,
        )

    asyncio.run(scenario())  # returns instead of raising


def _run_feeder_briefly(ws, leg, sink, seconds):
    async def scenario():
        task = asyncio.ensure_future(bridge.silence_feeder(ws, leg, sink))
        await asyncio.sleep(seconds)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())


def test_silence_feeder_streams_silence_when_leg_is_idle():
    ws = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-1")

    _run_feeder_briefly(ws, "dealer", sink, seconds=0.6)

    assert len(ws.sent) >= 2
    chunk = json.loads(ws.sent[0])["user_audio_chunk"]
    assert base64.b64decode(chunk) == b"\x00" * len(base64.b64decode(chunk))
    # silence is filler for the server's turn detector, not call audio
    assert bytes(sink.pcm["dealer"]) == b""
    assert bytes(sink.pcm["negotiator"]) == b""


def test_silence_feeder_pauses_while_real_audio_flows():
    import time as _time

    ws = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-1")

    async def scenario():
        task = asyncio.ensure_future(bridge.silence_feeder(ws, "dealer", sink))
        for _ in range(6):
            sink.last_sent["dealer"] = _time.monotonic()
            await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())

    assert ws.sent == []


def test_silence_feeder_does_not_reset_silence_watchdog():
    ws = FakeWebSocket()
    sink = bridge.CallSink(call_id="call-1")
    before = sink.last_audio_ts

    _run_feeder_briefly(ws, "dealer", sink, seconds=0.4)

    assert sink.last_audio_ts == before


def test_silence_feeder_stops_when_socket_closes():
    import websockets

    class ClosedWebSocket(FakeWebSocket):
        async def send(self, message):
            raise websockets.exceptions.ConnectionClosedOK(None, None)

    ws = ClosedWebSocket()
    sink = bridge.CallSink(call_id="call-1")

    async def scenario():
        await asyncio.wait_for(bridge.silence_feeder(ws, "dealer", sink), timeout=2)

    asyncio.run(scenario())  # returns instead of raising


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
    sink = bridge.CallSink(call_id="call-1")

    async def scenario():
        await bridge.relay_loop(src, "negotiator", sink, asyncio.Queue())

    asyncio.run(scenario())

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


def test_request_stop_returns_false_when_no_active_bridge():
    assert bridge.request_stop("no-such-call") is False


def test_run_bridge_stops_early_and_finalizes_on_request_stop(monkeypatch):
    neg_ws = _HangingWebSocket()
    deal_ws = _HangingWebSocket()
    monkeypatch.setattr(
        bridge, "_connect", lambda agent_id: _FakeConnect(neg_ws if agent_id == "agent-neg" else deal_ws)
    )
    updates = []
    monkeypatch.setattr(bridge.crud, "update_call", lambda call_id, fields: updates.append((call_id, fields)))
    monkeypatch.setattr(bridge.storage, "upload_recording", lambda call_id, wav: f"{call_id}.wav")

    async def scenario():
        task = asyncio.ensure_future(
            bridge.run_bridge("call-stop", "spec-1", "dealer-1", "agent-neg", "agent-deal", {})
        )
        await asyncio.sleep(0.05)
        assert bridge.request_stop("call-stop") is True
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(scenario())

    assert len(updates) == 1
    call_id, fields = updates[0]
    assert call_id == "call-stop"
    assert fields["status"] == "completed"
    assert fields["outcome"] == "callback"
    # stop event deregistered once the call is over
    assert bridge.request_stop("call-stop") is False


def test_negotiator_init_suppresses_first_message_with_a_space_not_empty_string():
    # Dealer answers the phone first. Live-verified against the real ElevenLabs API:
    # an empty-string first_message override never closes the agent's own turn (it
    # never starts listening for user_audio_chunk afterward). A single space closes
    # the turn normally.
    msg = json.loads(bridge._negotiator_init({"x": 1}))

    assert msg["conversation_config_override"]["agent"]["first_message"] == " "
    assert msg["dynamic_variables"] == {"x": 1}


def test_dealer_init_keeps_factory_first_message():
    msg = json.loads(bridge._dealer_init())

    assert "conversation_config_override" not in msg


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
