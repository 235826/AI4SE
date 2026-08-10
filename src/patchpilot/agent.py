from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from patchpilot.feedback import parse_pytest_result
from patchpilot.llm import LLMProvider
from patchpilot.models import Action, Feedback, RunEvent, RunStatus, ToolResult
from patchpilot.redaction import redact_data, redact_text
from patchpilot.tools import ToolDispatcher


_ACTION_TYPES = {"list_files", "read_file", "apply_patch", "run_tests", "remember", "finish"}


class AgentLoop:
    def __init__(
        self,
        llm: LLMProvider,
        dispatcher: ToolDispatcher,
        max_steps: int = 5,
        run_id: str = "run",
    ) -> None:
        self.llm = llm
        self.dispatcher = dispatcher
        self.max_steps = max_steps
        self.run_id = run_id
        self.events: list[RunEvent] = []

    def run(self, task: str, test_command: str) -> RunStatus:
        context = self._initial_context(task, test_command)
        consecutive_invalid = 0
        for step in range(1, self.max_steps + 1):
            try:
                action = self.llm.next_action(context)
                if not isinstance(action, Action):
                    raise ValueError("provider returned a non-Action value")
                if action.type not in _ACTION_TYPES:
                    raise ValueError(f"provider returned unsupported action type: {action.type}")
            except (TypeError, ValueError) as error:
                consecutive_invalid += 1
                safe_error = redact_text(str(error))
                context["last_result"] = {
                    "action_type": "invalid_action",
                    "ok": False,
                    "error": safe_error,
                }
                context["feedback"] = {
                    "kind": "loop",
                    "passed": False,
                    "failed_tests": [],
                    "counts": {},
                    "summary": safe_error,
                }
                self.events.append(self._invalid_event(step, safe_error))
                if consecutive_invalid >= 2:
                    return self._finalize(RunStatus(False, "invalid_actions", step))
                continue

            consecutive_invalid = 0
            result = self.dispatcher.dispatch(action)
            feedback = self._feedback_for(action, result)
            if action.type == "run_tests" and not result.blocked:
                feedback = parse_pytest_result(result)

            self.events.append(self._event(step, action.type, action.args, result, feedback))
            context["last_result"] = asdict(result)
            context["feedback"] = asdict(feedback)

            if result.timed_out:
                return self._finalize(RunStatus(False, "tool_timeout", step))
            if result.blocked:
                return self._finalize(RunStatus(False, "blocked_action", step))

            if action.type == "finish":
                return self._finalize(
                    RunStatus(bool(action.args.get("ok", True)), "finish", step)
                )
            if action.type == "run_tests" and feedback.passed:
                return self._finalize(RunStatus(True, "tests_passed", step))

        return self._finalize(RunStatus(False, "max_steps", self.max_steps))

    def _initial_context(self, task: str, test_command: str) -> dict[str, Any]:
        memory = self.dispatcher.memory
        entries = [] if memory is None else [asdict(entry) for entry in memory.recent(limit=5)]
        files = self.dispatcher.visible_files(limit=50)
        return {
            "task": task,
            "test_command": test_command,
            "workspace": {
                "root": str(self.dispatcher.workspace),
                "files": files,
                "files_truncated": len(self.dispatcher.visible_files(limit=51)) > 50,
            },
            "memory": entries,
        }

    @staticmethod
    def _feedback_for(action: Action, result: ToolResult) -> Feedback:
        summary = result.error or result.stdout_summary or result.stderr_summary
        return Feedback(
            kind="guardrail" if result.blocked else "tool",
            passed=result.ok,
            failed_tests=[],
            counts={},
            summary=summary,
        )

    def _finalize(self, status: RunStatus) -> RunStatus:
        if self.dispatcher.memory is not None:
            summary = json.dumps(
                {"ok": status.ok, "reason": status.reason, "steps": status.steps},
                sort_keys=True,
            )
            try:
                self.dispatcher.memory.append(
                    "run_summary", summary, source="agent_loop", run_id=self.run_id
                )
            except OSError:
                pass
        return status

    def _event(
        self,
        step: int,
        action_type: str,
        action_args: dict[str, Any],
        result: ToolResult,
        feedback: Feedback | None,
    ) -> RunEvent:
        payload: dict[str, Any] = {
            "action_type": action_type,
            "action_args": redact_data(action_args),
            "tool": redact_data(
                {"ok": result.ok, "error": result.error, "blocked": result.blocked}
            ),
        }
        if result.timed_out:
            payload["tool"]["timed_out"] = True
        if action_type == "run_tests":
            payload["feedback_summary"] = redact_text(feedback.summary)
        return RunEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            run_id=self.run_id,
            step=step,
            event_type=action_type,
            payload=payload,
        )

    def _invalid_event(self, step: int, error: str) -> RunEvent:
        return RunEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            run_id=self.run_id,
            step=step,
            event_type="invalid_action",
            payload={"error": redact_text(error)},
        )
