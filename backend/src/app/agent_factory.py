from dataclasses import dataclass, field

from app.vertical import VerticalConfig

EXTRACTION_LLM = "gpt-5.4-mini"
PERSONA_LLM = "gemini-3.1-flash-lite"

PERSONA_NAMES = ["stonewaller", "lowballer", "upseller", "firm"]

NEGOTIATOR_TOOL_NAMES = ["log_quote", "get_leverage", "check_redflag", "get_benchmark"]

FEE_HINTS = {
    "monthly_rent": "Monthly rent in the client's currency, as quoted by the dealer.",
    "advance_months": "Number of months' rent required as an upfront advance.",
    "commission": "One-time dealer commission fee.",
    "maintenance": "Monthly maintenance/society charges.",
    "annual_increment_pct": "Annual rent increment, as a percentage.",
}

FIRST_MESSAGES = {
    "estimator": "Hi! I'll help you describe the shop you're looking to rent. Ready to get started?",
    "negotiator": "Assalam-o-Alaikum, I'm calling on behalf of a client who is looking to rent a commercial shop.",
    "stonewaller": "Yes hello, dealer speaking.",
    "lowballer": "Hello ji, how can I help you?",
    "upseller": "Good day, I have some excellent properties available.",
    "firm": "Hello, thank you for calling. How may I assist you?",
}


@dataclass
class AgentDef:
    name: str
    prompt: str
    first_message: str
    llm: str
    tool_names: list[str] = field(default_factory=list)
    # K5's bridge suppresses the dealer leg's first_message per-conversation (Negotiator
    # opens); ElevenLabs rejects that override unless the agent explicitly allows it.
    allow_first_message_override: bool = False


def build_dynamic_variable_names(config: VerticalConfig) -> list[str]:
    return [*config.spec_schema.keys(), "currency"]


def build_negotiator_prompt(config: VerticalConfig) -> str:
    lines = ["--- CLIENT BRIEF (do not repeat verbatim; pitch naturally) ---"]
    for name, spec_field in config.spec_schema.items():
        marker = "" if spec_field.required else " (if known)"
        lines.append(f"{name}: {{{{{name}}}}}{marker}")
    lines.append("currency: {{currency}}")
    return config.negotiator_prompt + "\n\n" + "\n".join(lines)


def _fee_property(fee_name: str) -> dict:
    return {
        "type": "number",
        "description": FEE_HINTS.get(fee_name, fee_name.replace("_", " ")),
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
    fee_properties = {fee: _fee_property(fee) for fee in config.fee_taxonomy}

    log_quote = _webhook_tool(
        "log_quote",
        "Writes an itemised quote row mid-call. Call this as soon as the dealer gives real numbers.",
        {
            **fee_properties,
            "call_id": {"type": "string", "description": "Current call id."},
            "dealer_id": {"type": "string", "description": "Current dealer id."},
            "binding": {"type": "boolean", "description": "Whether the dealer can produce a written quote."},
            "notes": {"type": "string", "description": "Any other relevant detail about the quote."},
        },
        required=[*config.fee_taxonomy, "call_id", "dealer_id"],
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
        {"spec_id": {"type": "string", "description": "Current client spec id."}},
        required=["spec_id"],
    )

    get_benchmark = _webhook_tool(
        "get_benchmark",
        "Returns the cached market rent benchmark for this spec's location.",
        {"spec_id": {"type": "string", "description": "Current client spec id."}},
        required=["spec_id"],
    )

    return [log_quote, get_leverage, check_redflag, get_benchmark]


def build_agents(config: VerticalConfig) -> list[AgentDef]:
    agents = [
        AgentDef(
            name="estimator",
            prompt=config.estimator_prompt,
            first_message=FIRST_MESSAGES["estimator"],
            llm=EXTRACTION_LLM,
        ),
        AgentDef(
            name="negotiator",
            prompt=build_negotiator_prompt(config),
            first_message=FIRST_MESSAGES["negotiator"],
            llm=EXTRACTION_LLM,
            tool_names=list(NEGOTIATOR_TOOL_NAMES),
        ),
    ]
    for persona in PERSONA_NAMES:
        agents.append(
            AgentDef(
                name=persona,
                prompt=config.persona_prompts[persona],
                first_message=FIRST_MESSAGES[persona],
                llm=PERSONA_LLM,
                allow_first_message_override=True,
            )
        )
    return agents
