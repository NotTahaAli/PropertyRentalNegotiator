from app.agent_factory import (
    build_agents,
    build_client_tool_schemas,
    build_dynamic_variable_names,
    build_negotiator_prompt,
    build_tool_schemas,
)
from app.vertical import load_vertical


def test_dynamic_variable_names_cover_every_spec_field_plus_currency():
    config = load_vertical()
    names = build_dynamic_variable_names(config)
    assert set(config.spec_schema.keys()) <= set(names)
    assert "currency" in names


def test_negotiator_prompt_references_every_required_spec_field():
    config = load_vertical()
    prompt = build_negotiator_prompt(config)
    for name, field in config.spec_schema.items():
        if field.required:
            assert f"{{{{{name}}}}}" in prompt


def test_negotiator_prompt_appended_brief_has_no_bid_or_quote_variables():
    config = load_vertical()
    prompt = build_negotiator_prompt(config)
    brief = prompt.split("--- CLIENT BRIEF")[1]
    assert "bid" not in brief.lower()
    assert "quote" not in brief.lower()


def test_log_quote_tool_body_covers_every_fee_taxonomy_item():
    config = load_vertical()
    tools = build_tool_schemas(config)
    log_quote = next(t for t in tools if t["name"] == "log_quote")
    props = log_quote["api_schema"]["request_body_schema"]["properties"]
    assert set(config.fee_taxonomy) <= set(props.keys())
    for fee in config.fee_taxonomy:
        assert props[fee]["type"] == "number"


def test_log_quote_has_optional_property_ref_param():
    """A dealer with several matching shops needs a way to discriminate quotes;
    it must stay optional so a single-property dealer's flow is unaffected."""
    config = load_vertical()
    tools = build_tool_schemas(config)
    log_quote = next(t for t in tools if t["name"] == "log_quote")
    props = log_quote["api_schema"]["request_body_schema"]["properties"]
    required = set(log_quote["api_schema"]["request_body_schema"]["required"])
    assert "property_ref" in props
    assert props["property_ref"]["type"] == "string"
    assert "property_ref" not in required


def test_log_quote_allows_partial_quotes():
    # Partial quotes are logged the moment the first real number lands and
    # updated by calling log_quote again — so only the ids (plus monthly_rent,
    # which QuoteCreate hard-requires) may be schema-required. An unconfirmed
    # binding stays False → no_written_quote flag → excluded from leverage, so
    # partial quotes can't leak into leverage before they're confirmed.
    config = load_vertical()
    tools = build_tool_schemas(config)
    log_quote = next(t for t in tools if t["name"] == "log_quote")
    required = set(log_quote["api_schema"]["request_body_schema"]["required"])
    assert required == {"monthly_rent", "call_id", "dealer_id"}
    assert "update" in log_quote["description"].lower()


def test_negotiator_prompt_instructs_asking_for_written_quote():
    config = load_vertical()
    assert "writing" in config.negotiator_prompt.lower()


def test_get_leverage_and_get_benchmark_bodies_exclude_fee_taxonomy():
    config = load_vertical()
    tools = build_tool_schemas(config)
    by_name = {t["name"]: t for t in tools}
    for name in ("get_leverage", "get_benchmark"):
        props = by_name[name]["api_schema"]["request_body_schema"]["properties"]
        assert not (set(config.fee_taxonomy) & set(props.keys()))
        assert "spec_id" in props


def test_get_leverage_requires_dealer_id():
    config = load_vertical()
    tools = build_tool_schemas(config)
    get_leverage = next(t for t in tools if t["name"] == "get_leverage")
    schema = get_leverage["api_schema"]["request_body_schema"]
    assert "dealer_id" in schema["properties"]
    assert set(schema["required"]) == {"spec_id", "dealer_id"}


def test_build_tool_schemas_returns_exactly_four_tools():
    config = load_vertical()
    names = {t["name"] for t in build_tool_schemas(config)}
    assert names == {"log_quote", "get_leverage", "check_redflag", "get_benchmark"}


def test_build_agents_returns_six_agents_only_negotiator_has_tools():
    config = load_vertical()
    agents = build_agents(config)
    assert len(agents) == 6
    by_name = {a.name: a for a in agents}
    assert set(by_name) == {
        "estimator",
        "negotiator",
        "stonewaller",
        "lowballer",
        "upseller",
        "firm",
    }
    assert by_name["negotiator"].tool_names == [
        "log_quote",
        "get_leverage",
        "check_redflag",
        "get_benchmark",
    ]
    for persona in ("stonewaller", "lowballer", "upseller", "firm"):
        assert by_name[persona].tool_names == []


def test_set_spec_field_client_tool_covers_every_spec_field_typed():
    config = load_vertical()
    tools = build_client_tool_schemas(config)
    assert [t["name"] for t in tools] == ["set_spec_field"]
    tool = tools[0]
    assert tool["type"] == "client"
    assert tool["expects_response"] is False
    props = tool["parameters"]["properties"]
    assert set(props.keys()) == set(config.spec_schema.keys())
    assert tool["parameters"]["required"] == []
    assert props["area_sqft"]["type"] == "number"
    assert props["parking"]["type"] == "boolean"
    assert props["floor"]["type"] == "string"
    for value in config.spec_schema["floor"].values:
        assert value in props["floor"]["description"]
    assert "YYYY-MM-DD" in props["move_in"]["description"]


def test_everyone_on_the_bridge_gets_end_call():
    # Negotiator must be able to hang up — without it a bridge call has no
    # terminator and loops goodbyes forever (live bug once the 3:00 cap was
    # removed). Personas also get end_call: the negotiator normally drives
    # closure, but a persona needs to be able to hang up too if the negotiator
    # stalls, so neither side can loop forever.
    config = load_vertical()
    by_name = {a.name: a for a in build_agents(config)}
    assert by_name["estimator"].tool_names == ["set_spec_field"]
    assert by_name["estimator"].end_call is True
    assert by_name["negotiator"].end_call is True
    for persona in ("stonewaller", "lowballer", "upseller", "firm"):
        assert by_name[persona].end_call is True


def test_build_agents_uses_configured_llm_split():
    config = load_vertical()
    agents = build_agents(config)
    by_name = {a.name: a for a in agents}
    assert by_name["estimator"].llm == "gpt-5.4-mini"
    assert by_name["negotiator"].llm == "gpt-5.4-mini"
    for persona in ("stonewaller", "lowballer", "upseller", "firm"):
        assert by_name[persona].llm == "gemini-3.1-flash-lite"
