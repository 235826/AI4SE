from pathlib import Path

from patchpilot.guardrails import GuardrailPolicy
from patchpilot.memory import MemoryStore
from patchpilot.models import Action
from patchpilot.tools import ToolDispatcher


def test_read_file_reads_workspace_file(tmp_path: Path):
    (tmp_path / "sample.py").write_text("x = 1\n", encoding="utf-8")
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))
    result = dispatcher.dispatch(Action("read_file", {"path": "sample.py"}))
    assert result.ok is True
    assert "x = 1" in result.stdout_summary


def test_dispatch_blocks_sensitive_file(tmp_path: Path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))
    result = dispatcher.dispatch(Action("read_file", {"path": ".env"}))
    assert result.ok is False
    assert result.error is not None
    assert "secret" not in result.stderr_summary


def test_remember_writes_memory(tmp_path: Path):
    memory = MemoryStore(tmp_path / ".patchpilot" / "memory.jsonl")
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path), memory=memory)
    result = dispatcher.dispatch(
        Action("remember", {"kind": "decision", "content": "use pytest", "run_id": "r1"})
    )
    assert result.ok is True
    assert memory.recent(1)[0].content == "use pytest"


def test_apply_patch_applies_single_file_unified_diff(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("x = 1\n", encoding="utf-8")
    patch = """--- a/sample.py
+++ b/sample.py
@@ -1 +1 @@
-x = 1
+x = 2
"""
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))
    result = dispatcher.dispatch(Action("apply_patch", {"patch": patch}))
    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "x = 2\n"
    assert result.changed_files == ["sample.py"]
