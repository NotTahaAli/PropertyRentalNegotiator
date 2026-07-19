import asyncio
import base64
import io
import json
import random
import re
import time
import wave
from datetime import datetime, timezone

import websockets

from . import crud, live, storage

EL_WS_URL = "wss://api.elevenlabs.io/v1/convai/conversation?agent_id={agent_id}"

# No per-conversation audio-format override exists in the ElevenLabs API (verified
# against elevenlabs.types) — both legs are pinned to this at agent level instead,
# see make_agents.py's AUDIO_FORMAT.
AUDIO_FORMAT = "pcm_16000"
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # bytes per 16-bit PCM sample

MAX_CALL_SECONDS = 180
SILENCE_SECONDS = 15

# Half-duplex turn-taking: a leg holds the floor while its TTS chunks keep
# arriving, and releases it after this gap with no new chunk (TTS arrives in
# faster-than-realtime bursts, so intra-utterance gaps are tiny). A leg that
# tried to speak while the other held the floor waits a random human-ish
# backoff after the floor frees, then re-checks it's still free before talking.
TURN_GAP_SECONDS = 0.6
BACKOFF_RANGE_SECONDS = (0.25, 0.5)

# ElevenLabs' server-side turn detection only commits a user turn after it hears
# silence *audio* following speech — a relay that forwards TTS bursts and then
# goes quiet never ends the turn, so the receiving agent never replies
# (live-verified: burst-only got no vad_score/user_transcript at all; the same
# burst followed by streamed silence chunks got a transcript and a reply).
# Feed each leg continuous silence whenever no real audio is being relayed to it,
# like an open microphone would.
SILENCE_CHUNK_SECONDS = 0.25
_SILENCE_CHUNK_B64 = base64.b64encode(
    b"\x00" * int(SAMPLE_RATE * SAMPLE_WIDTH * SILENCE_CHUNK_SECONDS)
).decode()

# ponytail: 4+ digit number (commas stripped) or a singular money scale word
# = money in PKR. Singular only: "thousands of customers" is not a quote.
# Webhook/quotes table is the ground truth anyway.
_QUOTE_NUMBER_RE = re.compile(r"\d{4,}|\b(?:thousand|lakh|lac|crore|million)\b")
_DECLINE_PHRASES = ("not interested", "no deal", "not available", "already rented")
_CALLBACK_PHRASES = ("call you back", "call back", "callback")


def stereo_wav(neg: bytes, dealer: bytes) -> bytes:
    length = max(len(neg), len(dealer))
    length += length % SAMPLE_WIDTH
    neg = neg.ljust(length, b"\x00")
    dealer = dealer.ljust(length, b"\x00")

    frames = bytearray(length * 2)
    frames[0::4] = neg[0::2]
    frames[1::4] = neg[1::2]
    frames[2::4] = dealer[0::2]
    frames[3::4] = dealer[1::2]

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)  # left = negotiator, right = dealer
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def accumulate_transcript(events: list[tuple[str, str, str]]) -> list[dict]:
    transcript: list[dict] = []
    has_agent_response: set[str] = set()
    for speaker, source, text in events:
        if source == "user_transcript" and speaker in has_agent_response:
            continue
        if source == "agent_response":
            has_agent_response.add(speaker)
        transcript.append({"line": len(transcript) + 1, "speaker": speaker, "text": text})
    return transcript


def _other(leg: str) -> str:
    return "dealer" if leg == "negotiator" else "negotiator"


# ponytail: single-process registry, same constraint as live._subscribers —
# one free-tier Render worker, the bridge task and the /end request share it.
_stop_events: dict[str, asyncio.Event] = {}


def request_stop(call_id: str) -> bool:
    """Ask a running bridge to hang up early. False if no such bridge."""
    event = _stop_events.get(call_id)
    if event is None:
        return False
    event.set()
    return True


