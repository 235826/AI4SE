import subprocess
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


def test_initial_context_contains_workspace_summary_and_recent_memory(tmp_path: Path):
    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    memory = MemoryStore(tmp_path / ".patchpilot" / "memory.jsonl")
    memory.append("decision", "keep changes focused", "user", "earlier")

    class CapturingLLM:
        def __init__(self):
            self.context = None

        def next_action(self, context):
            self.context = context
            return Action("finish", {"ok": True})

    llm = CapturingLLM()
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path), memory)
    AgentLoop(llm, dispatcher, run_id="r1").run("inspect", "pytest")

    assert llm.context["workspace"]["root"] == str(tmp_path.resolve())
    assert "sample.py" in llm.context["workspace"]["files"]
    assert llm.context["memory"][-1]["content"] == "keep changes focused"


def test_context_aware_llm_changes_action_after_failed_feedback(tmp_path: Path):
    (tmp_path / "test_failure.py").write_text(
        "def test_failure():\n    assert False\n", encoding="utf-8"
    )

    class FeedbackAwareLLM:
        def __init__(self):
            self.calls = 0
            self.observed_failure = False

        def next_action(self, context):
            self.calls += 1
            if self.calls == 1:
                return Action("run_tests", {"command": "pytest -q"})
            self.observed_failure = bool(
                context["feedback"]["passed"] is False
                and context["last_result"]["ok"] is False
                and context["feedback"]["failed_tests"]
            )
            return Action("finish", {"ok": self.observed_failure})

    llm = FeedbackAwareLLM()
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))

    status = AgentLoop(llm, dispatcher, run_id="r1").run("react", "pytest -q")

    assert status.ok is True
    assert llm.observed_failure is True


def test_loop_writes_run_summary_memory_on_exit(tmp_path: Path):
    memory = MemoryStore(tmp_path / ".patchpilot" / "memory.jsonl")
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path), memory)

    status = AgentLoop(MockLLM([Action("finish", {"ok": True})]), dispatcher, run_id="r9").run(
        "stop", "pytest"
    )

    summary = memory.recent(1)[0]
    assert status.ok is True
    assert summary.kind == "run_summary"
    assert summary.run_id == "r9"
    assert "finish" in summary.content


def test_loop_stops_with_tool_timeout_reason(tmp_path: Path, monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("pytest", 1)

    monkeypatch.setattr("patchpilot.tools.subprocess.run", raise_timeout)
    loop = make_loop(tmp_path, [Action("run_tests", {"command": "pytest"})])

    status = loop.run("timeout", "pytest")

    assert status == RunStatus(False, "tool_timeout", 1)


def test_loop_stops_after_two_consecutive_invalid_actions(tmp_path: Path):
    class InvalidLLM:
        def next_action(self, context):
            raise ValueError("invalid action schema")

    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))
    loop = AgentLoop(InvalidLLM(), dispatcher, max_steps=4, run_id="r1")

    status = loop.run("invalid", "pytest")

    assert status == RunStatus(False, "invalid_actions", 2)
    assert [event.event_type for event in loop.events] == ["invalid_action", "invalid_action"]


def test_run_event_redacts_secret_values_in_remember_and_patch_args(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("value = 'old'\n", encoding="utf-8")
    memory = MemoryStore(tmp_path / ".patchpilot" / "memory.jsonl")
    patch = """--- a/sample.py
+++ b/sample.py
@@ -1 +1 @@
-value = 'old'
+value = 'sk-patch-secret'
"""
    actions = [
        Action("remember", {"kind": "note", "content": "api_token=memory-secret", "run_id": "r1"}),
        Action("apply_patch", {"patch": patch}),
    ]
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path), memory)
    loop = AgentLoop(MockLLM(actions), dispatcher, max_steps=2, run_id="r1")

    loop.run("redact", "pytest")

    payloads = repr([event.payload for event in loop.events])
    assert "memory-secret" not in payloads
    assert "sk-patch-secret" not in payloads
    assert "[REDACTED]" in payloads
