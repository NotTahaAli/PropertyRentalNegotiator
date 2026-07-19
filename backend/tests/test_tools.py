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
    "/tools/log_call_status",
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


def test_no_written_quote_fires_only_on_explicit_false():
    result = tools.evaluate_red_flags(_spec(), monthly_rent=200000, binding=False)
    assert result["action"] == "flag"
    assert any("written" in r for r in result["reasons"])


def test_unknown_binding_does_not_fire_no_written_quote():
    """Regression: `not binding` treated None as "dealer refused a written quote".

    An above-market dealer that simply didn't have `binding` recorded came back
    flagged, which inverts the whole point of the rule. Unknown stays unjudged.
    """
    result = tools.evaluate_red_flags(_spec(), monthly_rent=200000, binding=None)
    assert result["action"] == "clear"
    assert result["reasons"] == []


def test_advance_months_boundary():
    fired = tools.evaluate_red_flags(_spec(), monthly_rent=200000, advance_months=7, binding=True)
    assert fired["action"] == "flag"
    ok = tools.evaluate_red_flags(_spec(), monthly_rent=200000, advance_months=6, binding=True)
    assert ok["action"] == "clear"


def test_multiple_rules_confirm_then_flag_wins():
    result = tools.evaluate_red_flags(_spec(), monthly_rent=90000, advance_months=12, binding=False)
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


def test_check_redflag_spec_id_only_is_clear(monkeypatch):
    """Nothing asserted about the quote yet -> nothing to flag. Previously this
    returned `flag` purely because `binding` was absent from the body."""
    monkeypatch.setattr(crud, "get_spec", lambda id: _spec())
    response = client.post("/tools/check_redflag", json={"spec_id": "s1"}, headers=_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["action"] == "clear"
    assert body["reasons"] == []


def test_check_redflag_explicit_non_binding_flags(monkeypatch):
    monkeypatch.setattr(crud, "get_spec", lambda id: _spec())
    response = client.post(
        "/tools/check_redflag",
        json={"spec_id": "s1", "monthly_rent": 200000, "binding": False},
        headers=_headers(),
    )
    body = response.json()
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
    monkeypatch.setattr(crud, "list_quotes", lambda call_id: [])

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
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 90000, "binding": False},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert captured["flagged"] is True
    assert "below" in captured["flag_reason"]
    assert "written" in captured["flag_reason"]


def test_log_quote_above_market_without_binding_is_not_flagged(monkeypatch):
    """The Upseller case: quotes *above* benchmark, `binding` never established.

    Used to come back flagged for "no written quote" purely because the field
    defaulted to False, which put an above-market dealer under the same badge as
    a suspiciously-cheap one.
    """
    captured = {}
    _wire_call(monkeypatch, captured)
    response = client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 300000},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert captured["flagged"] is False
    assert captured["flag_reason"] is None
def _wire_upserting_call(monkeypatch):
    """Stateful quote store: second log_quote for the same call updates the row."""
    store: dict[str, dict] = {}
    monkeypatch.setattr(crud, "get_call", lambda id: {"id": id, "spec_id": "s1"} if id == "c1" else None)
    monkeypatch.setattr(crud, "get_spec", lambda id: _spec())

    def fake_create(row):
        store["q1"] = {"id": "q1", **row}
        return store["q1"]

    def fake_update(id, fields):
        store[id] = {**store[id], **fields}
        return store[id]

    monkeypatch.setattr(crud, "create_quote", fake_create)
    monkeypatch.setattr(crud, "update_quote", fake_update)
    monkeypatch.setattr(crud, "list_quotes", lambda call_id: list(store.values()) if call_id == "c1" else [])
    return store


def test_log_quote_partial_then_update_merges_same_row(monkeypatch):
    store = _wire_upserting_call(monkeypatch)

    first = client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 200000},
        headers=_headers(),
    )
    assert first.status_code == 200
    assert first.json()["quote_id"] == "q1"
    assert store["q1"]["flagged"] is False  # binding not stated != dealer refused

    second = client.post(
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
    assert second.status_code == 200
    assert second.json()["quote_id"] == "q1"  # same row, not a second insert
    assert len(store) == 1
    assert store["q1"]["total_first_year"] == 2960000
    assert store["q1"]["flagged"] is False  # fresh verdict unflags


def test_log_quote_update_keeps_earlier_fields_and_binding(monkeypatch):
    store = _wire_upserting_call(monkeypatch)

    client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 200000, "advance_months": 3, "binding": True},
        headers=_headers(),
    )
    # later call omits advance_months and binding — earlier values must survive
    client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 190000, "commission": 50000},
        headers=_headers(),
    )
    q = store["q1"]
    assert q["monthly_rent"] == 190000
    assert q["advance_months"] == 3
    assert q["commission"] == 50000
    assert q["binding"] is True


