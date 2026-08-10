from __future__ import annotations

import re
import subprocess
from pathlib import Path

from patchpilot.guardrails import GuardrailPolicy
from patchpilot.memory import MemoryStore
from patchpilot.models import Action, ToolResult


_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_SENSITIVE_OUTPUT = re.compile(r"(?i)(authorization\s*:\s*bearer\s+\S+|sk-[a-z0-9_-]+|secret|token|key)")


class ToolDispatcher:
    def __init__(
        self,
        workspace: Path,
        guardrails: GuardrailPolicy,
        memory: MemoryStore | None = None,
        timeout_seconds: int = 20,
    ):
        self.workspace = workspace.resolve()
        self.guardrails = guardrails
        self.memory = memory
        self.timeout_seconds = timeout_seconds

    def dispatch(self, action: Action) -> ToolResult:
        decision = self.guardrails.check_action(action)
        if not decision.allowed:
            return ToolResult(action.type, False, None, error=decision.reason)
        if decision.requires_approval:
            return ToolResult(action.type, False, None, error="action requires approval")

        try:
            handler = getattr(self, f"_{action.type}")
        except AttributeError:
            return ToolResult(action.type, False, None, error="unsupported action")

        try:
            return handler(action.args)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            return ToolResult(action.type, False, None, error=self._safe_error(error))

    def _list_files(self, _: dict[str, object]) -> ToolResult:
        files: list[str] = []
        for path in self.workspace.rglob("*"):
            relative = path.relative_to(self.workspace)
            if self._is_sensitive(relative):
                continue
            if path.is_file():
                files.append(relative.as_posix())
        return ToolResult("list_files", True, 0, "\n".join(sorted(files)))

    def _read_file(self, args: dict[str, object]) -> ToolResult:
        path = self._workspace_path(args.get("path"))
        content = path.read_text(encoding="utf-8")
        return ToolResult("read_file", True, 0, self._redact(content[:4000]))

    def _apply_patch(self, args: dict[str, object]) -> ToolResult:
        patch = args.get("patch")
        if not isinstance(patch, str):
            raise ValueError("patch must be text")
        path, lines = self._parse_patch(patch)
        target = self._workspace_path(path)
        original = target.read_text(encoding="utf-8")
        updated = self._apply_hunks(original, lines)
        target.write_text(updated, encoding="utf-8")
        return ToolResult("apply_patch", True, 0, "patch applied", changed_files=[path])

    def _run_tests(self, args: dict[str, object]) -> ToolResult:
        command = args.get("command")
        if not isinstance(command, str) or not command:
            raise ValueError("command must be text")
        completed = subprocess.run(
            command.split(),
            cwd=self.workspace,
            timeout=self.timeout_seconds,
            capture_output=True,
            text=True,
            check=False,
        )
        return ToolResult(
            "run_tests",
            completed.returncode == 0,
            completed.returncode,
            self._redact(completed.stdout),
            self._redact(completed.stderr),
            error=None if completed.returncode == 0 else "test command failed",
        )

    def _remember(self, args: dict[str, object]) -> ToolResult:
        if self.memory is None:
            raise ValueError("memory store is unavailable")
        kind = args.get("kind")
        content = args.get("content")
        run_id = args.get("run_id")
        if not all(isinstance(value, str) for value in (kind, content, run_id)):
            raise ValueError("memory entry fields must be text")
        self.memory.append(kind, content, source="agent", run_id=run_id)
        return ToolResult("remember", True, 0, "memory saved")

    def _finish(self, _: dict[str, object]) -> ToolResult:
        return ToolResult("finish", True, 0, "finish", "", [], None)

    def _workspace_path(self, raw_path: object) -> Path:
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError("path must be text")
        path = Path(raw_path)
        resolved = (self.workspace / path).resolve() if not path.is_absolute() else path.resolve()
        if resolved != self.workspace and self.workspace not in resolved.parents:
            raise ValueError("path outside workspace")
        return resolved

    def _parse_patch(self, patch: str) -> tuple[str, list[str]]:
        lines = patch.splitlines()
        if len(lines) < 3 or not lines[0].startswith("--- a/") or not lines[1].startswith("+++ b/"):
            raise ValueError("patch must target one workspace file")
        old_path = lines[0][6:].split("\t", 1)[0]
        new_path = lines[1][6:].split("\t", 1)[0]
        if not old_path or old_path != new_path or old_path == "/dev/null":
            raise ValueError("file creation and deletion are unsupported")
        if any(line.startswith(("--- ", "+++ ")) for line in lines[2:]):
            raise ValueError("patch must target one file")
        return new_path, lines[2:]

    def _apply_hunks(self, original: str, patch_lines: list[str]) -> str:
        source = [
            (line.removesuffix("\n"), line.endswith("\n"))
            for line in original.splitlines(keepends=True)
        ]
        result: list[tuple[str, bool]] = []
        cursor = 0
        index = 0
        while index < len(patch_lines):
            header = _HUNK_HEADER.match(patch_lines[index])
            if header is None:
                raise ValueError("invalid unified diff hunk")
            old_start = int(header.group(1))
            old_count = int(header.group(2) or "1")
            new_count = int(header.group(4) or "1")
            if old_start == 0:
                if old_count != 0 or cursor != 0:
                    raise ValueError("invalid hunk position")
                hunk_start = 0
            else:
                hunk_start = old_start - 1
            if old_start < 0 or hunk_start < cursor:
                raise ValueError("invalid hunk position")
            result.extend(source[cursor:hunk_start])
            cursor = hunk_start
            index += 1
            removed = added = 0
            previous_kind: str | None = None
            while index < len(patch_lines) and not patch_lines[index].startswith("@@ "):
                line = patch_lines[index]
                if line == r"\ No newline at end of file":
                    if previous_kind is None:
                        raise ValueError("invalid no-newline marker")
                    if previous_kind in {" ", "+"}:
                        text, _ = result[-1]
                        result[-1] = (text, False)
                    index += 1
                    continue
                if not line or line[0] not in " +-":
                    raise ValueError("invalid unified diff line")
                text = line[1:]
                if line[0] == " ":
                    if cursor >= len(source) or source[cursor][0] != text:
                        raise ValueError("patch context does not match file")
                    result.append(source[cursor])
                    cursor += 1
                    removed += 1
                    added += 1
                elif line[0] == "-":
                    if cursor >= len(source) or source[cursor][0] != text:
                        raise ValueError("patch removal does not match file")
                    cursor += 1
                    removed += 1
                else:
                    result.append((text, True))
                    added += 1
                previous_kind = line[0]
                index += 1
            if removed != old_count or added != new_count:
                raise ValueError("hunk line counts do not match header")
        result.extend(source[cursor:])
        return "".join(text + ("\n" if has_newline else "") for text, has_newline in result)

    @staticmethod
    def _is_sensitive(path: Path) -> bool:
        return any(
            part.lower() in {".git", ".patchpilot", ".env", ".ssh"}
            or part.lower().endswith(".pem")
            or any(word in part.lower() for word in {"id_rsa", "token", "secret", "key"})
            for part in path.parts
        )

    @staticmethod
    def _redact(text: str) -> str:
        return "\n".join(
            "[REDACTED]" if _SENSITIVE_OUTPUT.search(line) else line
            for line in text.splitlines()
        )

    @staticmethod
    def _safe_error(error: Exception) -> str:
        if isinstance(error, subprocess.TimeoutExpired):
            return "tool execution timed out"
        return str(error)
