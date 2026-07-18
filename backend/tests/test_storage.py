from app import storage


class FakeBucketApi:
    def __init__(self):
        self.uploaded = []
        self.signed = []

    def upload(self, path, file, file_options=None):
        self.uploaded.append((path, file, file_options))
        return {"path": path}

    def create_signed_url(self, path, expires_in):
        self.signed.append((path, expires_in))
        return {"signedURL": f"https://signed/{path}?exp={expires_in}"}


class FakeStorage:
    def __init__(self, bucket_api):
        self.bucket_api = bucket_api

    def from_(self, bucket):
        assert bucket == "recordings"
        return self.bucket_api


class FakeClient:
    def __init__(self, bucket_api):
        self.storage = FakeStorage(bucket_api)


def test_upload_recording_writes_to_recordings_bucket_and_returns_path(monkeypatch):
    bucket_api = FakeBucketApi()
    monkeypatch.setattr(storage, "get_client", lambda: FakeClient(bucket_api))

    path = storage.upload_recording("call-1", b"RIFF....")

    assert path == "call-1.wav"
    assert bucket_api.uploaded[0][0] == "call-1.wav"
    assert bucket_api.uploaded[0][1] == b"RIFF...."


def test_signed_recording_url_mints_url_for_path(monkeypatch):
    bucket_api = FakeBucketApi()
    monkeypatch.setattr(storage, "get_client", lambda: FakeClient(bucket_api))

    url = storage.signed_recording_url("call-1.wav", expires_s=120)

    assert url == "https://signed/call-1.wav?exp=120"
    assert bucket_api.signed[0] == ("call-1.wav", 120)
