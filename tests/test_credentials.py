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
