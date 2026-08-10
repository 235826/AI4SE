from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchpilot.models import Action


SENSITIVE_PARTS = {".env", ".ssh"}
SENSITIVE_SUFFIXES = {".pem"}
SENSITIVE_WORDS = {"token", "secret", "id_rsa"}
DANGEROUS_COMMANDS = ("rm -rf", "curl | sh", "git push", "twine upload", "npm publish", "docker push")


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    risk: str
    reason: str
    requires_approval: bool = False


@dataclass(frozen=True)
class GuardrailPolicy:
    workspace: Path
    interactive_approval: bool = False

    def check_action(self, action: Action) -> RiskDecision:
        known_actions = {"list_files", "read_file", "apply_patch", "run_tests", "remember", "finish"}
        if action.type not in known_actions:
            return RiskDecision(False, "high", f"unknown action blocked: {action.type}")

        if action.type in {"read_file", "apply_patch"}:
            raw_path = action.args.get("path") or action.args.get("target")
            if raw_path:
                decision = self._check_path(str(raw_path))
                if not decision.allowed:
                    return decision
            if action.type == "apply_patch" and "patch" in action.args:
                decision = self._check_patch_paths(str(action.args["patch"]))
                if not decision.allowed:
                    return decision

        if action.type == "run_tests":
            return self._check_command(str(action.args.get("command", "")))

        return RiskDecision(True, "low", "action allowed")

    def _check_path(self, raw_path: str) -> RiskDecision:
        path = Path(raw_path)
        resolved = (self.workspace / path).resolve() if not path.is_absolute() else path.resolve()
        workspace = self.workspace.resolve()
        if not (resolved == workspace or workspace in resolved.parents):
            return RiskDecision(False, "high", f"path outside workspace: {raw_path}")

        parts = {part.lower() for part in path.parts}
        lowered = raw_path.lower()
        if parts & SENSITIVE_PARTS:
            return RiskDecision(False, "high", f"sensitive path blocked: {raw_path}")
        if any(lowered.endswith(suffix) for suffix in SENSITIVE_SUFFIXES):
            return RiskDecision(False, "high", f"sensitive suffix blocked: {raw_path}")
        if any(word in lowered for word in SENSITIVE_WORDS):
            return RiskDecision(False, "high", f"sensitive name blocked: {raw_path}")
        return RiskDecision(True, "low", "path allowed")

    def _check_patch_paths(self, patch: str) -> RiskDecision:
        for line in patch.splitlines():
            if not (line.startswith("--- ") or line.startswith("+++ ")):
                continue
            raw_path = line[4:].split("\t", 1)[0]
            if raw_path == "/dev/null":
                continue
            if raw_path.startswith(("a/", "b/")):
                raw_path = raw_path[2:]
            else:
                return RiskDecision(False, "high", f"invalid patch path: {raw_path}")
            decision = self._check_path(raw_path)
            if not decision.allowed:
                return decision
        return RiskDecision(True, "low", "patch paths allowed")

    def _check_command(self, command: str) -> RiskDecision:
        normalized = " ".join(command.lower().split())
        dangerous = tuple(" ".join(pattern.split()) for pattern in DANGEROUS_COMMANDS)
        if any(pattern in normalized for pattern in dangerous):
            return RiskDecision(False, "high", f"dangerous command blocked: {command}")
        parts = command.split()
        if not parts or parts[0] != "pytest":
            return RiskDecision(False, "high", f"command outside allowlist: {command}")
        allowed_flags = {"-q", "-v", "--maxfail=1"}
        for part in parts[1:]:
            if part in allowed_flags:
                continue
            if not self._is_allowed_test_target(part):
                return RiskDecision(False, "high", f"command argument outside allowlist: {command}")
        if "--maxfail=1" in parts:
            reason = "pytest maxfail changes run behavior and requires approval"
            if self.interactive_approval:
                return RiskDecision(True, "medium", reason, True)
            return RiskDecision(False, "medium", reason)
        return RiskDecision(True, "low", "pytest command allowed")

    def _is_allowed_test_target(self, target: str) -> bool:
        path_text = target.split("::", 1)[0]
        path = Path(path_text)
        if not path_text.startswith("tests/") or path.is_absolute() or ".." in path.parts:
            return False
        resolved = (self.workspace / path).resolve()
        workspace = self.workspace.resolve()
        return workspace in resolved.parents
