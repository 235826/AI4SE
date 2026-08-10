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


def test_blocks_dangerous_test_command(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    action = Action(type="run_tests", args={"command": "rm -rf ."})
    decision = policy.check_action(action)
    assert decision.allowed is False
    assert "rm -rf" in decision.reason


def test_allows_pytest_command(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    action = Action(type="run_tests", args={"command": "pytest tests/test_sample.py -q"})
    decision = policy.check_action(action)
    assert decision.allowed is True
    assert decision.risk == "low"


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
