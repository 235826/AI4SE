from pathlib import Path

from patchpilot.agent import AgentLoop
from patchpilot.guardrails import GuardrailPolicy
from patchpilot.llm import MockLLM
from patchpilot.memory import MemoryStore
from patchpilot.models import Action
from patchpilot.tools import ToolDispatcher


def make_loop(tmp_path: Path, actions):
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path), MemoryStore(tmp_path / ".patchpilot" / "memory.jsonl"))
    return AgentLoop(MockLLM(actions), dispatcher, max_steps=3, run_id="r1")


def test_loop_stops_on_finish(tmp_path: Path):
    loop = make_loop(tmp_path, [Action("finish", {"ok": True})])
    status = loop.run(task="stop", test_command="pytest")
    assert status.ok is True
    assert status.reason == "finish"
    assert len(loop.events) == 1


def test_loop_stops_when_tests_pass(tmp_path: Path):
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    loop = make_loop(tmp_path, [Action("run_tests", {"command": "pytest -q"})])
    status = loop.run(task="run tests", test_command="pytest -q")
    assert status.ok is True
    assert status.reason == "tests_passed"


def test_loop_stops_on_blocked_action(tmp_path: Path):
    loop = make_loop(tmp_path, [Action("read_file", {"path": ".env"})])
    status = loop.run(task="read secret", test_command="pytest")
    assert status.ok is False
    assert status.reason == "blocked_action"
