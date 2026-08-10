from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


REDACTED = "[REDACTED]"
_SENSITIVE_KEY = re.compile(r"(?i)(authorization|password|api[_-]?key|secret|token)")
_OPENAI_KEY = re.compile(r"sk-[A-Za-z0-9_-]+")
_BEARER = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)\S+")
_ASSIGNMENT = re.compile(
    r"(?i)\b([\w.-]*(?:api[_-]?key|password|secret|token)[\w.-]*)(\s*[:=]\s*)([^\s,;]+)"
)


def redact_text(text: str) -> str:
    redacted = _BEARER.sub(rf"\1{REDACTED}", text)
    redacted = _ASSIGNMENT.sub(rf"\1\2{REDACTED}", redacted)
    return _OPENAI_KEY.sub(REDACTED, redacted)


def redact_data(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: REDACTED if _SENSITIVE_KEY.search(str(key)) else redact_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_data(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value
