from fastapi.testclient import TestClient

from app import crud
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_get_spec(monkeypatch):
    monkeypatch.setattr(
        crud, "create_spec", lambda row: {"id": "s1", **row}
    )
    monkeypatch.setattr(
        crud,
        "get_spec",
        lambda id: {"id": "s1", "vertical": "shop_rental"} if id == "s1" else None,
    )

    created = client.post(
        "/specs",
        json={
            "vertical": "shop_rental",
            "status": "draft",
            "spec_json": {"area_sqft": 800},
        },
    )
    assert created.status_code == 200
    assert created.json()["id"] == "s1"

    fetched = client.get("/specs/s1")
    assert fetched.status_code == 200
    assert fetched.json() == {"id": "s1", "vertical": "shop_rental"}

    missing = client.get("/specs/missing")
    assert missing.status_code == 404


def test_list_dealers_filters_by_spec_id(monkeypatch):
    captured = {}

    def fake_list_dealers(**filters):
        captured.update(filters)
        return [{"id": "d1"}]

    monkeypatch.setattr(crud, "list_dealers", fake_list_dealers)

    response = client.get("/dealers", params={"spec_id": "s1"})
    assert response.status_code == 200
    assert response.json() == [{"id": "d1"}]
    assert captured == {"spec_id": "s1"}
