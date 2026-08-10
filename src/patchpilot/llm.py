from __future__ import annotations

import json
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
    ACTION_TYPES = {"list_files", "read_file", "apply_patch", "run_tests", "remember", "finish"}

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini", client: Any | None = None) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.model = model
        self._client = client

    def next_action(self, context: dict[str, Any]) -> Action:
        client = self._get_client()
        completion = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return one JSON action with keys type, args, and optional reason. "
                        f"Allowed types: {', '.join(sorted(self.ACTION_TYPES))}."
                    ),
                },
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
        )
        try:
            content = completion.choices[0].message.content
        except (AttributeError, IndexError) as error:
            raise ValueError("OpenAI response missing action content") from error
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError("OpenAI returned invalid JSON action") from error
        if not isinstance(data, dict):
            raise ValueError("OpenAI returned invalid action schema: expected object")
        action_type = data.get("type")
        args = data.get("args")
        reason = data.get("reason", "")
        if not isinstance(action_type, str) or not isinstance(args, dict) or not isinstance(reason, str):
            raise ValueError("OpenAI returned invalid action schema")
        if action_type not in self.ACTION_TYPES:
            raise ValueError(f"OpenAI returned unsupported action type: {action_type}")
        return Action(action_type, args, reason)

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as error:
                raise RuntimeError(
                    "OpenAI provider requires the optional 'openai' dependency"
                ) from error
            self._client = OpenAI(api_key=self.api_key)
        return self._client
