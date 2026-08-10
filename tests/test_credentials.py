import keyring

from patchpilot.credentials import CredentialManager


class FakeKeyring:
    def __init__(self):
        self.value = None

    def get_password(self, service, username):
        return self.value

    def set_password(self, service, username, password):
        self.value = password

    def delete_password(self, service, username):
        self.value = None


class UnavailableKeyring:
    def get_password(self, service, username):
        raise RuntimeError("keyring unavailable")

    def delete_password(self, service, username):
        raise RuntimeError("keyring unavailable")


class MissingKeyring:
    def delete_password(self, service, username):
        raise keyring.errors.PasswordDeleteError("missing key")


def test_status_set_and_clear_without_printing_key(capsys):
    fake = FakeKeyring()
    manager = CredentialManager(keyring_backend=fake)
    assert manager.status() is False
    manager.set_key("sk-test-secret")
    assert manager.status() is True
    assert manager.get_key() == "sk-test-secret"
    manager.clear()
    assert manager.status() is False
    captured = capsys.readouterr()
    assert "sk-test-secret" not in captured.out
    assert "sk-test-secret" not in captured.err


def test_get_key_uses_dotenv_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-dotenv-secret\n", encoding="utf-8")

    manager = CredentialManager(keyring_backend=FakeKeyring())

    assert manager.get_key() == "sk-dotenv-secret"


def test_get_key_prefers_keyring_over_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-environment-secret")
    fake = FakeKeyring()
    fake.value = "sk-keyring-secret"
    manager = CredentialManager(keyring_backend=fake)

    assert manager.get_key() == "sk-keyring-secret"


def test_get_key_uses_environment_when_keyring_is_unavailable(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fallback-secret")
    manager = CredentialManager(keyring_backend=UnavailableKeyring())

    assert manager.get_key() == "sk-fallback-secret"


def test_clear_ignores_missing_key():
    CredentialManager(keyring_backend=MissingKeyring()).clear()


def test_clear_ignores_unavailable_keyring():
    CredentialManager(keyring_backend=UnavailableKeyring()).clear()
