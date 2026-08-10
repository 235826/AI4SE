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


def test_parse_plural_pytest_error_count():
    result = ToolResult("run_tests", False, 1, "2 errors in 0.20s", "", [], None)
    feedback = parse_pytest_result(result)
    assert feedback.passed is False
    assert feedback.counts["error"] == 2


def test_parse_parameterized_failed_test_name_with_spaces():
    output = "FAILED tests/test_x.py::test_case[a b] - AssertionError\n1 failed in 0.20s"
    result = ToolResult("run_tests", False, 1, output, "", [], None)
    feedback = parse_pytest_result(result)
    assert feedback.failed_tests == ["tests/test_x.py::test_case[a b]"]


def test_parse_parameterized_failed_test_name_with_separator_text():
    output = "FAILED tests/test_x.py::test_case[a - b] - AssertionError\n1 failed in 0.20s"
    result = ToolResult("run_tests", False, 1, output, "", [], None)
    feedback = parse_pytest_result(result)
    assert feedback.failed_tests == ["tests/test_x.py::test_case[a - b]"]


def test_timeout_feedback_is_not_passed():
    feedback = timeout_feedback("pytest")
    assert feedback.passed is False
    assert feedback.kind == "pytest"
    assert "timeout" in feedback.summary


def test_failure_summary_includes_brief_traceback_context():
    output = """============================= test session starts ==============================
_______________________________ test_total ________________________________
    def test_total():
>       assert total(2, 2) == 5
E       assert 4 == 5
tests/test_math.py:7: AssertionError
=========================== short test summary info ============================
FAILED tests/test_math.py::test_total - assert 4 == 5
1 failed in 0.10s
"""
    result = ToolResult("run_tests", False, 1, output, "", [], "test command failed")

    feedback = parse_pytest_result(result)

    assert "1 failed in 0.10s" in feedback.summary
    assert "assert 4 == 5" in feedback.summary
