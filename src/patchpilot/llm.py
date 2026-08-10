from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from patchpilot.models import Action


class LLMProvider(Protocol):
    def next_action(self, context: dict[str, Any]) -> Action:
        ...


@dataclass
class MockLLM:
    actions: list[Action]

    def next_action(self, context: dict[str, Any]) -> Action:
        if self.actions:
            return self.actions.pop(0)
        return Action("finish", {"ok": False})


class OpenAILLM:
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.model = model

    def next_action(self, context: dict[str, Any]) -> Action:
        try:
            import openai  # noqa: F401
        except ImportError:
            pass
        raise RuntimeError("OpenAI provider is not implemented for offline tests")
