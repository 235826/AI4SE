from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from patchpilot.feedback import parse_pytest_result
from patchpilot.llm import LLMProvider
from patchpilot.models import Feedback, RunEvent, RunStatus, ToolResult
from patchpilot.tools import ToolDispatcher


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
        context: dict[str, Any] = {"task": task, "test_command": test_command}
        for step in range(1, self.max_steps + 1):
            action = self.llm.next_action(context)
            result = self.dispatcher.dispatch(action)
            feedback: Feedback | None = None
            if action.type == "run_tests" and not result.blocked:
                feedback = parse_pytest_result(result)
                context["feedback"] = feedback

            self.events.append(self._event(step, action.type, action.args, result, feedback))

            if result.blocked:
                return RunStatus(False, "blocked_action", step)

            if action.type == "finish":
                return RunStatus(bool(action.args.get("ok", True)), "finish", step)
            if feedback is not None:
                if feedback.passed:
                    return RunStatus(True, "tests_passed", step)

            context["last_result"] = result

        return RunStatus(False, "max_steps", self.max_steps)

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
            "action_args": action_args,
            "tool": {"ok": result.ok, "error": result.error, "blocked": result.blocked},
        }
        if feedback is not None:
            payload["feedback_summary"] = feedback.summary
        return RunEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            run_id=self.run_id,
            step=step,
            event_type=action_type,
            payload=payload,
        )
