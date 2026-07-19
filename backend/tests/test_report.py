import pytest
from fastapi.testclient import TestClient

from app import crud, report, storage
from app.auth import get_current_user_id
from app.main import app

client = TestClient(app)

USER_A = "user-a"
USER_B = "user-b"
SPEC_ID = "s1"


def _as(user_id):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def teardown_function():
    app.dependency_overrides.clear()


def _dealer(id, name, persona):
    return {"id": id, "spec_id": SPEC_ID, "name": name, "persona": persona}


def _call(id, dealer_id, round, started_at, outcome="quote", transcript=None, recording=None):
    return {
        "id": id,
        "spec_id": SPEC_ID,
        "dealer_id": dealer_id,
        "round": round,
        "status": "completed",
        "started_at": started_at,
        "outcome": outcome,
        "transcript_json": transcript,
        "recording_url": recording,
    }


def _quote(call_id, dealer_id, total, rent=100000, flagged=False, reason=None, binding=True, property_ref=None):
    return {
        "id": f"q-{call_id}-{property_ref or 'x'}",
        "call_id": call_id,
        "dealer_id": dealer_id,
        "monthly_rent": rent,
        "advance_months": 2,
        "commission": 50000,
        "maintenance": 3000,
        "total_first_year": total,
        "binding": binding,
        "flagged": flagged,
        "flag_reason": reason,
        "property_ref": property_ref,
    }


def _wire(monkeypatch, dealers, calls, quotes_by_call, spec_owner=USER_A):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": SPEC_ID, "user_id": spec_owner} if id == SPEC_ID else None
    )
    monkeypatch.setattr(crud, "list_dealers", lambda spec_id: dealers)
    monkeypatch.setattr(crud, "list_calls", lambda spec_id: calls)
    monkeypatch.setattr(crud, "list_quotes", lambda call_id: quotes_by_call.get(call_id, []))
    monkeypatch.setattr(storage, "signed_recording_url", lambda path, **kw: f"https://signed/{path}")
    monkeypatch.setattr(report.storage, "signed_recording_url", lambda path, **kw: f"https://signed/{path}")


# --- ranking -------------------------------------------------------------

def test_ranks_by_total_first_year_ascending(monkeypatch):
    dealers = [_dealer("d1", "Alpha", "firm"), _dealer("d2", "Beta", "upseller")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z"), _call("c2", "d2", 1, "2026-01-01T11:00:00Z")]
    quotes = {"c1": [_quote("c1", "d1", 2_000_000)], "c2": [_quote("c2", "d2", 1_500_000)]}
    _wire(monkeypatch, dealers, calls, quotes)

    result = report.build_report(SPEC_ID)

    assert [r["dealer_name"] for r in result["rows"]] == ["Beta", "Alpha"]
    assert [r["rank"] for r in result["rows"]] == [1, 2]
    assert result["recommended_dealer_id"] == "d2"


def test_flagged_quote_never_ranks_first_even_when_cheapest(monkeypatch):
    dealers = [_dealer("d1", "Clean", "firm"), _dealer("d2", "Suspicious", "lowballer")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z"), _call("c2", "d2", 1, "2026-01-01T11:00:00Z")]
    quotes = {
        "c1": [_quote("c1", "d1", 2_000_000)],
        "c2": [_quote("c2", "d2", 900_000, flagged=True, reason="40% under benchmark")],
    }
    _wire(monkeypatch, dealers, calls, quotes)

    result = report.build_report(SPEC_ID)

    assert result["recommended_dealer_id"] == "d1"
    ranks = {r["dealer_name"]: r["rank"] for r in result["rows"]}
    assert ranks == {"Clean": 1, "Suspicious": 2}
    # shown and ranked, never dropped
    assert any(r["quote"]["flagged"] for r in result["rows"])
    assert "40% under benchmark" in result["recommendation_text"]


def test_dealer_without_quote_is_unranked_but_present(monkeypatch):
    dealers = [_dealer("d1", "Alpha", "firm"), _dealer("d2", "Stonewall", "stonewaller")]
    calls = [
        _call("c1", "d1", 1, "2026-01-01T10:00:00Z"),
        _call("c2", "d2", 1, "2026-01-01T11:00:00Z", outcome="declined"),
    ]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 2_000_000)]})

    result = report.build_report(SPEC_ID)

    stonewall = next(r for r in result["rows"] if r["dealer_name"] == "Stonewall")
    assert stonewall["rank"] is None
    assert stonewall["quote"] is None
    assert stonewall["outcome"] == "declined"
    assert result["rows"][-1]["dealer_name"] == "Stonewall"  # unranked sort last


