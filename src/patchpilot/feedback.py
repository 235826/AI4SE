from __future__ import annotations

import re

from patchpilot.models import Feedback, ToolResult


_COUNT_PATTERN = re.compile(r"(\d+)\s+(passed|failed|error)\b")
_FAILED_TEST_PATTERN = re.compile(r"^FAILED\s+(\S+)", re.MULTILINE)


def parse_pytest_result(result: ToolResult) -> Feedback:
    output = "\n".join((result.stdout_summary, result.stderr_summary))
    counts = {
        match.group(2): int(match.group(1))
        for match in _COUNT_PATTERN.finditer(output)
    }
    failed_tests = _FAILED_TEST_PATTERN.findall(output)
    passed = result.ok and not counts.get("failed", 0) and not counts.get("error", 0)
    summary = next((line.strip() for line in reversed(output.splitlines()) if line.strip()), "")
    return Feedback("pytest", passed, failed_tests, counts, summary)


def timeout_feedback(command: str) -> Feedback:
    return Feedback("pytest", False, [], {}, f"timeout: {command}")
