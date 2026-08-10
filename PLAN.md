# PatchPilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Python CLI Coding Agent Harness：默认使用 mock LLM，受控读写工作区、应用 patch、运行 `pytest`、解析客观反馈、执行危险动作拦截，并支持可选 OpenAI 凭据配置与 Docker 分发。

**Architecture:** 代码按 harness 机制拆分：`models` 定义跨模块数据契约，`guardrails` 在执行前做确定性安全判断，`tools` 只执行允许动作，`feedback` 把测试结果变成结构化信号，`memory` 保存有界上下文，`llm` 提供 mock/OpenAI provider，`agent` 实现主循环，`cli` 暴露用户入口。所有核心机制必须能用 mock LLM 和单元测试离线验证。

**Tech Stack:** Python 3.11+，标准库 `argparse`，`pytest`，`keyring`，`python-dotenv`，可选 OpenAI API，Docker，GitHub Actions。

## Global Constraints

- 语言使用 Python 3.11+。
- CLI 使用标准库 `argparse`。
- 测试框架使用 `pytest`。
- 默认 provider 是 `mock`，真实 OpenAI provider 只能作为可选功能。
- 凭据优先从 OS keychain 读取，`.env` 只作为开发 fallback。
- 日志和 CLI 输出不得回显明文 API key。
- v1 只支持 Python 项目的 `pytest` 测试命令。
- 任何核心机制都必须能在没有真实 LLM、没有网络的情况下用单测验证。
- 高风险 action 始终拒绝，`--interactive-approval` 只允许处理中风险 action。
- 每个实现 task 都必须先写失败测试，再实现最少代码使其通过。

---

## 文件结构

- `pyproject.toml`：包元数据、依赖、pytest 配置、console script。
- `Makefile`：一键测试、格式检查入口。
- `src/patchpilot/__init__.py`：版本号。
- `src/patchpilot/__main__.py`：`python -m patchpilot` 入口，由 Task 9 在 CLI 存在后创建。
- `src/patchpilot/models.py`：`Action`、`ToolResult`、`Feedback`、`MemoryEntry`、`RunEvent`、`RunStatus`。
- `src/patchpilot/guardrails.py`：路径策略、命令策略、风险等级、审批接口。
- `src/patchpilot/feedback.py`：pytest 输出解析和 timeout/error feedback 构造。
- `src/patchpilot/memory.py`：JSONL memory store 与 recent retrieval。
- `src/patchpilot/tools.py`：工具 dispatcher、文件读取、文件列举、patch 应用、pytest runner。
- `src/patchpilot/credentials.py`：keyring、`.env`、隐藏输入、auth status/set/clear。
- `src/patchpilot/llm.py`：provider 抽象、`MockLLM`、`OpenAILLM` schema parsing。
- `src/patchpilot/agent.py`：context builder、主循环、停止策略、事件记录。
- `src/patchpilot/cli.py`：`argparse` CLI，`run` 与 `auth` 子命令。
- `tests/`：与模块一一对应的单元测试。
- `Dockerfile`：容器分发。
- `.dockerignore`：排除 git、cache、secret-like 文件。
- `.github/workflows/ci.yml`：测试与 Docker build。
- `README.md`：安装、运行、凭据、Docker、限制。
- `AGENT_LOG.md`：Superpowers 过程日志。
- `REFLECTION.md`：1500-2500 字反思报告。

## 依赖与并行关系

- Task 1 是所有代码 task 的基础。
- Task 2、Task 3、Task 4、Task 5 可在 Task 1 后并行。
- Task 6 依赖 Task 1 和 Task 5。
- Task 7 依赖 Task 1、Task 2、Task 3、Task 4、Task 6。
- Task 8 依赖 Task 5 和 Task 7。
- Task 9 依赖 Task 8。
- Task 10 和 Task 11 依赖 Task 8。
- Task 12 依赖 `PLAN.md`、Task 1、Task 2、Task 7，用于正式实现前冷启动验证。
- Task 13 是收尾文档任务，依赖所有实现任务。

---

### Task 1: 项目骨架与数据模型

