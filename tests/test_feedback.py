from patchpilot.feedback import parse_pytest_result, timeout_feedback
from patchpilot.models import ToolResult


def test_parse_passing_pytest_output():
    result = ToolResult("run_tests", True, 0, "3 passed in 0.10s", "", [], None)
    feedback = parse_pytest_result(result)
    assert feedback.passed is True
    assert feedback.counts["passed"] == 3
    assert feedback.failed_tests == []


def test_parse_failed_test_names():
    output = "FAILED tests/test_math.py::test_add - AssertionError\n1 failed, 2 passed in 0.20s"
    result = ToolResult("run_tests", False, 1, output, "", [], None)
    feedback = parse_pytest_result(result)
    assert feedback.passed is False
    assert feedback.failed_tests == ["tests/test_math.py::test_add"]
    assert feedback.counts["failed"] == 1
    assert feedback.counts["passed"] == 2


def test_timeout_feedback_is_not_passed():
    feedback = timeout_feedback("pytest")
    assert feedback.passed is False
    assert feedback.kind == "pytest"
    assert "timeout" in feedback.summary