def test_never_dialled_dealer_is_omitted(monkeypatch):
    dealers = [_dealer("d1", "Alpha", "firm"), _dealer("d2", "NeverCalled", "human")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z")]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 2_000_000)]})

    result = report.build_report(SPEC_ID)

    assert [r["dealer_name"] for r in result["rows"]] == ["Alpha"]


def test_no_quotes_at_all_returns_empty_recommendation(monkeypatch):
    dealers = [_dealer("d1", "Alpha", "firm")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z", outcome="declined")]
    _wire(monkeypatch, dealers, calls, {})

    result = report.build_report(SPEC_ID)

    assert result["recommended_dealer_id"] is None
    assert "nothing to rank" in result["recommendation_text"]


# --- rounds --------------------------------------------------------------

def test_latest_round_with_a_quote_wins(monkeypatch):
    """Round 2 is the leverage round — its concession is the dealer's real position."""
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [
        _call("c1", "d1", 1, "2026-01-01T10:00:00Z"),
        _call("c2", "d1", 2, "2026-01-01T12:00:00Z"),
    ]
    quotes = {"c1": [_quote("c1", "d1", 1_655_000)], "c2": [_quote("c2", "d1", 1_460_000)]}
    _wire(monkeypatch, dealers, calls, quotes)

    row = report.build_report(SPEC_ID)["rows"][0]

    assert row["round"] == 2
    assert row["quote"]["total_first_year"] == 1_460_000
    assert row["call_number"] == 2


def test_falls_back_to_earlier_quoted_round_when_latest_call_has_none(monkeypatch):
    """A round-2 callback that produced nothing must not erase the round-1 quote."""
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [
        _call("c1", "d1", 1, "2026-01-01T10:00:00Z"),
        _call("c2", "d1", 2, "2026-01-01T12:00:00Z", outcome="callback"),
    ]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 1_655_000)]})

    row = report.build_report(SPEC_ID)["rows"][0]

    assert row["round"] == 1
    assert row["quote"]["total_first_year"] == 1_655_000


def test_last_quote_on_a_call_wins(monkeypatch):
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z")]
    quotes = {"c1": [_quote("c1", "d1", 2_000_000), _quote("c1", "d1", 1_800_000)]}
    _wire(monkeypatch, dealers, calls, quotes)

    assert report.build_report(SPEC_ID)["rows"][0]["quote"]["total_first_year"] == 1_800_000


# --- citations -----------------------------------------------------------

def test_call_number_is_stable_and_ordered_by_start_time(monkeypatch):
    dealers = [_dealer("d1", "Alpha", "firm"), _dealer("d2", "Beta", "upseller")]
    # deliberately out of chronological order in the list
    calls = [
        _call("c2", "d2", 1, "2026-01-01T11:00:00Z"),
        _call("c1", "d1", 1, "2026-01-01T09:00:00Z"),
    ]
    quotes = {"c1": [_quote("c1", "d1", 2_000_000)], "c2": [_quote("c2", "d2", 3_000_000)]}
    _wire(monkeypatch, dealers, calls, quotes)

    numbers = {r["dealer_name"]: r["call_number"] for r in report.build_report(SPEC_ID)["rows"]}
    assert numbers == {"Alpha": 1, "Beta": 2}