完成提交：`bea1bc8`

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `src/patchpilot/__init__.py`
- Create: `src/patchpilot/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Action(type: str, args: dict[str, Any], reason: str = "")`
- Produces: `ToolResult(action_type: str, ok: bool, exit_code: int | None, stdout_summary: str, stderr_summary: str, changed_files: list[str], error: str | None)`
- Produces: `Feedback(kind: str, passed: bool, failed_tests: list[str], counts: dict[str, int], summary: str)`
- Produces: `MemoryEntry(timestamp: str, kind: str, content: str, source: str, run_id: str)`
- Produces: `RunEvent(timestamp: str, run_id: str, step: int, event_type: str, payload: dict[str, Any])`
- Produces: `RunStatus(ok: bool, reason: str, steps: int)`

- [x] **Step 1: Write the failing test**

```python
# tests/test_models.py
from patchpilot.models import Action, Feedback, RunStatus, ToolResult


def test_action_defaults_to_empty_reason():
    action = Action(type="finish", args={})
    assert action.reason == ""


def test_tool_result_records_changed_files():
    result = ToolResult(
        action_type="apply_patch",
        ok=True,
        exit_code=0,
        stdout_summary="patched",
        stderr_summary="",
        changed_files=["src/example.py"],
        error=None,
    )
    assert result.changed_files == ["src/example.py"]


def test_feedback_and_run_status_are_plain_data():
    feedback = Feedback(kind="pytest", passed=True, failed_tests=[], counts={"passed": 3}, summary="3 passed")
    status = RunStatus(ok=True, reason="tests_passed", steps=2)
    assert feedback.passed is True
    assert status.reason == "tests_passed"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'patchpilot'`.

- [x] **Step 3: Write minimal implementation**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "patchpilot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["keyring>=24", "python-dotenv>=1"]

