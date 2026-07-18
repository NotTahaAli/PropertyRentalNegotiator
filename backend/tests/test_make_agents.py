import json

import pytest

from app.make_agents import upsert_all
from app.vertical import load_vertical


@pytest.fixture(autouse=True)
def tools_secret(monkeypatch):
    monkeypatch.setenv("TOOLS_WEBHOOK_SECRET", "test-secret")


class FakeResource:
    def __init__(self, prefix, kind, remote=None):
        self.prefix = prefix
        self.kind = kind  # "tool" or "agent"
        self.created = []
        self.updated = []
        self.remote = dict(remote or {})  # name -> id, pre-existing remote records not in the local manifest

    def create(self, **kwargs):
        agent_id = f"{self.prefix}_{len(self.created) + len(self.updated)}"
        self.created.append((agent_id, kwargs))
        return type("Resp", (), {"agent_id": agent_id, "tool_id": agent_id, "id": agent_id})()

    def update(self, id, **kwargs):
        self.updated.append((id, kwargs))
        return type("Resp", (), {"agent_id": id, "tool_id": id, "id": id})()

    def list(self, search=None, **kwargs):
        matches = [(name, id_) for name, id_ in self.remote.items() if search is None or search == name]
        if self.kind == "tool":
            objs = [type("T", (), {"id": id_, "tool_config": type("C", (), {"name": name})()})() for name, id_ in matches]
            return type("R", (), {"tools": objs})()
        objs = [type("A", (), {"agent_id": id_, "name": name})() for name, id_ in matches]
        return type("R", (), {"agents": objs})()


class FakeConversationalAi:
    def __init__(self, remote_agents=None, remote_tools=None):
        self.agents = FakeResource("agent", "agent", remote_agents)
        self.tools = FakeResource("tool", "tool", remote_tools)


class FakeClient:
    def __init__(self, remote_agents=None, remote_tools=None):
        self.conversational_ai = FakeConversationalAi(remote_agents, remote_tools)


def test_first_run_creates_four_tools_and_six_agents():
    config = load_vertical()
    client = FakeClient()

    manifest = upsert_all(client, config, manifest={}, backend_base_url="http://x")

    assert len(client.conversational_ai.tools.created) == 4
    assert len(client.conversational_ai.agents.created) == 6
    assert len(manifest["tools"]) == 4
    assert len(manifest["agents"]) == 6


def test_every_tool_sends_shared_secret_header():
    config = load_vertical()
    client = FakeClient()

    upsert_all(client, config, manifest={}, backend_base_url="http://x")

    assert client.conversational_ai.tools.created
    for _tool_id, kwargs in client.conversational_ai.tools.created:
        headers = kwargs["request"].tool_config.api_schema.request_headers
        assert headers == {"X-Tools-Secret": "test-secret"}


def test_agents_pinned_to_pcm_16000_audio_format():
    config = load_vertical()
    client = FakeClient()

    upsert_all(client, config, manifest={}, backend_base_url="http://x")

    assert client.conversational_ai.agents.created
    for _agent_id, kwargs in client.conversational_ai.agents.created:
        cc = kwargs["conversation_config"]
        assert cc.tts.agent_output_audio_format == "pcm_16000"
        assert cc.asr.user_input_audio_format == "pcm_16000"


def test_persona_agents_allow_first_message_override_negotiator_and_estimator_do_not():
    config = load_vertical()
    client = FakeClient()

    upsert_all(client, config, manifest={}, backend_base_url="http://x")

    by_name = {}
    for agent_id, kwargs in client.conversational_ai.agents.created:
        by_name[kwargs["name"]] = kwargs

    for persona in ("stonewaller", "lowballer", "upseller", "firm"):
        settings = by_name[persona]["platform_settings"]
        assert settings.overrides.conversation_config_override.agent.first_message is True

    for other in ("negotiator", "estimator"):
        assert by_name[other].get("platform_settings") is None


def test_second_run_with_manifest_updates_instead_of_creating():
    config = load_vertical()
    client = FakeClient()
    manifest = upsert_all(client, config, manifest={}, backend_base_url="http://x")

    client2 = FakeClient()
    manifest2 = upsert_all(client2, config, manifest=manifest, backend_base_url="http://x")

    assert len(client2.conversational_ai.tools.created) == 0
    assert len(client2.conversational_ai.tools.updated) == 4
    assert len(client2.conversational_ai.agents.created) == 0
    assert len(client2.conversational_ai.agents.updated) == 6
    assert manifest2["agents"] == manifest["agents"]
    assert manifest2["tools"] == manifest["tools"]


def test_lost_manifest_reuses_remote_match_by_name_instead_of_duplicating(tmp_path):
    config = load_vertical()
    client = FakeClient(
        remote_agents={"estimator": "agent_remote_existing"},
        remote_tools={"log_quote": "tool_remote_existing"},
    )
    manifest_path = tmp_path / "agents.generated.json"

    manifest = upsert_all(client, config, manifest={}, backend_base_url="http://x", manifest_path=manifest_path)

    assert manifest["tools"]["log_quote"] == "tool_remote_existing"
    assert manifest["agents"]["estimator"] == "agent_remote_existing"
    assert ("tool_remote_existing", ) not in [c[:1] for c in client.conversational_ai.tools.created]
    assert len(client.conversational_ai.tools.created) == 3
    assert len(client.conversational_ai.agents.created) == 5
    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text()) == manifest