def test_citation_points_at_dealer_line_stating_the_rent(monkeypatch):
    transcript = [
        {"line": 1, "speaker": "negotiator", "text": "What is the monthly rent?"},
        {"line": 2, "speaker": "dealer", "text": "For that shop it is 120,000 per month."},
        {"line": 3, "speaker": "dealer", "text": "Rent is 100,000 per month, final."},
        {"line": 4, "speaker": "negotiator", "text": "Understood."},
    ]
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z", transcript=transcript)]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 1_460_000, rent=100000)]})

    assert report.build_report(SPEC_ID)["rows"][0]["citation_line"] == 3


def test_citation_falls_back_to_last_dealer_line(monkeypatch):
    transcript = [
        {"line": 1, "speaker": "negotiator", "text": "Rent?"},
        {"line": 2, "speaker": "dealer", "text": "The unit is already rented out."},
    ]
    dealers = [_dealer("d1", "Stonewall", "stonewaller")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z", outcome="declined", transcript=transcript)]
    _wire(monkeypatch, dealers, calls, {})

    assert report.build_report(SPEC_ID)["rows"][0]["citation_line"] == 2


def test_citation_defaults_to_one_for_empty_transcript(monkeypatch):
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z", transcript=None)]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 2_000_000)]})

    assert report.build_report(SPEC_ID)["rows"][0]["citation_line"] == 1


# --- recommendation text -------------------------------------------------

def test_recommendation_states_only_figures_that_exist(monkeypatch):
    dealers = [_dealer("d1", "Firm", "firm"), _dealer("d2", "Upsell", "upseller")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z"), _call("c2", "d2", 1, "2026-01-01T11:00:00Z")]
    quotes = {
        "c1": [_quote("c1", "d1", 1_460_000, rent=100000)],
        "c2": [_quote("c2", "d2", 1_800_000, rent=130000)],
    }
    _wire(monkeypatch, dealers, calls, quotes)

    text = report.build_report(SPEC_ID)["recommendation_text"]

    assert "PKR 1,460,000" in text
    assert "[call 1, line 1]" in text
    assert "PKR 340,000 under the next clean offer from Upsell" in text


def test_recommendation_warns_when_top_quote_is_not_binding(monkeypatch):
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z")]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 1_460_000, binding=None)]})

    assert "in writing" in report.build_report(SPEC_ID)["recommendation_text"]


# --- recordings ----------------------------------------------------------

def test_recording_url_is_signed(monkeypatch):
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z", recording="c1.wav")]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 2_000_000)]})

    assert report.build_report(SPEC_ID)["rows"][0]["recording_url"] == "https://signed/c1.wav"


def test_signing_failure_does_not_break_the_report(monkeypatch):
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z", recording="c1.wav")]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 2_000_000)]})

    def boom(path, **kw):
        raise RuntimeError("bucket gone")

    monkeypatch.setattr(report.storage, "signed_recording_url", boom)

    result = report.build_report(SPEC_ID)
    assert result["rows"][0]["recording_url"] is None
    assert result["rows"][0]["rank"] == 1


# --- endpoint auth -------------------------------------------------------

def test_report_requires_auth():
    assert client.get(f"/report/{SPEC_ID}").status_code == 401


def test_report_404s_for_non_owner(monkeypatch):
    _wire(monkeypatch, [], [], {}, spec_owner=USER_A)
    _as(USER_B)
    assert client.get(f"/report/{SPEC_ID}").status_code == 404


def test_report_404s_for_unknown_spec(monkeypatch):
    _wire(monkeypatch, [], [], {})
    _as(USER_A)
    assert client.get("/report/nope").status_code == 404


def test_report_endpoint_returns_report_for_owner(monkeypatch):
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z")]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 1_460_000)]})
    _as(USER_A)

    response = client.get(f"/report/{SPEC_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["spec_id"] == SPEC_ID
    assert body["recommended_dealer_id"] == "d1"
    assert body["rows"][0]["rank"] == 1


def test_stale_callback_outcome_is_corrected_by_the_quote_row(monkeypatch):
    """Rows written before outcome derivation trusted the quotes table can say
    "callback" while carrying a real quote. The report shows what actually
    happened rather than repeating the stale verdict."""
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z", outcome="callback")]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 1_460_000)]})

    row = report.build_report(SPEC_ID)["rows"][0]

    assert row["outcome"] == "quote"
    assert row["rank"] == 1


def test_declined_outcome_survives_when_there_is_no_quote(monkeypatch):
    dealers = [_dealer("d1", "Stonewall", "stonewaller")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z", outcome="declined")]
    _wire(monkeypatch, dealers, calls, {})

    row = report.build_report(SPEC_ID)["rows"][0]

    assert row["outcome"] == "declined"
    assert row["rank"] is None


# --- multiple properties per dealer ---------------------------------------

def test_two_properties_from_one_dealer_produce_two_ranked_rows(monkeypatch):
    dealers = [_dealer("d1", "Multi", "upseller")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z")]
    quotes = {
        "c1": [
            _quote("c1", "d1", 2_000_000, property_ref="Shop 2"),
            _quote("c1", "d1", 1_500_000, property_ref="Shop 7"),
        ],
    }
    _wire(monkeypatch, dealers, calls, quotes)

    result = report.build_report(SPEC_ID)
    rows = [r for r in result["rows"] if r["dealer_id"] == "d1"]

    assert len(rows) == 2
    assert len({r["row_id"] for r in rows}) == 2
    assert {r["property_ref"] for r in rows} == {"Shop 2", "Shop 7"}
    assert sorted(r["rank"] for r in rows) == [1, 2]

    cheapest = next(r for r in rows if r["property_ref"] == "Shop 7")
    assert result["recommended_row_id"] == cheapest["row_id"]
    assert result["recommended_dealer_id"] == "d1"


def test_round2_revision_of_one_property_does_not_erase_other_property(monkeypatch):
    """A follow-up call scoped to one shop must not blank out a sibling shop's quote."""
    dealers = [_dealer("d1", "Multi", "upseller")]
    calls = [
        _call("c1", "d1", 1, "2026-01-01T10:00:00Z"),
        _call("c2", "d1", 2, "2026-01-01T12:00:00Z"),
    ]
    quotes = {
        "c1": [
            _quote("c1", "d1", 2_000_000, property_ref="Shop 2"),
            _quote("c1", "d1", 1_500_000, property_ref="Shop 7"),
        ],
        "c2": [_quote("c2", "d1", 1_800_000, property_ref="Shop 2")],
    }
    _wire(monkeypatch, dealers, calls, quotes)

    rows = report.build_report(SPEC_ID)["rows"]
    by_ref = {r["property_ref"]: r for r in rows}

    assert by_ref["Shop 2"]["quote"]["total_first_year"] == 1_800_000
    assert by_ref["Shop 2"]["round"] == 2
    assert by_ref["Shop 7"]["quote"]["total_first_year"] == 1_500_000
    assert by_ref["Shop 7"]["round"] == 1


def test_single_property_dealer_row_id_and_property_ref_unaffected(monkeypatch):
    """Back-compat: a dealer with no property_ref still gets exactly one row."""
    dealers = [_dealer("d1", "Firm", "firm")]
    calls = [_call("c1", "d1", 1, "2026-01-01T10:00:00Z")]
    _wire(monkeypatch, dealers, calls, {"c1": [_quote("c1", "d1", 1_460_000)]})

    rows = report.build_report(SPEC_ID)["rows"]

    assert len(rows) == 1
    assert rows[0]["property_ref"] is None
    assert rows[0]["row_id"] == "d1:"
