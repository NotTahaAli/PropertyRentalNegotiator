import pytest
from fastapi.testclient import TestClient

from app import crud, tools
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


# --- _benchmark ----------------------------------------------------------

def _spec(area=900, benchmark_json=None):
    spec_json = {"location": "Gulberg Lahore"}
    if area is not None:
        spec_json["area_sqft"] = area
    return {"id": "s1", "spec_json": spec_json, "benchmark_json": benchmark_json}


def test_benchmark_fallback_scaled_by_area():
    result = tools._benchmark(_spec(area=900))
    assert result == {
        "currency": "PKR",
        "per_sqft_low": 180,
        "per_sqft_high": 450,
        "area_sqft": 900,
        "monthly_low": 162000,
        "monthly_high": 405000,
        "source": "fallback",
    }


def test_benchmark_cached_json_wins():
    result = tools._benchmark(_spec(area=100, benchmark_json={"per_sqft_low": 200, "per_sqft_high": 400}))
    assert result["per_sqft_low"] == 200
    assert result["monthly_low"] == 20000
    assert result["monthly_high"] == 40000
    assert result["source"] == "cached"


def test_benchmark_without_area_omits_monthly():
    result = tools._benchmark(_spec(area=None))
    assert result["per_sqft_low"] == 180
    assert result["area_sqft"] is None
    assert result["monthly_low"] is None
    assert result["monthly_high"] is None


# --- evaluate_red_flags --------------------------------------------------
# fallback low for area 900 = 162000; below-market boundary = 0.7 * 162000 = 113400

def test_clear_quote_passes_all_rules():
    result = tools.evaluate_red_flags(_spec(), monthly_rent=200000, advance_months=3, binding=True)
    assert result["action"] == "clear"
    assert result["reasons"] == []
    assert result["confirm_question"] is None
    assert result["benchmark"]["monthly_low"] == 162000


def test_below_market_fires_under_boundary():
    result = tools.evaluate_red_flags(_spec(), monthly_rent=113399, binding=True)
    assert result["action"] == "confirm_then_flag"
    assert result["confirm_question"]
    assert any("below" in r for r in result["reasons"])


def test_below_market_not_fired_at_boundary():
    result = tools.evaluate_red_flags(_spec(), monthly_rent=113400, binding=True)
    assert result["action"] == "clear"


def test_below_market_skipped_without_area():
    result = tools.evaluate_red_flags(_spec(area=None), monthly_rent=1, binding=True)
    assert result["action"] == "clear"


def test_no_written_quote_fires_on_false_and_absent():
    for binding in (False, None):
        result = tools.evaluate_red_flags(_spec(), monthly_rent=200000, binding=binding)
        assert result["action"] == "flag"
        assert any("written" in r for r in result["reasons"])


def test_advance_months_boundary():
    fired = tools.evaluate_red_flags(_spec(), monthly_rent=200000, advance_months=7, binding=True)
    assert fired["action"] == "flag"
    ok = tools.evaluate_red_flags(_spec(), monthly_rent=200000, advance_months=6, binding=True)
    assert ok["action"] == "clear"


def test_multiple_rules_confirm_then_flag_wins():
    result = tools.evaluate_red_flags(_spec(), monthly_rent=90000, advance_months=12, binding=None)
    assert result["action"] == "confirm_then_flag"
    assert len(result["reasons"]) == 3
    assert result["confirm_question"]


# --- POST /tools/get_benchmark -------------------------------------------

def test_get_benchmark_endpoint(monkeypatch):
    monkeypatch.setattr(crud, "get_spec", lambda id: _spec() if id == "s1" else None)
    response = client.post("/tools/get_benchmark", json={"spec_id": "s1"}, headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["monthly_low"] == 162000
    assert body["source"] == "fallback"


def test_get_benchmark_unknown_spec_404(monkeypatch):
    monkeypatch.setattr(crud, "get_spec", lambda id: None)
    response = client.post("/tools/get_benchmark", json={"spec_id": "nope"}, headers=_headers())
    assert response.status_code == 404


# --- POST /tools/check_redflag -------------------------------------------

def test_check_redflag_clear(monkeypatch):
    monkeypatch.setattr(crud, "get_spec", lambda id: _spec())
    response = client.post(
        "/tools/check_redflag",
        json={"spec_id": "s1", "monthly_rent": 200000, "advance_months": 2, "binding": True},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["action"] == "clear"


def test_check_redflag_lowball(monkeypatch):
    monkeypatch.setattr(crud, "get_spec", lambda id: _spec())
    response = client.post(
        "/tools/check_redflag",
        json={"spec_id": "s1", "monthly_rent": 90000, "binding": True},
        headers=_headers(),
    )
    body = response.json()
    assert body["action"] == "confirm_then_flag"
    assert body["confirm_question"]
    assert body["benchmark"]["monthly_low"] == 162000


def test_check_redflag_spec_id_only_fires_no_written_quote(monkeypatch):
    monkeypatch.setattr(crud, "get_spec", lambda id: _spec())
    response = client.post("/tools/check_redflag", json={"spec_id": "s1"}, headers=_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["action"] == "flag"
    assert any("written" in r for r in body["reasons"])


def test_check_redflag_unknown_spec_404(monkeypatch):
    monkeypatch.setattr(crud, "get_spec", lambda id: None)
    response = client.post("/tools/check_redflag", json={"spec_id": "nope"}, headers=_headers())
    assert response.status_code == 404


# --- POST /tools/log_quote -----------------------------------------------

def _wire_call(monkeypatch, captured):
    monkeypatch.setattr(crud, "get_call", lambda id: {"id": id, "spec_id": "s1"} if id == "c1" else None)
    monkeypatch.setattr(crud, "get_spec", lambda id: _spec())

    def fake_create_quote(row):
        captured.update(row)
        return {"id": "q1", **row}

    monkeypatch.setattr(crud, "create_quote", fake_create_quote)


def test_log_quote_clean(monkeypatch):
    captured = {}
    _wire_call(monkeypatch, captured)
    response = client.post(
        "/tools/log_quote",
        json={
            "call_id": "c1",
            "dealer_id": "d1",
            "monthly_rent": 200000,
            "advance_months": 2,
            "commission": 100000,
            "maintenance": 5000,
            "annual_increment_pct": 10,
            "binding": True,
        },
        headers=_headers(),
    )
    assert response.status_code == 200
    assert captured["total_first_year"] == 2960000  # 12*200k + 2*200k + 100k + 12*5k
    assert captured["flagged"] is False
    assert captured["flag_reason"] is None
    assert response.json() == {
        "quote_id": "q1",
        "total_first_year": 2960000,
        "flagged": False,
        "flag_reason": None,
    }


def test_log_quote_lowball_unbinding_flagged(monkeypatch):
    captured = {}
    _wire_call(monkeypatch, captured)
    response = client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 90000},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert captured["flagged"] is True
    assert "below" in captured["flag_reason"]
    assert "written" in captured["flag_reason"]


def test_log_quote_unknown_call_404(monkeypatch):
    called = []
    monkeypatch.setattr(crud, "get_call", lambda id: None)
    monkeypatch.setattr(crud, "create_quote", lambda row: called.append(row))
    response = client.post(
        "/tools/log_quote",
        json={"call_id": "nope", "dealer_id": "d1", "monthly_rent": 100},
        headers=_headers(),
    )
    assert response.status_code == 404
    assert called == []
