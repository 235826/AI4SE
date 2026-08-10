from pathlib import Path

from patchpilot.guardrails import GuardrailPolicy
from patchpilot.models import Action


def test_blocks_reading_env_file(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    decision = policy.check_action(Action(type="read_file", args={"path": ".env"}))
    assert decision.allowed is False
    assert decision.risk == "high"
    assert ".env" in decision.reason


def test_blocks_path_outside_workspace(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    outside = tmp_path.parent / "outside.py"
    decision = policy.check_action(Action(type="read_file", args={"path": str(outside)}))
    assert decision.allowed is False
    assert decision.risk == "high"


def test_blocks_patch_targeting_env_file(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    patch = "diff --git a/app.py b/.env\n--- a/app.py\n+++ b/.env\n@@ -1 +1 @@\n-old\n+new\n"
    decision = policy.check_action(Action(type="apply_patch", args={"patch": patch}))
    assert decision.allowed is False
    assert decision.risk == "high"
    assert ".env" in decision.reason


def test_blocks_patch_targeting_outside_workspace(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    patch = "--- a/app.py\n+++ b/../outside.py\n@@ -1 +1 @@\n-old\n+new\n"
    decision = policy.check_action(Action(type="apply_patch", args={"patch": patch}))
    assert decision.allowed is False
    assert decision.risk == "high"


def test_blocks_case_insensitive_sensitive_paths(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    for path in (".ENV", ".SSH/config"):
        decision = policy.check_action(Action(type="read_file", args={"path": path}))
        assert decision.allowed is False
        assert decision.risk == "high"


def test_blocks_dangerous_test_command(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    action = Action(type="run_tests", args={"command": "rm -rf ."})
    decision = policy.check_action(action)
    assert decision.allowed is False
    assert "rm -rf" in decision.reason


def test_blocks_dangerous_command_with_extra_whitespace(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    decision = policy.check_action(Action(type="run_tests", args={"command": "rm  -rf ."}))
    assert decision.allowed is False
    assert decision.risk == "high"
    assert "dangerous command blocked" in decision.reason


def test_blocks_case_insensitive_dangerous_command(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    decision = policy.check_action(Action(type="run_tests", args={"command": "GIT PUSH"}))
    assert decision.allowed is False
    assert decision.risk == "high"
    assert "dangerous command blocked" in decision.reason


def test_allows_pytest_command(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    action = Action(type="run_tests", args={"command": "pytest tests/test_sample.py -q"})
    decision = policy.check_action(action)
    assert decision.allowed is True
    assert decision.risk == "low"


def test_allows_pytest_flags_and_test_nodeid(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    action = Action(
        type="run_tests",
        args={"command": "pytest -v tests/test_sample.py::test_case -q"},
    )
    decision = policy.check_action(action)
    assert decision.allowed is True
    assert decision.risk == "low"


def test_rejects_unlisted_pytest_argument(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    action = Action(type="run_tests", args={"command": "pytest -p evil_plugin"})
    decision = policy.check_action(action)
    assert decision.allowed is False
    assert decision.risk == "high"


def test_medium_risk_requires_approval_only_when_enabled(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path, interactive_approval=True)
    action = Action(type="run_tests", args={"command": "pytest --maxfail=1"})
    decision = policy.check_action(action)
    assert decision.allowed is True
    assert decision.requires_approval is True


def test_unknown_action_is_rejected(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    decision = policy.check_action(Action(type="delete_everything", args={}))
    assert decision.allowed is False
    assert decision.risk == "high"
    assert "unknown action" in decision.reason
