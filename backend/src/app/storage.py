from .db import get_client

RECORDINGS_BUCKET = "recordings"


def upload_recording(call_id: str, wav_bytes: bytes) -> str:
    path = f"{call_id}.wav"
    get_client().storage.from_(RECORDINGS_BUCKET).upload(
        path, wav_bytes, file_options={"content-type": "audio/wav", "upsert": "true"}
    )
    return path


def signed_recording_url(path: str, expires_s: int = 3600) -> str:
    resp = get_client().storage.from_(RECORDINGS_BUCKET).create_signed_url(path, expires_s)
    return resp["signedURL"]