# --- POST /tools/get_leverage --------------------------------------------

def _quote(dealer_id, total, flagged=False, rent=100000):
    return {
        "id": f"q-{dealer_id}-{total}",
        "dealer_id": dealer_id,
        "monthly_rent": rent,
        "advance_months": 2,
        "commission": 50000,
        "maintenance": 3000,
        "total_first_year": total,
        "flagged": flagged,
    }


def _wire_leverage(monkeypatch, quotes_by_call):
    monkeypatch.setattr(crud, "get_spec", lambda id: _spec())
    monkeypatch.setattr(
        crud,
        "list_dealers",
        lambda spec_id: [
            {"id": "d1", "name": "Ali Estates"},
            {"id": "d2", "name": "Khan Properties"},
            {"id": "d3", "name": "Metro Realty"},
        ],
    )
    monkeypatch.setattr(
        crud, "list_calls", lambda spec_id: [{"id": c} for c in quotes_by_call]
    )
    monkeypatch.setattr(crud, "list_quotes", lambda call_id: quotes_by_call[call_id])


def _leverage(dealer_id="d1"):
    return client.post(
        "/tools/get_leverage",
        json={"spec_id": "s1", "dealer_id": dealer_id},
        headers=_headers(),
    )


def test_get_leverage_sorted_top3_with_names(monkeypatch):
    _wire_leverage(
        monkeypatch,
        {
            "c1": [_quote("d2", 2000000), _quote("d2", 1800000)],
            "c2": [_quote("d3", 1500000), _quote("d3", 2200000)],
        },
    )
    body = _leverage("d1").json()
    totals = [q["total_first_year"] for q in body["quotes"]]
    assert totals == [1500000, 1800000, 2000000]
    assert body["quotes"][0]["dealer"] == "Metro Realty"
    assert set(body["quotes"][0]) == {
        "dealer",
        "property",
        "monthly_rent",
        "advance_months",
        "commission",
        "maintenance",
        "total_first_year",
    }


def test_get_leverage_excludes_flagged_and_own(monkeypatch):
    _wire_leverage(
        monkeypatch,
        {
            "c1": [_quote("d1", 1000000)],  # caller's own
            "c2": [_quote("d2", 1200000, flagged=True), _quote("d3", 1900000)],
        },
    )
    body = _leverage("d1").json()
    assert [q["total_first_year"] for q in body["quotes"]] == [1900000]


def test_get_leverage_empty_when_nothing_qualifies(monkeypatch):
    _wire_leverage(monkeypatch, {"c1": [_quote("d1", 1000000)]})
    assert _leverage("d1").json() == {"quotes": []}


def test_get_leverage_includes_property_to_distinguish_a_dealer_s_shops(monkeypatch):
    quotes_by_call = {
        "c1": [
            {**_quote("d2", 1900000), "property_ref": "Shop 2"},
            {**_quote("d2", 2100000), "property_ref": "Shop 7"},
        ],
    }
    _wire_leverage(monkeypatch, quotes_by_call)
    body = _leverage("d1").json()
    assert {q["property"] for q in body["quotes"]} == {"Shop 2", "Shop 7"}


def test_get_leverage_unknown_spec_404(monkeypatch):
    monkeypatch.setattr(crud, "get_spec", lambda id: None)
    assert _leverage().status_code == 404


def _wire_upserting_call_multi(monkeypatch):
    """Stateful quote store supporting multiple property-discriminated rows per call."""
    store: dict[str, dict] = {}
    counter = {"n": 0}
    monkeypatch.setattr(crud, "get_call", lambda id: {"id": id, "spec_id": "s1"} if id == "c1" else None)
    monkeypatch.setattr(crud, "get_spec", lambda id: _spec())

    def fake_create(row):
        counter["n"] += 1
        qid = f"q{counter['n']}"
        store[qid] = {"id": qid, **row}
        return store[qid]

    def fake_update(id, fields):
        store[id] = {**store[id], **fields}
        return store[id]

    monkeypatch.setattr(crud, "create_quote", fake_create)
    monkeypatch.setattr(crud, "update_quote", fake_update)
    monkeypatch.setattr(crud, "list_quotes", lambda call_id: list(store.values()) if call_id == "c1" else [])
    return store


def test_log_quote_two_properties_same_call_create_two_rows(monkeypatch):
    store = _wire_upserting_call_multi(monkeypatch)

    r1 = client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 200000, "property_ref": "Shop 4"},
        headers=_headers(),
    )
    r2 = client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 250000, "property_ref": "Shop 7"},
        headers=_headers(),
    )

    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["quote_id"] != r2.json()["quote_id"]
    assert len(store) == 2
    assert {q["property_ref"] for q in store.values()} == {"Shop 4", "Shop 7"}