class CallSink:
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.pcm: dict[str, bytearray] = {"negotiator": bytearray(), "dealer": bytearray()}
        self.events: list[tuple[str, str, str]] = []
        # K5 diagnostic: server-side VAD score of the audio *sent to* each leg.
        # Dealer-leg peak ~0 would confirm the relayed-audio/VAD theory (TODO.md).
        self.vad_scores: dict[str, list[float]] = {"negotiator": [], "dealer": []}
        self.last_audio_ts = time.monotonic()
        # monotonic ts of the last real audio chunk relayed *to* each leg;
        # silence_feeder pauses while fresher than SILENCE_CHUNK_SECONDS
        self.last_sent: dict[str, float] = {"negotiator": 0.0, "dealer": 0.0}
        # time alignment for the stereo recording: on each turn switch both leg
        # buffers are padded to a shared cursor so turns replay sequentially
        self.start = time.monotonic()
        self.last_leg: str | None = None

    def add_audio(self, leg: str, chunk: bytes) -> None:
        if leg != self.last_leg:
            # TTS bursts arrive faster than real time, so the shared cursor is
            # whichever is furthest along: either leg's audio, or the wall clock
            # (which captures thinking gaps between turns)
            elapsed = int((time.monotonic() - self.start) * SAMPLE_RATE) * SAMPLE_WIDTH
            target = max(len(self.pcm["negotiator"]), len(self.pcm["dealer"]), elapsed)
            for buf in self.pcm.values():
                buf.extend(b"\x00" * (target - len(buf)))
            self.last_leg = leg
        self.pcm[leg] += chunk


class TurnGate:
    def __init__(self):
        self.speaker: str | None = None
        self._free = asyncio.Event()
        self._free.set()

    def try_acquire(self, leg: str) -> bool:
        if self.speaker in (None, leg):
            self.speaker = leg
            self._free.clear()
            return True
        return False

    def release(self, leg: str) -> None:
        if self.speaker == leg:
            self.speaker = None
            self._free.set()

    async def wait_free(self) -> None:
        await self._free.wait()


async def turn_sender(dst_ws, leg: str, queue: asyncio.Queue, sink: CallSink, gate: TurnGate) -> None:
    """Drain one leg's TTS chunks to the other leg, one speaker at a time.

    Chunks produced while the other leg holds the floor are held in the queue
    (never dropped — the receiving agent's ASR must still hear the whole
    utterance) and replayed once the floor frees plus a random backoff.
    """
    while True:
        if gate.speaker == leg:
            try:
                audio_b64 = await asyncio.wait_for(queue.get(), timeout=TURN_GAP_SECONDS)
            except asyncio.TimeoutError:
                gate.release(leg)
                continue
        else:
            audio_b64 = await queue.get()
            while not gate.try_acquire(leg):
                await gate.wait_free()
                await asyncio.sleep(random.uniform(*BACKOFF_RANGE_SECONDS))
        try:
            await dst_ws.send(json.dumps({"user_audio_chunk": audio_b64}))
        except websockets.exceptions.ConnectionClosed:
            return
        sink.add_audio(leg, base64.b64decode(audio_b64))
        sink.last_audio_ts = time.monotonic()
        sink.last_sent[_other(leg)] = sink.last_audio_ts
        live.publish(sink.call_id, json.dumps({"leg": leg, "audio": audio_b64}))


async def relay_loop(src_ws, leg: str, sink: CallSink, queue: asyncio.Queue) -> None:
    async for raw in src_ws:
        msg = json.loads(raw)
        msg_type = msg.get("type")

        if msg_type == "audio":
            queue.put_nowait(msg["audio_event"]["audio_base_64"])

        elif msg_type == "agent_response":
            text = msg["agent_response_event"]["agent_response"]
            sink.events.append((leg, "agent_response", text))

        elif msg_type == "user_transcript":
            text = msg["user_transcription_event"]["user_transcript"]
            sink.events.append((_other(leg), "user_transcript", text))

        elif msg_type == "vad_score":
            sink.vad_scores[leg].append(msg["vad_score_event"]["vad_score"])

        elif msg_type == "ping":
            event_id = msg["ping_event"]["event_id"]
            await src_ws.send(json.dumps({"type": "pong", "event_id": event_id}))


def derive_outcome(transcript: list[dict]) -> str:
    dealer_lines = [
        e["text"].lower().replace(",", "") for e in transcript if e["speaker"] == "dealer"
    ]
    if any(_QUOTE_NUMBER_RE.search(line) for line in dealer_lines):
        return "quote"
    if any(phrase in line for line in dealer_lines for phrase in _DECLINE_PHRASES):
        return "declined"
    return "callback"


