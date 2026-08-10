from patchpilot.cli import main


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
