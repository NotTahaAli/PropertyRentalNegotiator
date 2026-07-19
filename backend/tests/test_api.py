import hashlib
import hmac
import json
import time

import pytest
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


class _FakeTask:
    def add_done_callback(self, cb):
        pass


def _fake_create_task_recording(spawned):
    def fake(coro):
        coro.close()
        spawned.append(coro)
        return _FakeTask()

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
    monkeypatch.setattr(crud, "list_calls", lambda spec_id: [])
    monkeypatch.setattr(crud, "list_quotes", lambda call_id: [])
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


def test_start_call_bridge_rejects_human_persona(monkeypatch):
    monkeypatch.setattr(
        crud,
        "get_spec",
        lambda id: {"id": "s1", "user_id": USER_A, "spec_json": {"area_sqft": 500}},
    )
    monkeypatch.setattr(
        crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1", "persona": "human"}
    )
    monkeypatch.setattr(crud, "create_call", lambda row: pytest.fail("call row created"))
    _as(USER_A)

    response = client.post("/calls/start", json={"spec_id": "s1", "dealer_id": "d1"})

    assert response.status_code == 422


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
    monkeypatch.setattr(crud, "list_calls", lambda spec_id: [])
    monkeypatch.setattr(crud, "list_quotes", lambda call_id: [])
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


def _mute_discovery(monkeypatch):
    monkeypatch.setattr(api, "fetch_benchmark", lambda location: None)
    monkeypatch.setattr(api, "discover_dealers", lambda location: [])


def test_create_spec_caches_fetched_benchmark(monkeypatch):
    captured = {}
    monkeypatch.setattr(crud, "create_spec", lambda row: captured.update(row) or {"id": "s1", **row})
    monkeypatch.setattr(crud, "create_dealer", lambda row: {"id": "d", **row})
    monkeypatch.setattr(
        api, "fetch_benchmark", lambda location: {"per_sqft_low": 210, "per_sqft_high": 390}
    )
    monkeypatch.setattr(api, "discover_dealers", lambda location: [])
    _as(USER_A)

    response = client.post(
        "/specs",
        json={"vertical": "shop_rental", "status": "draft", "spec_json": {"location": "Gulberg"}},
    )

    assert response.status_code == 200
    assert captured["benchmark_json"] == {"per_sqft_low": 210, "per_sqft_high": 390}


def test_create_spec_body_benchmark_wins_over_fetch(monkeypatch):
    captured = {}
    monkeypatch.setattr(crud, "create_spec", lambda row: captured.update(row) or {"id": "s1", **row})
    monkeypatch.setattr(crud, "create_dealer", lambda row: {"id": "d", **row})
    monkeypatch.setattr(
        api, "fetch_benchmark", lambda location: pytest.fail("fetched despite body value")
    )
    monkeypatch.setattr(api, "discover_dealers", lambda location: [])
    _as(USER_A)

    response = client.post(
        "/specs",
        json={
            "vertical": "shop_rental",
            "status": "draft",
            "spec_json": {"location": "Gulberg"},
            "benchmark_json": {"per_sqft_low": 100, "per_sqft_high": 200},
        },
    )

    assert response.status_code == 200
    assert captured["benchmark_json"] == {"per_sqft_low": 100, "per_sqft_high": 200}


def test_create_spec_inserts_discovered_dealers(monkeypatch):
    created = []
    monkeypatch.setattr(crud, "create_spec", lambda row: {"id": "s1", **row})

    def fake_create_dealer(row):
        created.append(row)
        return {"id": f"d{len(created)}", **row}

    monkeypatch.setattr(crud, "create_dealer", fake_create_dealer)
    monkeypatch.setattr(api, "fetch_benchmark", lambda location: None)
    monkeypatch.setattr(
        api,
        "discover_dealers",
        lambda location: [
            {"name": "Alpha Estate", "persona": "human", "phone_label": "https://alpha.pk", "source": "tavily"}
        ],
    )
    _as(USER_A)

    response = client.post(
        "/specs",
        json={"vertical": "shop_rental", "status": "draft", "spec_json": {"location": "Gulberg"}},
    )

    assert response.status_code == 200
    assert response.json()["dealers_discovered"] == 1
    tavily_rows = [d for d in created if d.get("source") == "tavily"]
    assert len(tavily_rows) == 1
    assert tavily_rows[0]["persona"] == "human"
    assert tavily_rows[0]["spec_id"] == "s1"
    # seeded personas still present
    assert len(created) > 1


