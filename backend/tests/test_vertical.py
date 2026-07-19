import datetime

import pytest
from pydantic import ValidationError

from app.vertical import DEFAULT_CONFIG_PATH, SpecField, build_spec_model, load_vertical


def test_config_loads_and_validates():
    config = load_vertical()
    assert config.vertical == "commercial_shop_rental_pk"
    assert config.currency == "PKR"


def test_all_six_prompts_present_and_nonempty():
    config = load_vertical()
    assert config.estimator_prompt.strip()
    assert config.negotiator_prompt.strip()
    assert set(config.persona_prompts.keys()) == {
        "stonewaller",
        "lowballer",
        "upseller",
        "firm",
    }
    for prompt in config.persona_prompts.values():
        assert prompt.strip()


def test_spec_model_accepts_valid_full_spec():
    config = load_vertical()
    SpecModel = build_spec_model(config)
    spec = SpecModel(
        area_sqft=400,
        location="DHA Lahore",
        floor="ground",
        business_type="pharmacy",
        lease_years=3,
        move_in="2026-09-01",
        budget_monthly_rent=250000,
    )
    assert spec.area_sqft == 400
    assert spec.move_in == datetime.date(2026, 9, 1)


def test_spec_model_allows_unanticipated_extra_field():
    config = load_vertical()
    SpecModel = build_spec_model(config)
    spec = SpecModel(
        area_sqft=400,
        location="DHA Lahore",
        floor="ground",
        business_type="pharmacy",
        lease_years=3,
        move_in="2026-09-01",
        budget_monthly_rent=250000,
        dealer_note="has a generator",
    )
    assert spec.model_dump()["dealer_note"] == "has a generator"


def test_spec_model_rejects_missing_required_field():
    config = load_vertical()
    SpecModel = build_spec_model(config)
    with pytest.raises(ValidationError):
        SpecModel(
            location="DHA Lahore",
            floor="ground",
            business_type="pharmacy",
            lease_years=3,
            move_in="2026-09-01",
            budget_monthly_rent=250000,
        )


def test_spec_model_rejects_bad_enum_value():
    config = load_vertical()
    SpecModel = build_spec_model(config)
    with pytest.raises(ValidationError):
        SpecModel(
            area_sqft=400,
            location="DHA Lahore",
            floor="mezzanine",
            business_type="pharmacy",
            lease_years=3,
            move_in="2026-09-01",
            budget_monthly_rent=250000,
        )


def test_red_flag_thresholds_match_locked_decision():
    config = load_vertical()
    by_rule = {flag.rule: flag for flag in config.red_flags}
    assert by_rule["below_market_pct"].threshold == 30
    assert by_rule["below_market_pct"].action == "confirm_then_flag"
    assert by_rule["no_written_quote"].action == "flag"
    assert by_rule["advance_months_gt"].threshold == 6
    assert by_rule["advance_months_gt"].action == "flag"


def test_benchmark_fallback_values():
    config = load_vertical()
    assert config.benchmark_fallback.per_sqft_low == 180
    assert config.benchmark_fallback.per_sqft_high == 450


def test_build_spec_model_rejects_enum_field_missing_values():
    config = load_vertical()
    broken = config.model_copy(
        update={
            "spec_schema": {
                **config.spec_schema,
                "floor": SpecField(type="enum", required=True, values=None),
            }
        }
    )
    with pytest.raises(ValueError, match="floor"):
        build_spec_model(broken)


def test_spec_model_allows_omitting_optional_field():
    config = load_vertical()
    SpecModel = build_spec_model(config)
    spec = SpecModel(
        area_sqft=400,
        location="DHA Lahore",
        floor="ground",
        business_type="pharmacy",
        lease_years=3,
        move_in="2026-09-01",
        budget_monthly_rent=250000,
    )
    assert spec.frontage_ft is None
    assert spec.parking is None


def test_second_vertical_config_swaps_cleanly():
    # The "config not code" demo: a second vertical must validate against the same
    # model and drive the same agent factory with zero code changes.
    from app.agent_factory import build_agents, build_tool_schemas

    path = DEFAULT_CONFIG_PATH.parent / "auto_repair_pk.json"
    config = load_vertical(path)
    assert config.vertical != load_vertical().vertical
    SpecModel = build_spec_model(config)
    assert SpecModel is not None
    agents = {a.name for a in build_agents(config)}
    assert {"estimator", "negotiator", "stonewaller", "lowballer", "upseller", "firm"} <= agents
    tools = {t["name"] for t in build_tool_schemas(config)}
    assert tools == {"log_quote", "get_leverage", "check_redflag", "get_benchmark"}
