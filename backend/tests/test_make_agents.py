from app.make_agents import upsert_all
from app.vertical import load_vertical


class FakeResource:
    def __init__(self, prefix):
        self.prefix = prefix
        self.created = []
        self.updated = []

    def create(self, **kwargs):
        agent_id = f"{self.prefix}_{len(self.created) + len(self.updated)}"
        self.created.append((agent_id, kwargs))
        return type("Resp", (), {"agent_id": agent_id, "tool_id": agent_id})()

    def update(self, id, **kwargs):
        self.updated.append((id, kwargs))
        return type("Resp", (), {"agent_id": id, "tool_id": id})()


class FakeConversationalAi:
    def __init__(self):
        self.agents = FakeResource("agent")
        self.tools = FakeResource("tool")


class FakeClient:
    def __init__(self):
        self.conversational_ai = FakeConversationalAi()


def test_first_run_creates_four_tools_and_six_agents():
    config = load_vertical()
    client = FakeClient()

    manifest = upsert_all(client, config, manifest={}, backend_base_url="http://x")

    assert len(client.conversational_ai.tools.created) == 4
    assert len(client.conversational_ai.agents.created) == 6
    assert len(manifest["tools"]) == 4
    assert len(manifest["agents"]) == 6


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
