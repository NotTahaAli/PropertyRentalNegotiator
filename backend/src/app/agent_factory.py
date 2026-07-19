from dataclasses import dataclass, field

from app.vertical import VerticalConfig

EXTRACTION_LLM = "gpt-5.4-mini"
PERSONA_LLM = "gemini-3.1-flash-lite"

PERSONA_NAMES = ["stonewaller", "lowballer", "upseller", "firm"]

NEGOTIATOR_TOOL_NAMES = ["log_quote", "get_leverage", "check_redflag", "get_benchmark"]


@dataclass
class AgentDef:
    name: str
    prompt: str
    first_message: str
    llm: str
    tool_names: list[str] = field(default_factory=list)
    # K5's bridge suppresses the negotiator leg's first_message per-conversation (dealer
    # answers the phone first, like a real call); ElevenLabs rejects that override
    # unless the agent explicitly allows it.
    allow_first_message_override: bool = False
    # Grants the built-in end_call system tool (estimator hangs up after confirmation).
    end_call: bool = False


def build_dynamic_variable_names(config: VerticalConfig) -> list[str]:
    return [*config.spec_schema.keys(), "currency"]


def build_negotiator_prompt(config: VerticalConfig) -> str:
    lines = ["--- CLIENT BRIEF (do not repeat verbatim; pitch naturally) ---"]
    for name, spec_field in config.spec_schema.items():
        marker = "" if spec_field.required else " (if known)"
        lines.append(f"{name}: {{{{{name}}}}}{marker}")
    lines.append("currency: {{currency}}")
    return config.negotiator_prompt + "\n\n" + "\n".join(lines)


def _fee_property(fee_name: str, fee_hints: dict[str, str]) -> dict:
    return {
        "type": "number",
        "description": fee_hints.get(fee_name, fee_name.replace("_", " ")),
    }


def _webhook_tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "webhook",
        "name": name,
        "description": description,
        "api_schema": {
            "url": f"/tools/{name}",
            "method": "POST",
            "request_body_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def build_tool_schemas(config: VerticalConfig) -> list[dict]:
    fee_properties = {fee: _fee_property(fee, config.fee_hints) for fee in config.fee_taxonomy}

    log_quote = _webhook_tool(
        "log_quote",
        "Logs the quote mid-call. Call it the moment the dealer gives the first real number, "
        "even if the quote is still partial — then call it again as more numbers arrive; "
        "repeat calls update the same quote and earlier fields are kept.",
        {
            **fee_properties,
            "call_id": {"type": "string", "description": "Current call id."},
            "dealer_id": {"type": "string", "description": "Current dealer id."},
            "binding": {"type": "boolean", "description": "Whether the dealer can produce a written quote. Send true as soon as they confirm it."},
            "notes": {"type": "string", "description": "Any other relevant detail about the quote or the property."},
        },
        # Partial quotes allowed: only the ids (plus monthly_rent, which QuoteCreate
        # hard-requires) are schema-required. binding stays optional — while it's
        # unconfirmed the quote carries the no_written_quote flag and get_leverage
        # excludes it, so a partial quote can't leak into leverage early.
        required=[
            *(["monthly_rent"] if "monthly_rent" in config.fee_taxonomy else []),
            "call_id",
            "dealer_id",
        ],
    )

    redflag_fees = [f for f in ("monthly_rent", "advance_months") if f in fee_properties]
    check_redflag = _webhook_tool(
        "check_redflag",
        "Checks a quote against the benchmark and red-flag rules; may ask you to confirm scope live on the call.",
        {
            **{fee: fee_properties[fee] for fee in redflag_fees},
            "binding": {"type": "boolean", "description": "Whether the dealer can produce a written quote."},
            "spec_id": {"type": "string", "description": "Current client spec id."},
        },
        required=["spec_id"],
    )

    get_leverage = _webhook_tool(
        "get_leverage",
        "Returns the best real quotes logged so far for this spec. Empty if none exist yet.",
        {
            "spec_id": {"type": "string", "description": "Current client spec id."},
            "dealer_id": {"type": "string", "description": "Current dealer id (their own quotes are excluded)."},
        },
        required=["spec_id", "dealer_id"],
    )

    get_benchmark = _webhook_tool(
        "get_benchmark",
        "Returns the cached market rent benchmark for this spec's location.",
        {"spec_id": {"type": "string", "description": "Current client spec id."}},
        required=["spec_id"],
    )

    return [log_quote, get_leverage, check_redflag, get_benchmark]


_SPEC_JSON_TYPES = {"number": "number", "string": "string", "enum": "string", "bool": "boolean", "date": "string"}


def build_client_tool_schemas(config: VerticalConfig) -> list[dict]:
    properties = {}
    for name, spec_field in config.spec_schema.items():
        description = spec_field.prompt or name.replace("_", " ")
        if spec_field.type == "enum" and spec_field.values:
            description += " One of: " + ", ".join(spec_field.values) + "."
        if spec_field.type == "date":
            description += " Format YYYY-MM-DD."
        properties[name] = {"type": _SPEC_JSON_TYPES[spec_field.type], "description": description}
    return [
        {
            "type": "client",
            "name": "set_spec_field",
            "description": (
                "Record spec fields in the client's form. Call immediately after every answer "
                "with the field(s) just learned; send only fields the client actually stated."
            ),
            "parameters": {"type": "object", "properties": properties, "required": []},
            "expects_response": False,
        }
    ]


def build_agents(config: VerticalConfig) -> list[AgentDef]:
    agents = [
        AgentDef(
            name="estimator",
            prompt=config.estimator_prompt,
            first_message=config.first_messages["estimator"],
            llm=EXTRACTION_LLM,
            tool_names=["set_spec_field"],
            end_call=True,
        ),
        AgentDef(
            name="negotiator",
            prompt=build_negotiator_prompt(config),
            first_message=config.first_messages["negotiator"],
            llm=EXTRACTION_LLM,
            tool_names=list(NEGOTIATOR_TOOL_NAMES),
            allow_first_message_override=True,
            # Without this the bridge call has no terminator: neither leg can
            # hang up and the goodbye loops forever (was masked by the old
            # 3:00 hard cap). The negotiator owns call closure.
            end_call=True,
        ),
    ]
    for persona in PERSONA_NAMES:
        agents.append(
            AgentDef(
                name=persona,
                prompt=config.persona_prompts[persona],
                first_message=config.first_messages[persona],
                llm=PERSONA_LLM,
            )
        )
    return agents
