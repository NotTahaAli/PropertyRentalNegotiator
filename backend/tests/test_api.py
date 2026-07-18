from fastapi.testclient import TestClient

from app import crud
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
    _as(USER_A)

    response = client.post(
        "/specs",
        json={"vertical": "shop_rental", "status": "draft", "spec_json": {}},
    )

    assert response.status_code == 200
    assert captured["user_id"] == USER_A


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
