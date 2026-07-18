import argparse
import json
import os
from pathlib import Path

from app.agent_factory import build_agents, build_tool_schemas
from app.vertical import DEFAULT_CONFIG_PATH, VerticalConfig, load_vertical

DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "agents.generated.json"


def _property_to_schema(prop: dict):
    from elevenlabs.types import LiteralJsonSchemaProperty

    return LiteralJsonSchemaProperty(type=prop["type"], description=prop["description"])


def _tool_schema_to_request(tool: dict, backend_base_url: str):
    from elevenlabs.types import (
        ObjectJsonSchemaPropertyInput,
        ToolRequestModel,
        ToolRequestModelToolConfig_Webhook,
        WebhookToolApiSchemaConfigInput,
    )

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
    )
    tool_config = ToolRequestModelToolConfig_Webhook(
        name=tool["name"],
        description=tool["description"],
        api_schema=api_schema,
    )
    return ToolRequestModel(tool_config=tool_config)


def _agent_def_to_conversation_config(agent_def, tool_ids: dict):
    from elevenlabs.types import AgentConfig, ConversationalConfig, PromptAgentApiModelOutput

    prompt = PromptAgentApiModelOutput(
        prompt=agent_def.prompt,
        llm=agent_def.llm,
        tool_ids=[tool_ids[name] for name in agent_def.tool_names],
    )
    agent_config = AgentConfig(first_message=agent_def.first_message, prompt=prompt)
    return ConversationalConfig(agent=agent_config)


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

    for tool in build_tool_schemas(config):
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
        existing_id = agent_ids.get(agent_def.name) or _find_existing_agent_id(client, agent_def.name)
        if existing_id:
            client.conversational_ai.agents.update(existing_id, conversation_config=conversation_config, name=agent_def.name)
            agent_ids[agent_def.name] = existing_id
        else:
            resp = client.conversational_ai.agents.create(conversation_config=conversation_config, name=agent_def.name)
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
