from pathlib import Path

from patchpilot.agent import AgentLoop
from patchpilot.guardrails import GuardrailPolicy
from patchpilot.llm import MockLLM
from patchpilot.memory import MemoryStore
from patchpilot.models import Action, RunStatus
from patchpilot.tools import ToolDispatcher


def make_loop(tmp_path: Path, actions, max_steps: int = 3):
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path), MemoryStore(tmp_path / ".patchpilot" / "memory.jsonl"))
    return AgentLoop(MockLLM(actions), dispatcher, max_steps=max_steps, run_id="r1")


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


def test_loop_stops_on_guardrail_blocked_test_command(tmp_path: Path):
    loop = make_loop(
        tmp_path,
        [Action("run_tests", {"command": "pytest -p evil_plugin"}), Action("finish", {"ok": True})],
    )

    status = loop.run(task="run blocked tests", test_command="pytest")

    assert status.ok is False
    assert status.reason == "blocked_action"
    assert status.steps == 1
    assert len(loop.events) == 1


def test_loop_continues_after_failed_test_command(tmp_path: Path):
    test_file = tmp_path / "test_failure.py"
    test_file.write_text("def test_failure():\n    assert False\n", encoding="utf-8")
    loop = make_loop(
        tmp_path,
        [Action("run_tests", {"command": "pytest -q"}), Action("finish", {"ok": True})],
    )

    status = loop.run(task="recover from test failure", test_command="pytest -q")

    assert status == RunStatus(True, "finish", 2)
    assert len(loop.events) == 2
    assert loop.events[0].payload["feedback_summary"]


def test_loop_reports_max_steps_and_auditable_event_payload(tmp_path: Path):
    loop = make_loop(tmp_path, [Action("list_files", {}), Action("list_files", {})], max_steps=2)

    status = loop.run(task="exhaust", test_command="pytest")

    assert status == RunStatus(False, "max_steps", 2)
    assert len(loop.events) == 2
    assert loop.events[0].payload == {
        "action_type": "list_files",
        "action_args": {},
        "tool": {"ok": True, "error": None, "blocked": False},
    }
