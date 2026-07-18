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
