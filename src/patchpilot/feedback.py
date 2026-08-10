from __future__ import annotations

import re

from patchpilot.models import Feedback, ToolResult


_COUNT_PATTERN = re.compile(r"(\d+)\s+(passed|failed|errors?)\b")
_FAILED_TEST_PATTERN = re.compile(r"^FAILED\s+(.+?)(?:\s+-\s+|$)", re.MULTILINE)


def parse_pytest_result(result: ToolResult) -> Feedback:
    output = "\n".join((result.stdout_summary, result.stderr_summary))
    counts = {}
    for match in _COUNT_PATTERN.finditer(output):
        name = "error" if match.group(2) == "errors" else match.group(2)
        counts[name] = int(match.group(1))
    failed_tests = _FAILED_TEST_PATTERN.findall(output)
    passed = result.ok and not counts.get("failed", 0) and not counts.get("error", 0)
    summary = next((line.strip() for line in reversed(output.splitlines()) if line.strip()), "")
    return Feedback("pytest", passed, failed_tests, counts, summary)


def timeout_feedback(command: str) -> Feedback:
    return Feedback("pytest", False, [], {}, f"timeout: {command}")