def test_create_spec_without_location_skips_discovery(monkeypatch):
    monkeypatch.setattr(crud, "create_spec", lambda row: {"id": "s1", **row})
    monkeypatch.setattr(crud, "create_dealer", lambda row: {"id": "d", **row})
    monkeypatch.setattr(
        api, "fetch_benchmark", lambda location: pytest.fail("fetched without location")
    )
    monkeypatch.setattr(
        api, "discover_dealers", lambda location: pytest.fail("discovered without location")
    )
    _as(USER_A)

    response = client.post(
        "/specs", json={"vertical": "shop_rental", "status": "draft", "spec_json": {}}
    )

    assert response.status_code == 200
    assert response.json()["dealers_discovered"] == 0


def test_patch_dealer_updates_persona(monkeypatch):
    monkeypatch.setattr(crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1", "persona": "human"})
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    updates = {}

    def fake_update_dealer(id, fields):
        updates.update({"id": id, **fields})
        return {"id": id, "spec_id": "s1", **fields}

    monkeypatch.setattr(crud, "update_dealer", fake_update_dealer)
    _as(USER_A)

    response = client.patch("/dealers/d1", json={"persona": "firm"})

    assert response.status_code == 200
    assert updates == {"id": "d1", "persona": "firm"}
    assert response.json()["persona"] == "firm"


def test_patch_dealer_rejects_unknown_persona(monkeypatch):
    monkeypatch.setattr(crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1"})
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    monkeypatch.setattr(
        crud, "update_dealer", lambda id, fields: pytest.fail("updated invalid persona")
    )
    _as(USER_A)

    response = client.patch("/dealers/d1", json={"persona": "robot"})

    assert response.status_code == 422


def test_patch_dealer_404s_for_non_owner(monkeypatch):
    monkeypatch.setattr(crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1"})
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    _as(USER_B)

    response = client.patch("/dealers/d1", json={"persona": "firm"})

    assert response.status_code == 404


def test_patch_dealer_updates_status(monkeypatch):
    monkeypatch.setattr(crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1", "status": "active"})
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    updates = {}

    def fake_update_dealer(id, fields):
        updates.update({"id": id, **fields})
        return {"id": id, "spec_id": "s1", **fields}

    monkeypatch.setattr(crud, "update_dealer", fake_update_dealer)
    _as(USER_A)

    response = client.patch("/dealers/d1", json={"status": "declined"})

    assert response.status_code == 200
    assert updates == {"id": "d1", "status": "declined"}
    assert response.json()["status"] == "declined"


def test_patch_dealer_rejects_unknown_status(monkeypatch):
    monkeypatch.setattr(crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1"})
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    monkeypatch.setattr(
        crud, "update_dealer", lambda id, fields: pytest.fail("updated invalid status")
    )
    _as(USER_A)

    response = client.patch("/dealers/d1", json={"status": "banned"})

    assert response.status_code == 422


def test_patch_dealer_rejects_empty_body(monkeypatch):
    monkeypatch.setattr(crud, "get_dealer", lambda id: {"id": "d1", "spec_id": "s1"})
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    _as(USER_A)

    response = client.patch("/dealers/d1", json={})

    assert response.status_code == 422


def test_start_call_422s_for_declined_dealer(monkeypatch):
    monkeypatch.setattr(
        crud,
        "get_spec",
        lambda id: {"id": "s1", "user_id": USER_A, "spec_json": {"area_sqft": 500}},
    )
    monkeypatch.setattr(
        crud,
        "get_dealer",
        lambda id: {"id": "d1", "spec_id": "s1", "persona": "firm", "status": "declined"},
    )
    monkeypatch.setattr(crud, "create_call", lambda row: pytest.fail("call row created"))
    _as(USER_A)

    response = client.post("/calls/start", json={"spec_id": "s1", "dealer_id": "d1"})

    assert response.status_code == 422


# --- POST /specs/{id}/reflag (K11) ---------------------------------------

REFLAG_SPEC = {
    "id": "s1",
    "user_id": USER_A,
    "spec_json": {"area_sqft": 900},
    "benchmark_json": {"per_sqft_low": 200, "per_sqft_high": 400},
}


def _reflag_fixture(monkeypatch, quote, spec=REFLAG_SPEC):
    monkeypatch.setattr(crud, "get_spec", lambda id: spec)
    monkeypatch.setattr(crud, "list_calls", lambda **f: [{"id": "c1", "spec_id": "s1"}])
    monkeypatch.setattr(crud, "list_quotes", lambda **f: [quote])
    updates = []

    def fake_update_quote(id, fields):
        updates.append((id, fields))
        return {"id": id, **fields}

    monkeypatch.setattr(crud, "update_quote", fake_update_quote)
    return updates


def test_reflag_requires_auth():
    response = client.post("/specs/s1/reflag")

    assert response.status_code == 401


def test_reflag_404s_for_non_owner(monkeypatch):
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    _as(USER_B)

    response = client.post("/specs/s1/reflag")

    assert response.status_code == 404


def test_reflag_flags_newly_bad_quote(monkeypatch):
    # monthly_low = 200 * 900 = 180000; 30% below = 126000 threshold
    updates = _reflag_fixture(
        monkeypatch,
        {
            "id": "q1",
            "monthly_rent": 100000,
            "advance_months": 2,
            "binding": True,
            "flagged": False,
            "flag_reason": None,
        },
    )
    _as(USER_A)

    response = client.post("/specs/s1/reflag")

    assert response.status_code == 200
    assert response.json() == {"checked": 1, "updated": 1}
    assert len(updates) == 1
    quote_id, fields = updates[0]
    assert quote_id == "q1"
    assert fields["flagged"] is True
    assert "below" in fields["flag_reason"]


def test_reflag_unflags_cleared_quote(monkeypatch):
    updates = _reflag_fixture(
        monkeypatch,
        {
            "id": "q1",
            "monthly_rent": 200000,
            "advance_months": 3,
            "binding": True,
            "flagged": True,
            "flag_reason": "stale reason",
        },
    )
    _as(USER_A)

    response = client.post("/specs/s1/reflag")

    assert response.status_code == 200
    assert response.json() == {"checked": 1, "updated": 1}
    assert updates == [("q1", {"flagged": False, "flag_reason": None})]


def test_reflag_skips_unchanged_quotes(monkeypatch):
    _reflag_fixture(
        monkeypatch,
        {
            "id": "q1",
            "monthly_rent": 200000,
            "advance_months": 3,
            "binding": True,
            "flagged": False,
            "flag_reason": None,
        },
    )
    monkeypatch.setattr(
        crud, "update_quote", lambda *a: pytest.fail("wrote unchanged quote")
    )
    _as(USER_A)

    response = client.post("/specs/s1/reflag")

    assert response.status_code == 200
    assert response.json() == {"checked": 1, "updated": 0}


def test_reflag_none_fields_and_no_benchmark(monkeypatch):
    # Fallback benchmark path with an above-market rent and *unknown* binding.
    # This used to flag ("no written quote" fired on None), which is exactly the
    # false positive that put above-market dealers under the red-flag badge.
    _reflag_fixture(
        monkeypatch,
        {
            "id": "q1",
            "monthly_rent": 200000,
            "advance_months": None,
            "binding": None,
            "flagged": False,
            "flag_reason": None,
        },
        spec={"id": "s1", "user_id": USER_A, "spec_json": {"area_sqft": 900}, "benchmark_json": None},
    )
    monkeypatch.setattr(
        crud, "update_quote", lambda *a: pytest.fail("flagged a quote with unknown binding")
    )
    _as(USER_A)

    response = client.post("/specs/s1/reflag")

    assert response.status_code == 200
    assert response.json() == {"checked": 1, "updated": 0}


def test_reflag_flags_explicitly_non_binding_quote(monkeypatch):
    updates = _reflag_fixture(
        monkeypatch,
        {
            "id": "q1",
            "monthly_rent": 200000,
            "advance_months": None,
            "binding": False,
            "flagged": False,
            "flag_reason": None,
        },
        spec={"id": "s1", "user_id": USER_A, "spec_json": {"area_sqft": 900}, "benchmark_json": None},
    )
    _as(USER_A)

    response = client.post("/specs/s1/reflag")

    assert response.status_code == 200
    assert response.json() == {"checked": 1, "updated": 1}
    _, fields = updates[0]
    assert fields["flagged"] is True
    assert "written quote" in fields["flag_reason"]


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


def test_end_call_404s_for_non_owner(monkeypatch):
    monkeypatch.setattr(crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"})
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    _as(USER_B)

    response = client.post("/calls/c1/end")

    assert response.status_code == 404


def test_end_call_signals_running_bridge(monkeypatch):
    monkeypatch.setattr(crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"})
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    stopped = []
    monkeypatch.setattr(api, "request_stop", lambda call_id: stopped.append(call_id) or True)
    _as(USER_A)

    response = client.post("/calls/c1/end")

    assert response.status_code == 200
    assert response.json() == {"call_id": "c1", "stopping": True}
    assert stopped == ["c1"]


def test_end_call_reports_no_active_bridge(monkeypatch):
    monkeypatch.setattr(crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"})
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    monkeypatch.setattr(api, "request_stop", lambda call_id: False)
    _as(USER_A)

    response = client.post("/calls/c1/end")

    assert response.status_code == 200
    assert response.json() == {"call_id": "c1", "stopping": False}


def test_end_call_finalizes_orphaned_running_call(monkeypatch):
    # backend restarted mid-call: bridge task gone, row stuck "running".
    # /end must finalize it so the frontend poll can converge.
    monkeypatch.setattr(
        crud,
        "get_call",
        lambda id: {"id": "c1", "spec_id": "s1", "status": "running", "transcript_json": None},
    )
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    monkeypatch.setattr(api, "request_stop", lambda call_id: False)
    updates = []
    monkeypatch.setattr(crud, "update_call", lambda id, fields: updates.append((id, fields)))
    _as(USER_A)

    response = client.post("/calls/c1/end")

    assert response.status_code == 200
    assert response.json() == {"call_id": "c1", "stopping": False}
    assert len(updates) == 1
    call_id, fields = updates[0]
    assert call_id == "c1"
    assert fields["status"] == "completed"
    assert fields["outcome"] == "callback"
    assert fields["ended_at"]


def test_end_call_leaves_completed_call_alone(monkeypatch):
    monkeypatch.setattr(
        crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1", "status": "completed"}
    )
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    monkeypatch.setattr(api, "request_stop", lambda call_id: False)
    updates = []
    monkeypatch.setattr(crud, "update_call", lambda id, fields: updates.append((id, fields)))
    _as(USER_A)

    response = client.post("/calls/c1/end")

    assert response.status_code == 200
    assert updates == []


def test_end_call_recovery_auto_blocks_declined_dealer(monkeypatch):
    monkeypatch.setattr(
        crud,
        "get_call",
        lambda id: {
            "id": "c1",
            "spec_id": "s1",
            "status": "running",
            "transcript_json": [{"line": 1, "speaker": "dealer", "text": "not interested"}],
        },
    )
    monkeypatch.setattr(crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A})
    monkeypatch.setattr(api, "request_stop", lambda call_id: False)
    monkeypatch.setattr(
        crud, "update_call", lambda id, fields: {"id": id, "dealer_id": "d1", **fields}
    )
    blocked = []
    monkeypatch.setattr(
        crud, "update_dealer", lambda id, fields: blocked.append((id, fields))
    )
    _as(USER_A)

    response = client.post("/calls/c1/end")

    assert response.status_code == 200
    assert blocked == [("d1", {"status": "declined"})]


def test_post_call_webhook_declined_transcript_auto_blocks_dealer(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr(
        crud, "update_call", lambda id, fields: {"id": id, "dealer_id": "d1", **fields}
    )
    blocked = []
    monkeypatch.setattr(
        crud, "update_dealer", lambda id, fields: blocked.append((id, fields))
    )

    event = {
        "type": "post_call_transcription",
        "data": {
            "conversation_initiation_client_data": {"dynamic_variables": {"call_id": "c1"}},
            "transcript": [
                {"role": "user", "message": "Sorry, not interested, already rented."},
            ],
        },
    }
    body = json.dumps(event)
    response = client.post(
        "/webhooks/post-call", content=body, headers=_signed_headers(body)
    )

    assert response.status_code == 200
    assert blocked == [("d1", {"status": "declined"})]


# --- _dealer_dynamic_variables (persona randomized anchor figures) -------

import re

from app.vertical import load_vertical


def test_dealer_dynamic_variables_covers_every_persona_placeholder():
    config = load_vertical()
    spec = {"id": "s1", "spec_json": {"location": "Gulberg", "floor": "ground", "budget_monthly_rent": 100000}}
    for persona in config.persona_prompts:
        placeholders = set(re.findall(r"{{(\w+)}}", config.persona_prompts[persona]))
        returned = api._dealer_dynamic_variables(spec, persona)
        assert placeholders <= set(returned), f"{persona} references unfilled vars: {placeholders - set(returned)}"


def test_dealer_dynamic_variables_stay_within_persona_bands():
    # no area_sqft -> _benchmark's monthly_low/high stay None -> base_rent
    # falls back to budget_monthly_rent, a value fixed by the test (not the
    # benchmark_fallback config), so the expected ratio math below is exact.
    spec = {"id": "s1", "spec_json": {"location": "Gulberg", "floor": "ground", "budget_monthly_rent": 100000}}
    base_rent = spec["spec_json"]["budget_monthly_rent"]
    for persona, band in api.PERSONA_BANDS.items():
        v = api._dealer_dynamic_variables(spec, persona)
        rent_ratio = v["asking_rent"] / base_rent
        assert band["rent"][0] - 0.01 <= rent_ratio <= band["rent"][1] + 0.01
        assert band["advance"][0] <= v["advance_months"] <= band["advance"][1]
        assert band["increment"][0] <= v["annual_increment_pct"] <= band["increment"][1]
        commission_ratio = v["commission"] / v["asking_rent"]
        assert band["commission_mo"][0] - 0.02 <= commission_ratio <= band["commission_mo"][1] + 0.02
        maint_ratio = v["maintenance"] / v["asking_rent"]
        assert band["maint_pct"][0] - 0.02 <= maint_ratio <= band["maint_pct"][1] + 0.02


def test_dealer_dynamic_variables_defaults_missing_spec_fields():
    # location/floor/area_sqft missing entirely — every key must still be
    # present (ElevenLabs breaks on an unfilled {{var}}), never omitted.
    spec = {"id": "s1", "spec_json": {}}
    v = api._dealer_dynamic_variables(spec, "firm")
    assert v["location"] == "the area"
    assert v["floor"] == ""
    assert v["area_sqft"] == ""
    assert v["asking_rent"] > 0


# --- call history: later calls remember this dealer's own quote --------------

def _hist(monkeypatch, calls, quotes_by_call):
    monkeypatch.setattr(crud, "list_calls", lambda spec_id: calls)
    monkeypatch.setattr(crud, "list_quotes", lambda call_id: quotes_by_call.get(call_id, []))


def test_prior_call_summary_is_empty_on_a_first_call(monkeypatch):
    _hist(monkeypatch, [], {})
    summary = api._prior_call_summary([], None)
    assert "first call" in summary


def test_prior_call_summary_recites_the_dealers_own_quote(monkeypatch):
    calls = [
        {
            "id": "c1",
            "dealer_id": "d1",
            "started_at": "2026-01-01T10:00:00Z",
            "transcript_json": [
                {"line": 1, "speaker": "dealer", "text": "Rent is 151000."},
                {"line": 2, "speaker": "negotiator", "text": "Understood, thank you."},
            ],
        }
    ]
    quote = {
        "monthly_rent": 151000,
        "advance_months": 2,
        "commission": 151000,
        "maintenance": 5000,
        "annual_increment_pct": 5,
    }

    summary = api._prior_call_summary(calls, quote)

    assert "151,000" in summary
    assert "2 months advance" in summary
    assert "Do not ask them to repeat" in summary
    assert "Rent is 151000." in summary  # last-call tail is carried through


def test_prior_call_summary_notes_when_no_quote_was_given():
    calls = [{"id": "c1", "dealer_id": "d1", "started_at": "2026-01-01T10:00:00Z"}]
    assert "did not give you a quote" in api._prior_call_summary(calls, None)


def test_latest_prior_quote_takes_the_most_recent_quoted_call(monkeypatch):
    calls = [
        {"id": "c1", "dealer_id": "d1", "started_at": "2026-01-01T10:00:00Z"},
        {"id": "c2", "dealer_id": "d1", "started_at": "2026-01-01T12:00:00Z"},
    ]
    _hist(monkeypatch, calls, {"c1": [{"monthly_rent": 151000}], "c2": [{"monthly_rent": 140000}]})

    assert api._latest_prior_quote(calls)["monthly_rent"] == 140000


def test_latest_prior_quote_falls_back_to_an_earlier_quoted_call(monkeypatch):
    """A later call that produced nothing must not erase the quote we do have."""
    calls = [
        {"id": "c1", "dealer_id": "d1", "started_at": "2026-01-01T10:00:00Z"},
        {"id": "c2", "dealer_id": "d1", "started_at": "2026-01-01T12:00:00Z"},
    ]
    _hist(monkeypatch, calls, {"c1": [{"monthly_rent": 151000}]})

    assert api._latest_prior_quote(calls)["monthly_rent"] == 151000


def test_prior_calls_excludes_other_dealers_and_the_current_call(monkeypatch):
    calls = [
        {"id": "c1", "dealer_id": "d1", "started_at": "2026-01-01T10:00:00Z"},
        {"id": "c2", "dealer_id": "OTHER", "started_at": "2026-01-01T11:00:00Z"},
        {"id": "c3", "dealer_id": "d1", "started_at": "2026-01-01T12:00:00Z"},
    ]
    monkeypatch.setattr(crud, "list_calls", lambda spec_id: calls)

    ids = [c["id"] for c in api._prior_calls("s1", "d1", "c3")]

    assert ids == ["c1"]  # other dealer excluded (honesty guardrail), current excluded


def test_dealer_reuses_its_own_prior_numbers_on_a_later_call(monkeypatch):
    """Regenerating per call meant a dealer who said 151,000 in round 1 said
    something else in round 2, making the negotiator's leverage incoherent."""
    spec = {"id": "s1", "spec_json": {"area_sqft": 900, "location": "Gulberg"}, "benchmark_json": None}
    prior = {
        "monthly_rent": 151000,
        "advance_months": 2,
        "commission": 151000,
        "maintenance": 5000,
        "annual_increment_pct": 5,
    }

    for _ in range(5):  # would drift if it were still random
        v = api._dealer_dynamic_variables(spec, "firm", prior)
        assert v["asking_rent"] == 151000
        assert v["advance_months"] == 2
        assert v["commission"] == 151000
        assert v["maintenance"] == 5000
        assert v["annual_increment_pct"] == 5
        assert "already quoted these exact" in v["prior_call_note"]


def test_dealer_generates_fresh_numbers_on_a_first_call():
    spec = {"id": "s1", "spec_json": {"area_sqft": 900, "location": "Gulberg"}, "benchmark_json": None}

    v = api._dealer_dynamic_variables(spec, "firm", None)

    assert v["asking_rent"] > 0
    assert "first call" in v["prior_call_note"]


def test_negotiator_vars_carry_round_and_history():
    spec = {"id": "s1", "spec_json": {"location": "Gulberg"}}

    v = api._dynamic_variables(spec, "c9", "d1", round_number=2, prior_summary="They quoted 151,000.")

    assert v["round_number"] == 2
    assert v["prior_call_summary"] == "They quoted 151,000."


def test_negotiator_vars_default_to_no_history():
    spec = {"id": "s1", "spec_json": {"location": "Gulberg"}}

    v = api._dynamic_variables(spec, "c1", "d1")

    assert v["round_number"] == 1
    assert "first call" in v["prior_call_summary"]
