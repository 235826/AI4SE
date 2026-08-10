from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

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
            elif action.type == "apply_patch":
                patch = str(action.args.get("patch", ""))
                for raw_path in re.findall(r"^\+\+\+ b/(.+)$", patch, re.MULTILINE):
                    decision = self._check_path(raw_path.split("\t", 1)[0])
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

    def _check_command(self, command: str) -> RiskDecision:
        normalized = " ".join(command.lower().split())
        dangerous = tuple(" ".join(pattern.split()) for pattern in DANGEROUS_COMMANDS)
        if any(pattern in normalized for pattern in dangerous):
            return RiskDecision(False, "high", f"dangerous command blocked: {command}")
        parts = command.split()
        if not parts or parts[0] != "pytest":
            return RiskDecision(False, "high", f"command outside allowlist: {command}")
        allowed_flags = {"-q", "-v", "--maxfail=1"}
        if any(part not in allowed_flags and not part.startswith("tests/") for part in parts[1:]):
            return RiskDecision(False, "high", f"command argument outside allowlist: {command}")
        if self.interactive_approval and "--maxfail=1" in parts:
            return RiskDecision(True, "medium", "pytest maxfail changes run behavior", True)
        return RiskDecision(True, "low", "pytest command allowed")
