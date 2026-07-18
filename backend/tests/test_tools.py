import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TOOL_PATHS = [
    "/tools/log_quote",
    "/tools/get_leverage",
    "/tools/check_redflag",
    "/tools/get_benchmark",
]

SECRET = "s3cret"


@pytest.fixture(autouse=True)
def tools_secret(monkeypatch):
    monkeypatch.setenv("TOOLS_WEBHOOK_SECRET", SECRET)


def _headers():
    return {"X-Tools-Secret": SECRET}


@pytest.mark.parametrize("path", TOOL_PATHS)
def test_missing_header_rejected(path):
    assert client.post(path, json={}).status_code == 401


@pytest.mark.parametrize("path", TOOL_PATHS)
def test_wrong_secret_rejected(path):
    assert client.post(path, json={}, headers={"X-Tools-Secret": "wrong"}).status_code == 401


@pytest.mark.parametrize("path", TOOL_PATHS)
def test_unset_server_secret_fails_closed(path, monkeypatch):
    monkeypatch.delenv("TOOLS_WEBHOOK_SECRET")
    assert client.post(path, json={}, headers={"X-Tools-Secret": ""}).status_code == 401
