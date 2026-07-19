import argparse
import json
import os
from pathlib import Path

from app.agent_factory import build_agents, build_client_tool_schemas, build_tool_schemas
from app.vertical import DEFAULT_CONFIG_PATH, VerticalConfig, load_vertical

DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "agents.generated.json"

# K5 bridges two agents over WS; both must speak the same PCM rate (no per-conversation
# override exists in the API — verified against the elevenlabs SDK's override types).
AUDIO_FORMAT = "pcm_16000"


def _property_to_schema(prop: dict):
    from elevenlabs.types import LiteralJsonSchemaProperty

    return LiteralJsonSchemaProperty(type=prop["type"], description=prop["description"])


def _tool_schema_to_request(tool: dict, backend_base_url: str):
    from elevenlabs.types import (
        ObjectJsonSchemaPropertyInput,
        ToolRequestModel,
        ToolRequestModelToolConfig_Client,
        ToolRequestModelToolConfig_Webhook,
        WebhookToolApiSchemaConfigInput,
    )

    if tool["type"] == "client":
        # No secret header: client tools run in the browser, never hit the backend.
        parameters = ObjectJsonSchemaPropertyInput(
            type="object",
            required=tool["parameters"]["required"],
            properties={k: _property_to_schema(v) for k, v in tool["parameters"]["properties"].items()},
        )
        tool_config = ToolRequestModelToolConfig_Client(
            name=tool["name"],
            description=tool["description"],
            parameters=parameters,
            expects_response=tool["expects_response"],
        )
        return ToolRequestModel(tool_config=tool_config)

    body = tool["api_schema"]["request_body_schema"]
    request_body_schema = ObjectJsonSchemaPropertyInput(
        type="object",
        required=body["required"],
        properties={k: _property_to_schema(v) for k, v in body["properties"].items()},
    )
    api_schema = WebhookToolApiSchemaConfigInput(
        url=backend_base_url.rstrip("/") + tool["api_schema"]["url"],
        method=tool["api_schema"]["method"],
        request_body_schema=request_body_schema,
        # KeyError on purpose: registering tools without the secret would leave them
        # unable to call the backend (tools.py fails closed).
        request_headers={"X-Tools-Secret": os.environ["TOOLS_WEBHOOK_SECRET"]},
    )
    tool_config = ToolRequestModelToolConfig_Webhook(
        name=tool["name"],
        description=tool["description"],
        api_schema=api_schema,
    )
    return ToolRequestModel(tool_config=tool_config)


def _platform_settings(agent_def):
    if not agent_def.allow_first_message_override:
        return None

    from elevenlabs.types import (
        AgentConfigOverrideConfig,
        AgentPlatformSettingsRequestModel,
        ConversationConfigClientOverrideConfigInput,
        ConversationInitiationClientDataConfigInput,
    )

    return AgentPlatformSettingsRequestModel(
        overrides=ConversationInitiationClientDataConfigInput(
            conversation_config_override=ConversationConfigClientOverrideConfigInput(
                agent=AgentConfigOverrideConfig(first_message=True)
            )
        )
    )


def _agent_def_to_conversation_config(agent_def, tool_ids: dict):
    from elevenlabs.types import (
        AgentConfig,
        AsrConversationalConfig,
        BuiltInToolsOutput,
        ConversationalConfig,
        PromptAgentApiModelOutput,
        SystemToolConfigOutput,
        SystemToolConfigOutputParams_EndCall,
        TtsConversationalConfigOutput,
    )

    prompt_kwargs = {}
    if agent_def.end_call:
        # server's BuiltInTools entries need an extra "type": "system" discriminator, and
        # the field must be omitted entirely (not null) when unused — both verified live
        prompt_kwargs["built_in_tools"] = BuiltInToolsOutput(
            end_call=SystemToolConfigOutput(
                name="end_call",
                params=SystemToolConfigOutputParams_EndCall(),
                type="system",
            )
        )
    prompt = PromptAgentApiModelOutput(
        prompt=agent_def.prompt,
        llm=agent_def.llm,
        tool_ids=[tool_ids[name] for name in agent_def.tool_names],
        **prompt_kwargs,
    )
    agent_config = AgentConfig(first_message=agent_def.first_message, prompt=prompt)
    return ConversationalConfig(
        agent=agent_config,
        tts=TtsConversationalConfigOutput(agent_output_audio_format=AUDIO_FORMAT),
        asr=AsrConversationalConfig(user_input_audio_format=AUDIO_FORMAT),
    )


def _find_existing_tool_id(client, name: str) -> str | None:
    for tool in client.conversational_ai.tools.list(search=name).tools:
        if getattr(tool.tool_config, "name", None) == name:
            return tool.id
    return None


def _find_existing_agent_id(client, name: str) -> str | None:
    for agent in client.conversational_ai.agents.list(search=name).agents:
        if agent.name == name:
            return agent.agent_id
    return None


def upsert_all(
    client,
    config: VerticalConfig,
    manifest: dict,
    backend_base_url: str,
    manifest_path: Path | None = None,
) -> dict:
    tool_ids: dict[str, str] = dict(manifest.get("tools", {}))
    agent_ids: dict[str, str] = dict(manifest.get("agents", {}))

    def _save() -> None:
        if manifest_path is not None:
            manifest_path.write_text(json.dumps({"tools": tool_ids, "agents": agent_ids}, indent=2))

    for tool in build_tool_schemas(config) + build_client_tool_schemas(config):
        request = _tool_schema_to_request(tool, backend_base_url)
        # manifest may be lost/missing (fresh checkout) -- check ElevenLabs by name before creating a duplicate
        existing_id = tool_ids.get(tool["name"]) or _find_existing_tool_id(client, tool["name"])
        if existing_id:
            client.conversational_ai.tools.update(existing_id, request=request)
            tool_ids[tool["name"]] = existing_id
        else:
            resp = client.conversational_ai.tools.create(request=request)
            tool_ids[tool["name"]] = resp.tool_id if hasattr(resp, "tool_id") else resp.id
        _save()

    for agent_def in build_agents(config):
        conversation_config = _agent_def_to_conversation_config(agent_def, tool_ids)
        platform_settings = _platform_settings(agent_def)
        kwargs = {"conversation_config": conversation_config, "name": agent_def.name}
        if platform_settings is not None:
            kwargs["platform_settings"] = platform_settings
        existing_id = agent_ids.get(agent_def.name) or _find_existing_agent_id(client, agent_def.name)
        if existing_id:
            client.conversational_ai.agents.update(existing_id, **kwargs)
            agent_ids[agent_def.name] = existing_id
        else:
            resp = client.conversational_ai.agents.create(**kwargs)
            agent_ids[agent_def.name] = resp.agent_id
        _save()

    return {"tools": tool_ids, "agents": agent_ids}


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Create/update all ElevenLabs agents from vertical.json")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--backend-base-url", default=os.environ.get("BACKEND_BASE_URL", "http://localhost:8000"))
    args = parser.parse_args()

    from elevenlabs.client import ElevenLabs

    config = load_vertical(args.config)
    manifest = json.loads(args.manifest.read_text()) if args.manifest.exists() else {}
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

    result = upsert_all(client, config, manifest, args.backend_base_url, manifest_path=args.manifest)

    for kind in ("tools", "agents"):
        for name, id_ in result[kind].items():
            print(f"{kind[:-1]}: {name} -> {id_}")


if __name__ == "__main__":
    main()
