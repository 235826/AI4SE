from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Action:
    type: str
    args: dict[str, Any]
    reason: str = ""


@dataclass(frozen=True)
class ToolResult:
    action_type: str
    ok: bool
    exit_code: int | None
    stdout_summary: str = ""
    stderr_summary: str = ""
    changed_files: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class Feedback:
    kind: str
    passed: bool
    failed_tests: list[str]
    counts: dict[str, int]
    summary: str


@dataclass(frozen=True)
class MemoryEntry:
    timestamp: str
    kind: str
    content: str
    source: str
    run_id: str


@dataclass(frozen=True)
class RunEvent:
    timestamp: str
    run_id: str
    step: int
    event_type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class RunStatus:
    ok: bool
    reason: str
    steps: int
