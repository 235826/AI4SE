from __future__ import annotations

import os
from pathlib import Path

import keyring
from dotenv import load_dotenv


class CredentialManager:
    _USERNAME = "openai-api-key"

    def __init__(self, service_name: str = "patchpilot-openai", keyring_backend=None) -> None:
        self.service_name = service_name
        self._keyring = keyring_backend if keyring_backend is not None else keyring

    def status(self) -> bool:
        return bool(self.get_key())

    def set_key(self, key: str) -> None:
        self._keyring.set_password(self.service_name, self._USERNAME, key)

    def clear(self) -> None:
        try:
            self._keyring.delete_password(self.service_name, self._USERNAME)
        except Exception:
            pass

    def get_key(self) -> str | None:
        try:
            key = self._keyring.get_password(self.service_name, self._USERNAME)
        except Exception:
            key = None
        if key:
            return key
        load_dotenv(dotenv_path=Path.cwd() / ".env")
        return os.getenv("OPENAI_API_KEY")
