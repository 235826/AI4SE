import json
from types import SimpleNamespace

import pytest

from patchpilot.llm import MockLLM, OpenAILLM
from patchpilot.models import Action


def test_mock_llm_returns_scripted_actions_in_order():
    llm = MockLLM([Action("list_files", {}), Action("finish", {"ok": True})])
    assert llm.next_action({}).type == "list_files"
    assert llm.next_action({}).type == "finish"


def test_mock_llm_returns_finish_after_script_exhausted():
    llm = MockLLM([])
    action = llm.next_action({})
    assert action.type == "finish"
    assert action.args["ok"] is False


def test_openai_llm_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        OpenAILLM(api_key="")


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def test_openai_llm_parses_chat_completion_json_action_with_fake_client():
    client = FakeClient(json.dumps({"type": "read_file", "args": {"path": "sample.py"}, "reason": "inspect"}))
    llm = OpenAILLM(api_key="test-key", model="test-model", client=client)

    action = llm.next_action({"task": "fix tests", "feedback": {"passed": False}})

    assert action == Action("read_file", {"path": "sample.py"}, "inspect")
    call = client.chat.completions.calls[0]
    assert call["model"] == "test-model"
    assert "fix tests" in call["messages"][1]["content"]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("not-json", "invalid JSON"),
        (json.dumps({"type": "read_file", "args": "sample.py"}), "invalid action schema"),
        (json.dumps({"type": "delete_everything", "args": {}}), "unsupported action type"),
    ],
)
def test_openai_llm_rejects_invalid_json_or_schema(content, message):
    llm = OpenAILLM(api_key="test-key", client=FakeClient(content))

    with pytest.raises(ValueError, match=message):
        llm.next_action({"task": "fix"})
