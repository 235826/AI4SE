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


def test_read_file_redacts_sensitive_content_in_non_sensitive_file(tmp_path: Path):
    (tmp_path / "settings.py").write_text("OPENAI_API_KEY: secret-value\n", encoding="utf-8")
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))

    result = dispatcher.dispatch(Action("read_file", {"path": "settings.py"}))

    assert result.ok is True
    assert "secret-value" not in result.stdout_summary
    assert "[REDACTED]" in result.stdout_summary


def test_dispatch_blocks_sensitive_file(tmp_path: Path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))
    result = dispatcher.dispatch(Action("read_file", {"path": ".env"}))
    assert result.ok is False
    assert result.error is not None
    assert "secret" not in result.stderr_summary


def test_run_tests_redacts_sensitive_stdout_and_stderr(tmp_path: Path):
    test_file = tmp_path / "tests" / "test_leak.py"
    test_file.parent.mkdir()
    test_file.write_text(
        "import sys\n\n"
        "def test_leaks_output():\n"
        "    print('Authorization: Bearer sk-stdout-secret')\n"
        "    print('service_token: stderr-secret', file=sys.stderr)\n"
        "    assert False\n",
        encoding="utf-8",
    )
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))

    result = dispatcher.dispatch(Action("run_tests", {"command": "pytest tests/test_leak.py -q"}))

    assert result.ok is False
    assert "sk-stdout-secret" not in result.stdout_summary
    assert "stderr-secret" not in result.stdout_summary
    assert "sk-stdout-secret" not in result.stderr_summary
    assert "stderr-secret" not in result.stderr_summary
    assert "[REDACTED]" in result.stdout_summary or "[REDACTED]" in result.stderr_summary


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


def test_apply_patch_inserts_into_empty_file_with_zero_length_hunk(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("", encoding="utf-8")
    patch = """--- a/sample.py
+++ b/sample.py
@@ -0,0 +1 @@
+x = 1
"""
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))

    result = dispatcher.dispatch(Action("apply_patch", {"patch": patch}))

    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "x = 1\n"


def test_apply_patch_accepts_no_newline_marker(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("x = 1", encoding="utf-8")
    patch = """--- a/sample.py
+++ b/sample.py
@@ -1 +1 @@
-x = 1
\\ No newline at end of file
+x = 2
\\ No newline at end of file
"""
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))

    result = dispatcher.dispatch(Action("apply_patch", {"patch": patch}))

    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "x = 2"


def test_list_files_skips_guardrail_sensitive_names(tmp_path: Path):
    safe_file = tmp_path / "safe.py"
    safe_file.write_text("safe\n", encoding="utf-8")
    sensitive_paths = (
        "id_rsa",
        "ID_RSA",
        ".env",
        ".ENV",
        ".ssh/config",
        ".SSH/config",
        "certificate.PEM",
        "api_token.txt",
        "client_secret.txt",
        "private_key.txt",
    )
    for name in sensitive_paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("sensitive\n", encoding="utf-8")
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))

    result = dispatcher.dispatch(Action("list_files", {}))

    assert result.ok is True
    assert result.stdout_summary.splitlines() == ["safe.py"]


def test_apply_patch_rejects_multiple_files_without_writing(tmp_path: Path):
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("first\n", encoding="utf-8")
    second.write_text("second\n", encoding="utf-8")
    patch = """--- a/first.py
+++ b/first.py
@@ -1 +1 @@
-first
+changed
--- a/second.py
+++ b/second.py
@@ -1 +1 @@
-second
+changed
"""
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))

    result = dispatcher.dispatch(Action("apply_patch", {"patch": patch}))

    assert result.ok is False
    assert first.read_text(encoding="utf-8") == "first\n"
    assert second.read_text(encoding="utf-8") == "second\n"


def test_apply_patch_rejects_path_traversal_without_writing(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("x = 1\n", encoding="utf-8")
    patch = """--- a/../sample.py
+++ b/../sample.py
@@ -1 +1 @@
-x = 1
+x = 2
"""
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))

    result = dispatcher.dispatch(Action("apply_patch", {"patch": patch}))

    assert result.ok is False
    assert target.read_text(encoding="utf-8") == "x = 1\n"


def test_apply_patch_rejects_deletion_without_writing(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("x = 1\n", encoding="utf-8")
    patch = """--- a/sample.py
+++ /dev/null
@@ -1 +0,0 @@
-x = 1
"""
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))

    result = dispatcher.dispatch(Action("apply_patch", {"patch": patch}))

    assert result.ok is False
    assert target.read_text(encoding="utf-8") == "x = 1\n"


def test_apply_patch_rejects_context_mismatch_without_writing(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("x = 1\n", encoding="utf-8")
    patch = """--- a/sample.py
+++ b/sample.py
@@ -1 +1 @@
-x = unknown
+x = 2
"""
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path))

    result = dispatcher.dispatch(Action("apply_patch", {"patch": patch}))

    assert result.ok is False
    assert target.read_text(encoding="utf-8") == "x = 1\n"