def test_log_quote_same_property_ref_merges_into_one_row(monkeypatch):
    store = _wire_upserting_call_multi(monkeypatch)

    client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 200000, "property_ref": "Shop 4"},
        headers=_headers(),
    )
    client.post(
        "/tools/log_quote",
        json={
            "call_id": "c1",
            "dealer_id": "d1",
            "monthly_rent": 200000,
            "advance_months": 2,
            "binding": True,
            "property_ref": "Shop 4",
        },
        headers=_headers(),
    )

    assert len(store) == 1
    q = next(iter(store.values()))
    assert q["advance_months"] == 2
    assert q["binding"] is True


def test_log_quote_no_property_ref_still_merges_single_row(monkeypatch):
    """Back-compat: omitting property_ref on both calls keeps today's one-row-per-call behavior."""
    store = _wire_upserting_call_multi(monkeypatch)

    client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 200000},
        headers=_headers(),
    )
    client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 200000, "advance_months": 2},
        headers=_headers(),
    )

    assert len(store) == 1


def test_log_quote_property_ref_and_no_ref_are_distinct_rows(monkeypatch):
    """A quote scoped to a shop must not merge into an earlier no-identifier quote."""
    store = _wire_upserting_call_multi(monkeypatch)

    client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 200000},
        headers=_headers(),
    )
    client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 250000, "property_ref": "Shop 7"},
        headers=_headers(),
    )

    assert len(store) == 2


def test_log_quote_empty_string_property_ref_same_as_none(monkeypatch):
    store = _wire_upserting_call_multi(monkeypatch)

    client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 200000, "property_ref": ""},
        headers=_headers(),
    )
    client.post(
        "/tools/log_quote",
        json={"call_id": "c1", "dealer_id": "d1", "monthly_rent": 250000},
        headers=_headers(),
    )

    assert len(store) == 1


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


# --- POST /tools/log_call_status ------------------------------------------

def _wire_status_call(monkeypatch, existing_outcome=None):
    updates = []
    monkeypatch.setattr(crud, "get_call", lambda id: {"id": id, "dealer_id": "d1", "outcome": existing_outcome} if id == "c1" else None)

    def fake_update(id, fields):
        updates.append((id, fields))
        return {"id": id, "dealer_id": "d1", **fields}

    monkeypatch.setattr(crud, "update_call", fake_update)
    blocked = []
    monkeypatch.setattr(crud, "update_dealer", lambda id, fields: blocked.append((id, fields)))
    return updates, blocked


def test_log_call_status_invalid_outcome_422(monkeypatch):
    _wire_status_call(monkeypatch)
    response = client.post(
        "/tools/log_call_status",
        json={"call_id": "c1", "outcome": "maybe"},
        headers=_headers(),
    )
    assert response.status_code == 422


def test_log_call_status_unknown_call_404(monkeypatch):
    _wire_status_call(monkeypatch)
    response = client.post(
        "/tools/log_call_status",
        json={"call_id": "nope", "outcome": "quote"},
        headers=_headers(),
    )
    assert response.status_code == 404


def test_log_call_status_writes_outcome(monkeypatch):
    updates, _ = _wire_status_call(monkeypatch)
    response = client.post(
        "/tools/log_call_status",
        json={"call_id": "c1", "outcome": "final_quote"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json() == {"call_id": "c1", "outcome": "final_quote"}
    assert updates == [("c1", {"outcome": "final_quote"})]


def test_log_call_status_declined_blocks_dealer(monkeypatch):
    _, blocked = _wire_status_call(monkeypatch)
    response = client.post(
        "/tools/log_call_status",
        json={"call_id": "c1", "outcome": "declined"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert blocked == [("d1", {"status": "declined"})]


def test_log_call_status_callback_writes_time_and_note(monkeypatch):
    updates, _ = _wire_status_call(monkeypatch)
    response = client.post(
        "/tools/log_call_status",
        json={"call_id": "c1", "outcome": "callback", "callback_at": "tomorrow 4pm", "notes": "ask for Bilal"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert updates == [
        ("c1", {"outcome": "callback", "callback_at": "tomorrow 4pm", "callback_note": "ask for Bilal"})
    ]


def test_log_call_status_updates_an_already_set_outcome(monkeypatch):
    # set_call_outcome (unlike finalize_call) is the authoritative setter and
    # must apply even if the negotiator already logged one earlier in the call.
    updates, _ = _wire_status_call(monkeypatch, existing_outcome="quote")
    response = client.post(
        "/tools/log_call_status",
        json={"call_id": "c1", "outcome": "final_quote"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "final_quote"
