from __future__ import annotations

import os
from pathlib import Path

import keyring
from dotenv import dotenv_values


class CredentialManager:
    _USERNAME = "openai-api-key"

    def __init__(self, service_name: str = "patchpilot-openai", keyring_backend=None) -> None:
        self.service_name = service_name
        self._keyring = keyring_backend if keyring_backend is not None else keyring

    def status(self) -> bool:
        return self.credential_source() is not None

    def set_key(self, key: str) -> None:
        self._keyring.set_password(self.service_name, self._USERNAME, key)

    def clear(self) -> str | None:
        try:
            self._keyring.delete_password(self.service_name, self._USERNAME)
        except Exception:
            pass
        return self.credential_source()

    def get_key(self) -> str | None:
        key = self._keyring_key()
        if key:
            return key
        environment_key = os.getenv("OPENAI_API_KEY")
        if environment_key:
            return environment_key
        value = dotenv_values(Path.cwd() / ".env").get("OPENAI_API_KEY")
        return value if isinstance(value, str) and value else None

    def credential_source(self) -> str | None:
        if self._keyring_key():
            return "keyring"
        if os.getenv("OPENAI_API_KEY"):
            return "environment"
        value = dotenv_values(Path.cwd() / ".env").get("OPENAI_API_KEY")
        return ".env" if isinstance(value, str) and value else None

    def _keyring_key(self) -> str | None:
        try:
            key = self._keyring.get_password(self.service_name, self._USERNAME)
        except Exception:
            return None
        return key if isinstance(key, str) and key else None