def _connect(agent_id: str):
    return websockets.connect(EL_WS_URL.format(agent_id=agent_id))


def _negotiator_init(dynamic_variables: dict) -> str:
    return json.dumps(
        {"type": "conversation_initiation_client_data", "dynamic_variables": dynamic_variables}
    )


def _dealer_init() -> str:
    return json.dumps(
        {
            "type": "conversation_initiation_client_data",
            "dynamic_variables": {},
            # Negotiator opens; dealer's factory first_message is suppressed for this call
            # only. Must be a single space, not "": an empty string never closes the
            # agent's own turn (live-verified — it then never starts listening for
            # user_audio_chunk, leaving the connection silent apart from pings).
            "conversation_config_override": {"agent": {"first_message": " "}},
        }
    )


async def silence_feeder(dst_ws, dst_leg: str, sink: CallSink) -> None:
    while True:
        await asyncio.sleep(SILENCE_CHUNK_SECONDS)
        if time.monotonic() - sink.last_sent[dst_leg] < SILENCE_CHUNK_SECONDS:
            continue
        try:
            await dst_ws.send(json.dumps({"user_audio_chunk": _SILENCE_CHUNK_B64}))
        except websockets.exceptions.ConnectionClosed:
            return


async def _silence_watchdog(sink: CallSink) -> None:
    while True:
        await asyncio.sleep(1)
        if time.monotonic() - sink.last_audio_ts > SILENCE_SECONDS:
            return


async def run_bridge(
    call_id: str,
    spec_id: str,
    dealer_id: str,
    negotiator_agent_id: str,
    dealer_agent_id: str,
    dynamic_vars: dict,
) -> None:
    sink = CallSink(call_id)
    stop_event = _stop_events[call_id] = asyncio.Event()
    failed = False
    try:
        async with _connect(negotiator_agent_id) as neg_ws, _connect(dealer_agent_id) as deal_ws:
            await neg_ws.send(_negotiator_init(dynamic_vars))
            await deal_ws.send(_dealer_init())

            gate = TurnGate()
            neg_queue: asyncio.Queue = asyncio.Queue()
            deal_queue: asyncio.Queue = asyncio.Queue()
            tasks = {
                asyncio.ensure_future(relay_loop(neg_ws, "negotiator", sink, neg_queue)),
                asyncio.ensure_future(relay_loop(deal_ws, "dealer", sink, deal_queue)),
                asyncio.ensure_future(turn_sender(deal_ws, "negotiator", neg_queue, sink, gate)),
                asyncio.ensure_future(turn_sender(neg_ws, "dealer", deal_queue, sink, gate)),
                asyncio.ensure_future(silence_feeder(deal_ws, "dealer", sink)),
                asyncio.ensure_future(silence_feeder(neg_ws, "negotiator", sink)),
                asyncio.ensure_future(_silence_watchdog(sink)),
                # user hit "End call": first completed task wins, normal finalize
                asyncio.ensure_future(stop_event.wait()),
            }
            done, pending = await asyncio.wait(
                tasks, timeout=MAX_CALL_SECONDS, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                exc = task.exception()
                if exc is not None:
                    raise exc
    except Exception:
        failed = True
    finally:
        _stop_events.pop(call_id, None)
        peaks = {leg: max(scores, default=0.0) for leg, scores in sink.vad_scores.items()}
        print(f"call {call_id} vad peaks: {peaks}")
        wav_bytes = stereo_wav(bytes(sink.pcm["negotiator"]), bytes(sink.pcm["dealer"]))
        recording_url = None
        try:
            recording_url = storage.upload_recording(call_id, wav_bytes)
        except Exception:
            pass
        transcript = accumulate_transcript(sink.events)
        if failed:
            status, outcome = "failed", "failed"
        else:
            status, outcome = "completed", derive_outcome(transcript)
        crud.update_call(
            call_id,
            {
                "status": status,
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "recording_url": recording_url,
                "transcript_json": transcript,
                "outcome": outcome,
            },
        )