[project.optional-dependencies]
dev = ["pytest>=8"]
openai = ["openai>=1"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `Makefile`:

```makefile
.PHONY: test check

test:
	pytest

check:
	pytest
```

Create `src/patchpilot/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/patchpilot/models.py`:

```python
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
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add pyproject.toml Makefile src/patchpilot/__init__.py src/patchpilot/models.py tests/test_models.py
git commit -m "feat: add project skeleton and data models"
```

---

### Task 2: Guardrails 路径与命令策略

完成提交：`7f85296`

**Files:**
- Create: `src/patchpilot/guardrails.py`
- Test: `tests/test_guardrails.py`

**Interfaces:**
- Consumes: `Action`
- Produces: `RiskDecision(allowed: bool, risk: str, reason: str, requires_approval: bool = False)`
- Produces: `GuardrailPolicy(workspace: Path, interactive_approval: bool = False)`
- Produces: `GuardrailPolicy.check_action(action: Action) -> RiskDecision`

- [x] **Step 1: Write the failing test**

```python
# tests/test_guardrails.py
from pathlib import Path

from patchpilot.guardrails import GuardrailPolicy
from patchpilot.models import Action


def test_blocks_reading_env_file(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    decision = policy.check_action(Action(type="read_file", args={"path": ".env"}))
    assert decision.allowed is False
    assert decision.risk == "high"
    assert ".env" in decision.reason


def test_blocks_path_outside_workspace(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    outside = tmp_path.parent / "outside.py"
    decision = policy.check_action(Action(type="read_file", args={"path": str(outside)}))
    assert decision.allowed is False
    assert decision.risk == "high"


def test_blocks_dangerous_test_command(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    action = Action(type="run_tests", args={"command": "rm -rf ."})
    decision = policy.check_action(action)
    assert decision.allowed is False
    assert "rm -rf" in decision.reason


def test_allows_pytest_command(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    action = Action(type="run_tests", args={"command": "pytest tests/test_sample.py -q"})
    decision = policy.check_action(action)
    assert decision.allowed is True
    assert decision.risk == "low"


def test_medium_risk_requires_approval_only_when_enabled(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path, interactive_approval=True)
    action = Action(type="run_tests", args={"command": "pytest --maxfail=1"})
    decision = policy.check_action(action)
    assert decision.allowed is True
    assert decision.requires_approval is True


def test_unknown_action_is_rejected(tmp_path: Path):
    policy = GuardrailPolicy(workspace=tmp_path)
    decision = policy.check_action(Action(type="delete_everything", args={}))
    assert decision.allowed is False
    assert decision.risk == "high"
    assert "unknown action" in decision.reason
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_guardrails.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'patchpilot.guardrails'`.

- [x] **Step 3: Write minimal implementation**

Create `src/patchpilot/guardrails.py` with:

```python
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

        if action.type == "run_tests":
            return self._check_command(str(action.args.get("command", "")))

        return RiskDecision(True, "low", "action allowed")

    def _check_path(self, raw_path: str) -> RiskDecision:
        path = Path(raw_path)
        resolved = (self.workspace / path).resolve() if not path.is_absolute() else path.resolve()
        workspace = self.workspace.resolve()
        if not (resolved == workspace or workspace in resolved.parents):
            return RiskDecision(False, "high", f"path outside workspace: {raw_path}")

        parts = set(path.parts)
        lowered = raw_path.lower()
        if parts & SENSITIVE_PARTS:
            return RiskDecision(False, "high", f"sensitive path blocked: {raw_path}")
        if any(lowered.endswith(suffix) for suffix in SENSITIVE_SUFFIXES):
            return RiskDecision(False, "high", f"sensitive suffix blocked: {raw_path}")
        if any(word in lowered for word in SENSITIVE_WORDS):
            return RiskDecision(False, "high", f"sensitive name blocked: {raw_path}")
        return RiskDecision(True, "low", "path allowed")

    def _check_command(self, command: str) -> RiskDecision:
        if any(pattern in command for pattern in DANGEROUS_COMMANDS):
            return RiskDecision(False, "high", f"dangerous command blocked: {command}")
        parts = command.split()
        if not parts or parts[0] != "pytest":
            return RiskDecision(False, "high", f"command outside allowlist: {command}")
        if self.interactive_approval and "--maxfail=1" in parts:
            return RiskDecision(True, "medium", "pytest maxfail changes run behavior", True)
        return RiskDecision(True, "low", "pytest command allowed")
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_guardrails.py -v`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/patchpilot/guardrails.py tests/test_guardrails.py
git commit -m "feat: add guardrail policy"
```

---

### Task 3: Pytest Feedback Sensor

完成提交：`ace610c`

**Files:**
- Create: `src/patchpilot/feedback.py`
- Test: `tests/test_feedback.py`

**Interfaces:**
- Consumes: `ToolResult`
- Produces: `parse_pytest_result(result: ToolResult) -> Feedback`
- Produces: `timeout_feedback(command: str) -> Feedback`

- [x] **Step 1: Write the failing test**

```python
# tests/test_feedback.py
from patchpilot.feedback import parse_pytest_result, timeout_feedback
from patchpilot.models import ToolResult


def test_parse_passing_pytest_output():
    result = ToolResult("run_tests", True, 0, "3 passed in 0.10s", "", [], None)
    feedback = parse_pytest_result(result)
    assert feedback.passed is True
    assert feedback.counts["passed"] == 3
    assert feedback.failed_tests == []


def test_parse_failed_test_names():
    output = "FAILED tests/test_math.py::test_add - AssertionError\n1 failed, 2 passed in 0.20s"
    result = ToolResult("run_tests", False, 1, output, "", [], None)
    feedback = parse_pytest_result(result)
    assert feedback.passed is False
    assert feedback.failed_tests == ["tests/test_math.py::test_add"]
    assert feedback.counts["failed"] == 1
    assert feedback.counts["passed"] == 2


def test_timeout_feedback_is_not_passed():
    feedback = timeout_feedback("pytest")
    assert feedback.passed is False
    assert feedback.kind == "pytest"
    assert "timeout" in feedback.summary
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feedback.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'patchpilot.feedback'`.

- [x] **Step 3: Write minimal implementation**

Create `src/patchpilot/feedback.py` with regex parsing for `(\d+) passed`, `(\d+) failed`, `(\d+) error`, and `FAILED <nodeid>`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_feedback.py -v`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/patchpilot/feedback.py tests/test_feedback.py
git commit -m "feat: parse pytest feedback"
```

---

### Task 4: JSONL Memory Store

完成提交：`e5ebbef`

**Files:**
- Create: `src/patchpilot/memory.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Consumes: `MemoryEntry`
- Produces: `MemoryStore(path: Path)`
- Produces: `MemoryStore.append(kind: str, content: str, source: str, run_id: str) -> MemoryEntry`
- Produces: `MemoryStore.recent(limit: int = 5) -> list[MemoryEntry]`

- [x] **Step 1: Write the failing test**

```python
# tests/test_memory.py
from pathlib import Path

from patchpilot.memory import MemoryStore


def test_append_and_read_recent_entries(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.jsonl")
    store.append(kind="decision", content="use mock provider", source="user", run_id="r1")
    store.append(kind="failure", content="test_x failed", source="pytest", run_id="r1")
    entries = store.recent(limit=1)
    assert len(entries) == 1
    assert entries[0].content == "test_x failed"


def test_recent_returns_empty_for_missing_file(tmp_path: Path):
    store = MemoryStore(tmp_path / "missing.jsonl")
    assert store.recent() == []
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'patchpilot.memory'`.

- [x] **Step 3: Write minimal implementation**

Create `src/patchpilot/memory.py` using `json.loads`, `json.dumps`, `datetime.now(timezone.utc).isoformat()`, and `MemoryEntry`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory.py -v`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/patchpilot/memory.py tests/test_memory.py
git commit -m "feat: add jsonl memory store"
```

---

### Task 5: LLM Provider 抽象与 MockLLM

完成提交：`822cdb7`

**Files:**
- Create: `src/patchpilot/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `Action`
- Produces: `class LLMProvider(Protocol): next_action(context: dict[str, Any]) -> Action`
- Produces: `MockLLM(actions: list[Action])`
- Produces: `OpenAILLM(api_key: str, model: str = "gpt-4.1-mini")`

- [x] **Step 1: Write the failing test**

```python
# tests/test_llm.py
import pytest

from patchpilot.llm import MockLLM, OpenAILLM
from patchpilot.models import Action


def test_mock_llm_returns_scripted_actions_in_order():
    llm = MockLLM([Action("list_files", {}), Action("finish", {"ok": True})])
    assert llm.next_action({}).type == "list_files"
    assert llm.next_action({}).type == "finish"


def test_mock_llm_returns_finish_after_script_exhausted():
    llm = MockLLM([])
    action = llm.next_action({})
    assert action.type == "finish"
    assert action.args["ok"] is False


def test_openai_llm_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        OpenAILLM(api_key="")
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'patchpilot.llm'`.

- [x] **Step 3: Write minimal implementation**

Create `src/patchpilot/llm.py`. `OpenAILLM.next_action` should import `openai` lazily and raise `RuntimeError("OpenAI provider is not implemented for offline tests")` until Task 11 wires optional behavior.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm.py -v`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/patchpilot/llm.py tests/test_llm.py
git commit -m "feat: add llm provider abstraction"
```

---

### Task 6: Credential Manager

完成提交：`d9d0a7d`

**Files:**
- Create: `src/patchpilot/credentials.py`
- Test: `tests/test_credentials.py`

**Interfaces:**
- Produces: `CredentialManager(service_name: str = "patchpilot-openai")`
- Produces: `CredentialManager.status() -> bool`
- Produces: `CredentialManager.set_key(key: str) -> None`
- Produces: `CredentialManager.clear() -> None`
- Produces: `CredentialManager.get_key() -> str | None`

- [x] **Step 1: Write the failing test**

```python
# tests/test_credentials.py
from patchpilot.credentials import CredentialManager


class FakeKeyring:
    def __init__(self):
        self.value = None

    def get_password(self, service, username):
        return self.value

    def set_password(self, service, username, password):
        self.value = password

    def delete_password(self, service, username):
        self.value = None


def test_status_set_and_clear_without_printing_key(capsys):
    fake = FakeKeyring()
    manager = CredentialManager(keyring_backend=fake)
    assert manager.status() is False
    manager.set_key("sk-test-secret")
    assert manager.status() is True
    assert manager.get_key() == "sk-test-secret"
    manager.clear()
    assert manager.status() is False
    captured = capsys.readouterr()
    assert "sk-test-secret" not in captured.out
    assert "sk-test-secret" not in captured.err
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_credentials.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'patchpilot.credentials'`.

- [x] **Step 3: Write minimal implementation**

Create `src/patchpilot/credentials.py` with injectable keyring backend. Use username `"openai-api-key"`. `get_key()` checks keyring first, then `OPENAI_API_KEY` from `.env` loaded with `dotenv.load_dotenv()`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_credentials.py -v`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/patchpilot/credentials.py tests/test_credentials.py
git commit -m "feat: add credential manager"
```

---

### Task 7: Tool Dispatcher

完成提交：`41e45e7`

**Files:**
- Create: `src/patchpilot/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `Action`, `ToolResult`, `GuardrailPolicy`, `MemoryStore`
- Produces: `ToolDispatcher(workspace: Path, guardrails: GuardrailPolicy, memory: MemoryStore | None = None, timeout_seconds: int = 20)`
- Produces: `ToolDispatcher.dispatch(action: Action) -> ToolResult`

- [x] **Step 1: Write the failing test**

```python
# tests/test_tools.py
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
    result = dispatcher.dispatch(Action("remember", {"kind": "decision", "content": "use pytest", "run_id": "r1"}))
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'patchpilot.tools'`.

- [x] **Step 3: Write minimal implementation**

Create `src/patchpilot/tools.py` with:

- `list_files`: recursively list files under workspace, skipping `.git`, `.patchpilot`, `.env`, `.ssh`, `*.pem`, names containing `token` or `secret`.
- `read_file`: guard the path, read UTF-8 text, return at most the first 4000 characters in `stdout_summary`.
- `apply_patch`: accept `{"patch": "<unified diff>"}`; parse one-file unified diff headers `--- a/<path>` and `+++ b/<path>`; reject `/dev/null`; apply hunks that contain context lines (` `), removed lines (`-`), and added lines (`+`) to the target file; return changed relative path.
- `run_tests`: guard command, run with `subprocess.run(command.split(), cwd=workspace, timeout=timeout_seconds, capture_output=True, text=True)`.
- `remember`: call `MemoryStore.append(kind, content, source="agent", run_id)`.
- `finish`: return `ToolResult("finish", True, 0, "finish", "", [], None)`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools.py -v`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/patchpilot/tools.py tests/test_tools.py
git commit -m "feat: add guarded tool dispatcher"
```

---

### Task 8: Agent Loop 与停止策略

**Files:**
- Create: `src/patchpilot/agent.py`
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: `Action`, `RunStatus`, `MockLLM`, `ToolDispatcher`, `parse_pytest_result`
- Produces: `AgentLoop(llm, dispatcher, max_steps: int = 5, run_id: str = "run")`
- Produces: `AgentLoop.run(task: str, test_command: str) -> RunStatus`
- Produces: `AgentLoop.events: list[RunEvent]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent.py
from pathlib import Path

from patchpilot.agent import AgentLoop
from patchpilot.guardrails import GuardrailPolicy
from patchpilot.llm import MockLLM
from patchpilot.memory import MemoryStore
from patchpilot.models import Action
from patchpilot.tools import ToolDispatcher


def make_loop(tmp_path: Path, actions):
    dispatcher = ToolDispatcher(tmp_path, GuardrailPolicy(tmp_path), MemoryStore(tmp_path / ".patchpilot" / "memory.jsonl"))
    return AgentLoop(MockLLM(actions), dispatcher, max_steps=3, run_id="r1")


def test_loop_stops_on_finish(tmp_path: Path):
    loop = make_loop(tmp_path, [Action("finish", {"ok": True})])
    status = loop.run(task="stop", test_command="pytest")
    assert status.ok is True
    assert status.reason == "finish"
    assert len(loop.events) == 1


def test_loop_stops_when_tests_pass(tmp_path: Path):
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    loop = make_loop(tmp_path, [Action("run_tests", {"command": "pytest -q"})])
    status = loop.run(task="run tests", test_command="pytest -q")
    assert status.ok is True
    assert status.reason == "tests_passed"


def test_loop_stops_on_blocked_action(tmp_path: Path):
    loop = make_loop(tmp_path, [Action("read_file", {"path": ".env"})])
    status = loop.run(task="read secret", test_command="pytest")
    assert status.ok is False
    assert status.reason == "blocked_action"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'patchpilot.agent'`.

- [ ] **Step 3: Write minimal implementation**

Implement loop: for each step, call LLM, dispatch action, append `RunEvent`, parse pytest result when action type is `run_tests`, return `RunStatus(True, "tests_passed", step)` when feedback passes, return `RunStatus(False, "blocked_action", step)` when dispatch result is blocked, and return `RunStatus(False, "max_steps", max_steps)` after exhaustion.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/patchpilot/agent.py tests/test_agent.py
git commit -m "feat: add agent loop"
```

---

### Task 9: argparse CLI

**Files:**
- Modify: `pyproject.toml`
- Create: `src/patchpilot/__main__.py`
- Create: `src/patchpilot/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `AgentLoop`, `CredentialManager`
- Produces: `build_parser() -> argparse.ArgumentParser`
- Produces: `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from patchpilot.cli import main


def test_run_requires_task():
    code = main(["run", "--test-cmd", "pytest"])
    assert code == 2


def test_auth_status_does_not_print_key(monkeypatch, capsys):
    class FakeManager:
        def status(self):
            return True

    monkeypatch.setattr("patchpilot.cli.CredentialManager", lambda: FakeManager())
    code = main(["auth", "status"])
    captured = capsys.readouterr()
    assert code == 0
    assert "configured" in captured.out
    assert "sk-" not in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'patchpilot.cli'`.

- [ ] **Step 3: Write minimal implementation**

Implement `run` and `auth` subcommands. Add `[project.scripts] patchpilot = "patchpilot.cli:main"` to `pyproject.toml`. Create `src/patchpilot/__main__.py` so `python -m patchpilot` imports `patchpilot.cli.main` only after Task 9 creates `cli.py`. `run` creates `GuardrailPolicy`, `MemoryStore`, `ToolDispatcher`, `MockLLM([Action("run_tests", {"command": args.test_cmd})])` for default mock demo, then invokes `AgentLoop`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/patchpilot/__main__.py src/patchpilot/cli.py tests/test_cli.py
git commit -m "feat: add argparse cli"
```

---

### Task 10: README、AGENT_LOG 与分发说明

**Files:**
- Create: `README.md`
- Create: `AGENT_LOG.md`
- Modify: `SPEC_PROCESS.md`

**Interfaces:**
- Consumes: implemented CLI commands.
- Produces: documented commands for local install, mock run, Docker run, auth status/set/clear, known limits.

- [ ] **Step 1: Write documentation acceptance check**

Run: `rg -n "patchpilot run|docker build|auth status|keyring|Mock|pytest|已知限制" README.md`

Expected before writing docs: FAIL because `README.md` does not exist.

- [ ] **Step 2: Write README.md**

Include these exact command blocks:

```bash
python -m pip install -e ".[dev]"
make test
patchpilot run --task "fix failing tests" --test-cmd "pytest"
patchpilot auth status
patchpilot auth set
patchpilot auth clear
docker build -t patchpilot .
docker run --rm -it -v "$PWD:/workspace" patchpilot run --task "fix failing tests" --test-cmd "pytest"
```

Explain in Chinese: mock mode requires no key; OpenAI mode reads keyring first and `.env` only as plaintext development fallback; status never prints plaintext key; v1 only supports Python + pytest.

- [ ] **Step 3: Write AGENT_LOG.md**

Record initial entries for:

- brainstorming used to select TDD Patch Agent Harness.
- writing-plans used to generate PLAN.
- each future task must append timestamp, task number, skill, prompt/context, result, human intervention, lesson.

- [ ] **Step 4: Verify documentation**

Run: `rg -n "patchpilot run|docker build|auth status|keyring|Mock|pytest|已知限制" README.md`

Expected: PASS with matching lines.

- [ ] **Step 5: Commit**

```bash
git add README.md AGENT_LOG.md SPEC_PROCESS.md
git commit -m "docs: add usage and agent log"
```

---

### Task 11: Docker 与 CI

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: Docker image command `docker build -t patchpilot .`
- Produces: CI jobs `test` and `docker-build`

- [ ] **Step 1: Write expected Dockerfile check**

Run: `test -f Dockerfile`

Expected before writing file: FAIL with exit code `1`.

- [ ] **Step 2: Write Dockerfile**

Use Python 3.11 slim, install package, set workdir `/workspace`, and entrypoint `patchpilot`.

- [ ] **Step 3: Write .dockerignore**

Ignore:

```gitignore
.git
.pytest_cache
__pycache__
*.pyc
.env
.ssh
*.pem
.patchpilot
```

- [ ] **Step 4: Write GitHub Actions CI**

Create `.github/workflows/ci.yml` with:

```yaml
name: ci
on:
  push:
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install -e ".[dev]"
      - run: make test
  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t patchpilot .
```

- [ ] **Step 5: Verify Dockerfile and CI files exist**

Run: `test -f Dockerfile && test -f .dockerignore && test -f .github/workflows/ci.yml`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile .dockerignore .github/workflows/ci.yml
git commit -m "ci: add docker build workflow"
```

---

### Task 12: 冷启动验证

完成提交：`c4b2487`

**Files:**
- Modify: `SPEC_PROCESS.md`

**Interfaces:**
- Consumes: `SPEC.md` and `PLAN.md`
- Produces: documented cold-start validation result in `SPEC_PROCESS.md`

- [x] **Step 1: Prepare cold-start prompt**

Use this prompt with a different type of coding agent:

```text
你是一个全新的 coding agent，不能访问先前设计对话。只能使用 SPEC.md 和 PLAN.md。请从 PLAN.md 中选择 Task 1 和 Task 2。必须遵循 TDD：先写失败测试并运行，确认失败后，再实现最少代码使测试通过。如果任何需求存在歧义，请暂停提问，不要猜测。
```

- [x] **Step 2: Record validation result**

In `SPEC_PROCESS.md`, add a section `## 7. 冷启动验证记录` with:

- 使用的第二 agent 类型。
- 它是否暂停提问。
- 暴露的 SPEC/PLAN 缺陷。
- 产出与预期差距。
- 根据反馈做出的修订。

- [x] **Step 3: Verify record exists**

Run: `rg -n "冷启动验证记录|第二 agent|SPEC/PLAN 缺陷|产出与预期差距" SPEC_PROCESS.md`

Expected: PASS with matching lines.

- [x] **Step 4: Commit**

```bash
git add SPEC_PROCESS.md
git commit -m "docs: record cold-start validation"
```

---

### Task 13: Reflection 与最终验收

**Files:**
- Create: `REFLECTION.md`
- Modify: `PLAN.md`
- Modify: `AGENT_LOG.md`

**Interfaces:**
- Consumes: all completed tasks and commits.
- Produces: final reflection and checked-off plan.

- [ ] **Step 1: Write reflection acceptance check**

Run: `test -f REFLECTION.md`

Expected before writing file: FAIL with exit code `1`.

- [ ] **Step 2: Write REFLECTION.md**

Use 1500-2500 Chinese characters. Cover:

- Superpowers 如何帮助从模糊想法变成 SPEC/PLAN。
- TDD 对 agentic SE 的约束作用。
- Mock LLM 为什么是 harness 机制验证的关键。
- 凭据治理和分发的工程价值。
- 哪些 AI 建议被采纳、修改或拒绝。
- 当前方法论的不足：冷启动成本、技能流程开销、subagent 上下文断裂风险。

- [ ] **Step 3: Update PLAN.md task checkboxes**

Mark completed tasks with `- [x]` only after corresponding commits exist. Add commit hash beside each completed task heading in this format:

```markdown
Task 1 完成提交：`<commit-hash>`
```

- [ ] **Step 4: Run final verification**

Run: `make test`

Expected: PASS.

Run: `docker build -t patchpilot .`

Expected: PASS.

Run: `rg -n "OPENAI_API_KEY=sk-|sk-[A-Za-z0-9]" .`

Expected: no matches.

- [ ] **Step 5: Commit**

```bash
git add REFLECTION.md PLAN.md AGENT_LOG.md
git commit -m "docs: add final reflection"
```

---

## Plan 自审清单

- SPEC §1 问题陈述：Task 8、Task 9、Task 10 覆盖 CLI harness 目标。
- SPEC §2 用户故事：Task 5、Task 6、Task 7、Task 8、Task 9、Task 10 覆盖默认 mock、OpenAI 凭据、日志审计、安全阻止和离线测试。
- SPEC §3 功能规约：Task 1 到 Task 9 覆盖 CLI、loop、LLM、tools、guardrails、feedback、memory、credentials。
- SPEC §4 非功能性需求：Task 2、Task 3、Task 6、Task 7、Task 8、Task 10、Task 11 覆盖安全、性能边界、可用性和可观测性。
- SPEC §5 系统架构：文件结构与 Task 1 到 Task 9 一一映射。
- SPEC §6 数据模型：Task 1 覆盖。
- SPEC §7 凭据与分发：Task 6、Task 10、Task 11 覆盖。
- SPEC §8 技术选型：Global Constraints 与 Task 1、Task 9、Task 11 覆盖。
- SPEC §9 验收标准：Task 1 到 Task 13 覆盖。
- SPEC §10 领域与机制设计：Task 2、Task 3、Task 4、Task 5、Task 7、Task 8 覆盖。
- SPEC §11 风险与对策：Task 2、Task 5、Task 7、Task 10、Task 11 覆盖。
