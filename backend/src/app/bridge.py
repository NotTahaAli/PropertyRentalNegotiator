import asyncio
import base64
import io
import json
import re
import struct
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

# ponytail: 4+ digit number (commas stripped) = money in PKR; misses spelled-out
# amounts ("eighty five thousand") — webhook/quotes table is the ground truth anyway.
_QUOTE_NUMBER_RE = re.compile(r"\d{4,}")
_DECLINE_PHRASES = ("not interested", "no deal", "not available", "already rented")
_CALLBACK_PHRASES = ("call you back", "call back", "callback")


def mix_pcm(neg: bytes, dealer: bytes) -> bytes:
    length = max(len(neg), len(dealer))
    length += length % 2
    neg = neg.ljust(length, b"\x00")
    dealer = dealer.ljust(length, b"\x00")

    sample_count = length // 2
    neg_samples = struct.unpack(f"<{sample_count}h", neg)
    dealer_samples = struct.unpack(f"<{sample_count}h", dealer)

    mixed = bytearray()
    for a, b in zip(neg_samples, dealer_samples):
        mixed += struct.pack("<h", max(-32768, min(32767, a + b)))

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(mixed))
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


class CallSink:
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.pcm: dict[str, bytearray] = {"negotiator": bytearray(), "dealer": bytearray()}
        self.events: list[tuple[str, str, str]] = []
        # K5 diagnostic: server-side VAD score of the audio *sent to* each leg.
        # Dealer-leg peak ~0 would confirm the relayed-audio/VAD theory (TODO.md).
        self.vad_scores: dict[str, list[float]] = {"negotiator": [], "dealer": []}
        self.last_audio_ts = time.monotonic()


async def relay_loop(src_ws, dst_ws, leg: str, sink: CallSink) -> None:
    async for raw in src_ws:
        msg = json.loads(raw)
        msg_type = msg.get("type")

        if msg_type == "audio":
            audio_b64 = msg["audio_event"]["audio_base_64"]
            await dst_ws.send(json.dumps({"user_audio_chunk": audio_b64}))
            sink.pcm[leg] += base64.b64decode(audio_b64)
            sink.last_audio_ts = time.monotonic()
            live.publish(sink.call_id, audio_b64)

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
    failed = False
    try:
        async with _connect(negotiator_agent_id) as neg_ws, _connect(dealer_agent_id) as deal_ws:
            await neg_ws.send(_negotiator_init(dynamic_vars))
            await deal_ws.send(_dealer_init())

            tasks = {
                asyncio.ensure_future(relay_loop(neg_ws, deal_ws, "negotiator", sink)),
                asyncio.ensure_future(relay_loop(deal_ws, neg_ws, "dealer", sink)),
                asyncio.ensure_future(_silence_watchdog(sink)),
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
        peaks = {leg: max(scores, default=0.0) for leg, scores in sink.vad_scores.items()}
        print(f"call {call_id} vad peaks: {peaks}")
        wav_bytes = mix_pcm(bytes(sink.pcm["negotiator"]), bytes(sink.pcm["dealer"]))
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
