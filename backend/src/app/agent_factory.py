from dataclasses import dataclass, field

from app.vertical import VerticalConfig

EXTRACTION_LLM = "gpt-5.4-mini"
PERSONA_LLM = "gemini-3.1-flash-lite"

PERSONA_NAMES = ["stonewaller", "lowballer", "upseller", "firm"]

NEGOTIATOR_TOOL_NAMES = ["log_quote", "get_leverage", "check_redflag", "get_benchmark", "log_call_status"]

# Every outcome the negotiator can explicitly log via log_call_status. Kept next
# to the tool schema builder so the enum offered to the LLM and the values the
# backend accepts (tools.py) can't drift apart.
CALL_OUTCOMES = ["quote", "final_quote", "vague_quote", "declined", "callback"]


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
    # Call history: the dealer's OWN prior quote and how the last call ended.
    # Without this the agent re-opens every follow-up from scratch and asks a
    # dealer to repeat a quote it already gave. Deliberately scoped to this one
    # dealer — competing bids stay behind get_leverage, see the honesty guardrail.
    lines.append("")
    lines.append("--- CALL HISTORY WITH THIS DEALER ---")
    lines.append("This is call number {{round_number}} with them.")
    lines.append("{{prior_call_summary}}")
    return config.negotiator_prompt + "\n\n" + "\n".join(lines)


def _fee_property(fee_name: str, fee_hints: dict[str, str]) -> dict:
    return {
        "type": "number",
        "description": fee_hints.get(fee_name, fee_name.replace("_", " ")),
    }


def _id_property(dynamic_variable: str) -> dict:
    """A call/dealer/spec id, auto-filled by ElevenLabs from the named dynamic
    variable set at conversation start (api._dynamic_variables) instead of being
    typed by the LLM.

    Every id was previously LLM-supplied free text ("Current call id.") even
    though the model was never shown the actual value anywhere in its prompt or
    context — it had no way to know the real UUID, so it either omitted the
    required field or invented one, and log_quote/get_leverage/check_redflag/
    get_benchmark calls failed silently (tools are prompted as invisible, so the
    agent never surfaced or retried the failure). Binding these to
    `dynamic_variable` removes the LLM from the loop entirely for values it can
    never actually know.
    """
    return {"type": "string", "dynamic_variable": dynamic_variable}


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
            "call_id": _id_property("call_id"),
            "dealer_id": _id_property("dealer_id"),
            "property_ref": {
                "type": "string",
                "description": "Identifier of the specific shop/unit this quote is for (e.g. "
                "'Shop 4, Ground Floor'). Pass the same value on every log_quote update for that "
                "shop. Omit entirely if the dealer has only one matching property.",
            },
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
            "spec_id": _id_property("spec_id"),
        },
        required=["spec_id"],
    )

    get_leverage = _webhook_tool(
        "get_leverage",
        "Returns the best real quotes logged so far for this spec, each tagged with the "
        "property it's for. Empty if none exist yet.",
        {
            "spec_id": _id_property("spec_id"),
            "dealer_id": _id_property("dealer_id"),
        },
        required=["spec_id", "dealer_id"],
    )

    get_benchmark = _webhook_tool(
        "get_benchmark",
        "Returns the cached market rent benchmark for this spec's location.",
        {"spec_id": _id_property("spec_id")},
        required=["spec_id"],
    )

    log_call_status = _webhook_tool(
        "log_call_status",
        "Records how this call ended. Call it exactly once, right before you hang up, "
        "with the outcome that best matches what actually happened: "
        "'quote' — you got numbers but the call isn't fully resolved yet; "
        "'final_quote' — the dealer gave a complete itemised quote and confirmed it is their "
        "final, non-negotiable offer; "
        "'vague_quote' — the dealer gave real verbal numbers but would not confirm them in "
        "writing (send binding=false via log_quote too); "
        "'callback' — the dealer could not give numbers now and agreed to a specific follow-up "
        "(pass callback_at with the concrete time they committed to, e.g. 'tomorrow 4pm' or an "
        "ISO datetime, never a vague 'later'); "
        "'declined' — the dealer said the unit is unavailable or they are not interested.",
        {
            "call_id": _id_property("call_id"),
            "outcome": {
                "type": "string",
                "enum": CALL_OUTCOMES,
                "description": "How the call ended. One of: " + ", ".join(CALL_OUTCOMES) + ".",
            },
            "callback_at": {
                "type": "string",
                "description": "Only for outcome=callback: the concrete time the dealer committed to.",
            },
            "notes": {
                "type": "string",
                "description": "Brief context for the outcome, e.g. why the dealer declined.",
            },
        },
        required=["call_id", "outcome"],
    )

    return [log_quote, get_leverage, check_redflag, get_benchmark, log_call_status]


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
                # Persona hangs up when its own goodbye line is done, instead of
                # relying solely on the negotiator to end the call.
                end_call=True,
            )
        )
    return agents
