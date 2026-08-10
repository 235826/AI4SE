from patchpilot.models import Action, Feedback, RunStatus, ToolResult


def test_action_defaults_to_empty_reason():
    action = Action(type="finish", args={})
    assert action.reason == ""


def test_tool_result_records_changed_files():
    result = ToolResult(
        action_type="apply_patch",
        ok=True,
        exit_code=0,
        stdout_summary="patched",
        stderr_summary="",
        changed_files=["src/example.py"],
        error=None,
    )
    assert result.changed_files == ["src/example.py"]


def test_tool_result_defaults_blocked_to_false_for_positional_callers():
    result = ToolResult("run_tests", False, 1, "", "", [], "test command failed")

    assert result.blocked is False


def test_feedback_and_run_status_are_plain_data():
    feedback = Feedback(kind="pytest", passed=True, failed_tests=[], counts={"passed": 3}, summary="3 passed")
    status = RunStatus(ok=True, reason="tests_passed", steps=2)
    assert feedback.passed is True
    assert status.reason == "tests_passed"
