import os
import subprocess
import sys
from pathlib import Path

from patchpilot.cli import main
from patchpilot.models import Action


def test_run_requires_task():
    code = main(["run", "--test-cmd", "pytest"])
    assert code == 2


def test_auth_status_does_not_print_key(monkeypatch, capsys):
    class FakeManager:
        def status(self):
            return True

    monkeypatch.setattr("patchpilot.cli.CredentialManager", lambda: FakeManager())
    code = main(["auth", "status"])
    captured = capsys.readouterr()
    assert code == 0
    assert "configured" in captured.out
    assert "sk-" not in captured.out


def test_run_uses_mock_provider_by_default(monkeypatch, tmp_path):
    created_actions = []

    class FakeMockLLM:
        def __init__(self, actions):
            created_actions.extend(actions)

        def next_action(self, context):
            return Action("finish", {"ok": True})

    monkeypatch.setattr("patchpilot.cli.MockLLM", FakeMockLLM)

    code = main(["run", "--task", "check tests", "--test-cmd", "pytest", "--workspace", str(tmp_path)])

    assert code == 0
    assert created_actions == [Action("run_tests", {"command": "pytest"})]


def test_run_openai_provider_injects_credential(monkeypatch, tmp_path):
    captured = {}

    class FakeManager:
        def get_key(self):
            return "sk-test-key"

    class FakeOpenAILLM:
        def __init__(self, api_key):
            captured["api_key"] = api_key

        def next_action(self, context):
            return Action("finish", {"ok": True})

    monkeypatch.setattr("patchpilot.cli.CredentialManager", FakeManager)
    monkeypatch.setattr("patchpilot.cli.OpenAILLM", FakeOpenAILLM, raising=False)

    code = main(
        ["run", "--task", "check tests", "--test-cmd", "pytest", "--provider", "openai", "--workspace", str(tmp_path)]
    )

    assert code == 0
    assert captured == {"api_key": "sk-test-key"}


def test_run_openai_without_key_returns_safe_error(monkeypatch, tmp_path, capsys):
    class FakeManager:
        def get_key(self):
            return None

    monkeypatch.setattr("patchpilot.cli.CredentialManager", FakeManager)

    code = main(
        ["run", "--task", "check tests", "--test-cmd", "pytest", "--provider", "openai", "--workspace", str(tmp_path)]
    )
    captured = capsys.readouterr()

    assert code == 1
    assert "patchpilot auth set" in captured.err
    assert "sk-" not in captured.out
    assert "sk-" not in captured.err


def test_auth_set_reads_key_with_getpass(monkeypatch, capsys):
    saved_keys = []

    class FakeManager:
        def set_key(self, key):
            saved_keys.append(key)

    monkeypatch.setattr("patchpilot.cli.CredentialManager", FakeManager)
    monkeypatch.setattr("patchpilot.cli.getpass.getpass", lambda prompt: "sk-test-key")

    code = main(["auth", "set"])
    captured = capsys.readouterr()

    assert code == 0
    assert saved_keys == ["sk-test-key"]
    assert "sk-test-key" not in captured.out


def test_module_entrypoint_shows_help_with_src_pythonpath():
    root = Path(__file__).resolve().parents[1]
    environment = os.environ | {"PYTHONPATH": str(root / "src")}

    completed = subprocess.run(
        [sys.executable, "-m", "patchpilot", "--help"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "usage: patchpilot" in completed.stdout
