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
