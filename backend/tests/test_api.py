import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from app import api, crud
from app.auth import get_current_user_id
from app.main import app

client = TestClient(app)

USER_A = "user-a"
USER_B = "user-b"


def _as(user_id):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def teardown_function():
    app.dependency_overrides.clear()


def test_health_does_not_require_auth():
    response = client.get("/health")
    assert response.status_code == 200


def test_specs_endpoints_require_auth():
    response = client.get("/specs")
    assert response.status_code == 401  # no dependency override, no header


def test_create_spec_sets_owner_from_token(monkeypatch):
    captured = {}

    def fake_create_spec(row):
        captured.update(row)
        return {"id": "s1", **row}

    monkeypatch.setattr(crud, "create_spec", fake_create_spec)
    monkeypatch.setattr(crud, "create_dealer", lambda row: {"id": "d", **row})
    _as(USER_A)

    response = client.post(
        "/specs",
        json={"vertical": "shop_rental", "status": "draft", "spec_json": {}},
    )

    assert response.status_code == 200
    assert captured["user_id"] == USER_A


def test_create_spec_seeds_one_dealer_per_persona(monkeypatch):
    seeded = []

    monkeypatch.setattr(crud, "create_spec", lambda row: {"id": "s1", **row})

    def fake_create_dealer(row):
        seeded.append(row)
        return {"id": f"d{len(seeded)}", **row}

    monkeypatch.setattr(crud, "create_dealer", fake_create_dealer)
    _as(USER_A)

    response = client.post(
        "/specs",
        json={"vertical": "shop_rental", "status": "confirmed", "spec_json": {}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dealers_seeded"] == len(seeded) > 0
    personas = [d["persona"] for d in seeded]
    assert len(set(personas)) == len(personas)
    assert all(d["spec_id"] == "s1" for d in seeded)


def test_list_specs_scoped_to_caller(monkeypatch):
    captured = {}

    def fake_list_specs(**filters):
        captured.update(filters)
        return []

    monkeypatch.setattr(crud, "list_specs", fake_list_specs)
    _as(USER_A)

    client.get("/specs")

    assert captured == {"user_id": USER_A}


def test_get_spec_404s_for_non_owner(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.get("/specs/s1")

    assert response.status_code == 404


def test_get_spec_200s_for_owner(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_A)

    response = client.get("/specs/s1")

    assert response.status_code == 200
    assert response.json()["id"] == "s1"


def test_create_dealer_requires_spec_ownership(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.post(
        "/dealers", json={"spec_id": "s1", "name": "D", "persona": "firm"}
    )

    assert response.status_code == 404


def test_list_dealers_requires_spec_id_query_param(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_A)

    response = client.get("/dealers")  # no spec_id

    assert response.status_code == 422


def test_list_dealers_scoped_to_owned_spec(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    monkeypatch.setattr(crud, "list_dealers", lambda **filters: [{"id": "d1"}])
    _as(USER_A)

    response = client.get("/dealers", params={"spec_id": "s1"})

    assert response.status_code == 200
    assert response.json() == [{"id": "d1"}]


def test_get_dealer_404s_for_non_owner(monkeypatch):
    monkeypatch.setattr(
        crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1"}
    )
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.get("/dealers/d1")

    assert response.status_code == 404


def test_get_dealer_200s_for_owner(monkeypatch):
    monkeypatch.setattr(
        crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1"}
    )
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_A)

    response = client.get("/dealers/d1")

    assert response.status_code == 200
    assert response.json()["id"] == "d1"


def test_list_dealers_404s_for_non_owned_spec(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.get("/dealers", params={"spec_id": "s1"})

    assert response.status_code == 404


def test_create_call_requires_spec_ownership(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.post(
        "/calls",
        json={"spec_id": "s1", "dealer_id": "d1", "round": 1, "status": "pending"},
    )

    assert response.status_code == 404


def test_get_call_404s_for_non_owner(monkeypatch):
    monkeypatch.setattr(
        crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"}
    )
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.get("/calls/c1")

    assert response.status_code == 404


def test_get_call_200s_for_owner(monkeypatch):
    monkeypatch.setattr(
        crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"}
    )
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_A)

    response = client.get("/calls/c1")

    assert response.status_code == 200
    assert response.json()["id"] == "c1"


def test_list_calls_requires_spec_id_query_param(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_A)

    response = client.get("/calls")  # no spec_id

    assert response.status_code == 422


def test_list_calls_404s_for_non_owned_spec(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.get("/calls", params={"spec_id": "s1"})

    assert response.status_code == 404


def test_list_calls_scoped_to_owned_spec(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    monkeypatch.setattr(crud, "list_calls", lambda **filters: [{"id": "c1"}])
    _as(USER_A)

    response = client.get("/calls", params={"spec_id": "s1"})

    assert response.status_code == 200
    assert response.json() == [{"id": "c1"}]


def test_create_quote_requires_call_ownership(monkeypatch):
    monkeypatch.setattr(
        crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"}
    )
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.post(
        "/quotes",
        json={
            "call_id": "c1",
            "dealer_id": "d1",
            "monthly_rent": 1000,
            "total_first_year": 12000,
        },
    )

    assert response.status_code == 404


def test_get_quote_checks_ownership_through_call_and_spec(monkeypatch):
    monkeypatch.setattr(
        crud, "get_quote", lambda id: {"id": "q1", "call_id": "c1"}
    )
    monkeypatch.setattr(
        crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"}
    )
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.get("/quotes/q1")

    assert response.status_code == 404


def test_list_quotes_requires_call_id_query_param(monkeypatch):
    monkeypatch.setattr(
        crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"}
    )
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_A)

    response = client.get("/quotes")  # no call_id

    assert response.status_code == 422


def test_list_quotes_404s_for_non_owned_call(monkeypatch):
    monkeypatch.setattr(
        crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"}
    )
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.get("/quotes", params={"call_id": "c1"})

    assert response.status_code == 404


def test_list_quotes_scoped_to_owned_call(monkeypatch):
    monkeypatch.setattr(
        crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"}
    )
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    monkeypatch.setattr(crud, "list_quotes", lambda **filters: [{"id": "q1"}])
    _as(USER_A)

    response = client.get("/quotes", params={"call_id": "c1"})

    assert response.status_code == 200
    assert response.json() == [{"id": "q1"}]


def _fake_create_task_recording(spawned):
    def fake(coro):
        coro.close()
        spawned.append(coro)
        return None

    return fake


def test_start_call_creates_row_and_spawns_bridge_task(monkeypatch):
    monkeypatch.setattr(
        crud,
        "get_spec",
        lambda id: {"id": "s1", "user_id": USER_A, "spec_json": {"area_sqft": 500}},
    )
    monkeypatch.setattr(
        crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1", "persona": "firm"}
    )
    monkeypatch.setattr(crud, "create_call", lambda row: {"id": "call-1", **row})
    spawned = []
    monkeypatch.setattr(api.asyncio, "create_task", _fake_create_task_recording(spawned))
    _as(USER_A)

    response = client.post("/calls/start", json={"spec_id": "s1", "dealer_id": "d1"})

    assert response.status_code == 200
    assert response.json() == {"call_id": "call-1", "status": "running"}
    assert len(spawned) == 1


def test_start_call_bridge_mode_actually_schedules_a_real_asyncio_task(monkeypatch):
    # Regression: start_call must run on the event loop (async def), not in FastAPI's
    # worker threadpool, or the real asyncio.create_task() call has no running loop.
    monkeypatch.setattr(
        crud,
        "get_spec",
        lambda id: {"id": "s1", "user_id": USER_A, "spec_json": {"area_sqft": 500}},
    )
    monkeypatch.setattr(
        crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1", "persona": "firm"}
    )
    monkeypatch.setattr(crud, "create_call", lambda row: {"id": "call-real", **row})

    called = []

    async def fake_run_bridge(*args, **kwargs):
        called.append(args)

    monkeypatch.setattr(api, "run_bridge", fake_run_bridge)
    _as(USER_A)

    response = client.post("/calls/start", json={"spec_id": "s1", "dealer_id": "d1"})

    assert response.status_code == 200
    assert response.json() == {"call_id": "call-real", "status": "running"}


def test_start_call_404_for_non_owner(monkeypatch):
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    _as(USER_B)

    response = client.post("/calls/start", json={"spec_id": "s1", "dealer_id": "d1"})

    assert response.status_code == 404


def test_start_call_roleplay_returns_agent_and_dynamic_variables_with_no_bid_data(monkeypatch):
    monkeypatch.setattr(
        crud,
        "get_spec",
        lambda id: {"id": "s1", "user_id": USER_A, "spec_json": {"area_sqft": 500}},
    )
    monkeypatch.setattr(
        crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1", "persona": "firm"}
    )
    monkeypatch.setattr(crud, "create_call", lambda row: {"id": "call-2", **row})
    spawned = []
    monkeypatch.setattr(api.asyncio, "create_task", _fake_create_task_recording(spawned))
    _as(USER_A)

    response = client.post(
        "/calls/start", json={"spec_id": "s1", "dealer_id": "d1", "mode": "roleplay"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["call_id"] == "call-2"
    assert "negotiator_agent_id" in body
    dyn = body["dynamic_variables"]
    assert dyn["call_id"] == "call-2"
    assert dyn["dealer_id"] == "d1"
    assert dyn["spec_id"] == "s1"
    assert "bid" not in json.dumps(dyn).lower()
    assert spawned == []


WEBHOOK_SECRET = "test-webhook-secret"

POSTCALL_EVENT = {
    "type": "post_call_transcription",
    "data": {
        "conversation_initiation_client_data": {
            "dynamic_variables": {"call_id": "c1"}
        },
        "transcript": [
            {"role": "agent", "message": "What is the rent?"},
            {"role": "user", "message": "Rent is 150000 monthly."},
            {"role": "user", "message": None},
        ],
    },
}


def _signed_headers(body: str, secret: str = WEBHOOK_SECRET) -> dict:
    t = str(int(time.time()))
    v0 = hmac.new(secret.encode(), f"{t}.{body}".encode(), hashlib.sha256).hexdigest()
    return {"elevenlabs-signature": f"t={t},v0={v0}"}


def test_post_call_webhook_valid_signature_writes_call(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", WEBHOOK_SECRET)
    updates = []

    def fake_update_call(id, fields):
        updates.append((id, fields))
        return {"id": id, **fields}

    monkeypatch.setattr(crud, "update_call", fake_update_call)

    body = json.dumps(POSTCALL_EVENT)
    response = client.post(
        "/webhooks/post-call", content=body, headers=_signed_headers(body)
    )

    assert response.status_code == 200
    assert len(updates) == 1
    call_id, fields = updates[0]
    assert call_id == "c1"
    assert fields["status"] == "completed"
    assert fields["transcript_json"] == [
        {"line": 1, "speaker": "negotiator", "text": "What is the rent?"},
        {"line": 2, "speaker": "dealer", "text": "Rent is 150000 monthly."},
    ]
    assert fields["outcome"] == "quote"


def test_post_call_webhook_bad_signature_401(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr(
        crud, "update_call", lambda id, fields: (_ for _ in ()).throw(AssertionError)
    )

    body = json.dumps(POSTCALL_EVENT)
    response = client.post(
        "/webhooks/post-call",
        content=body,
        headers=_signed_headers(body, secret="wrong-secret"),
    )

    assert response.status_code == 401


def test_post_call_webhook_fails_closed_without_secret_env(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_WEBHOOK_SECRET", raising=False)

    body = json.dumps(POSTCALL_EVENT)
    response = client.post(
        "/webhooks/post-call", content=body, headers=_signed_headers(body)
    )

    assert response.status_code == 401


def test_post_call_webhook_acks_events_without_call_id(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", WEBHOOK_SECRET)
    updates = []
    monkeypatch.setattr(
        crud, "update_call", lambda id, fields: updates.append(id)
    )

    body = json.dumps({"type": "post_call_transcription", "data": {"transcript": []}})
    response = client.post(
        "/webhooks/post-call", content=body, headers=_signed_headers(body)
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert updates == []


def test_recording_endpoint_owner_only(monkeypatch):
    monkeypatch.setattr(
        crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1", "recording_url": "c1.wav"}
    )
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    _as(USER_B)

    response = client.get("/calls/c1/recording")
    assert response.status_code == 404

    _as(USER_A)
    monkeypatch.setattr(
        api.storage, "signed_recording_url", lambda path, expires_s=3600: f"https://signed/{path}"
    )

    response = client.get("/calls/c1/recording")
    assert response.status_code == 200
    assert response.json() == {"recording_url": "https://signed/c1.wav"}
