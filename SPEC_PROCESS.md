# PatchPilot SPEC 过程文档

## 1. Brainstorming 背景

作业要求使用 Superpowers 完成 AI4SE 期末项目。当前选择的是项目 A：Coding Agent Harness。该项目必须实现自己的 harness 内核，而不是配置现成 agent 框架。项目还必须包含确定性机制：工具、反馈、护栏、记忆、TDD、凭据、分发和过程文档。

目前已使用的 Superpowers 技能：

- `superpowers:using-superpowers`：确认后续任务必须先调用相关技能。
- `superpowers:brainstorming`：用于在实现前澄清项目目的、范围、架构、安全、凭据、分发和测试策略。

## 2. 关键 Brainstorming 节点

### 迭代 1：项目类型

问题：

应该构建哪一种 Coding Agent Harness？

考虑过的选项：

- TDD Patch Agent Harness。
- Safe Shell Coding Agent。
- Memory-Aware Coding Agent。

决策：

选择 TDD Patch Agent Harness。

理由：

它最贴合作业 A 的要求，可以自然覆盖 agent loop、工具分发、客观测试反馈、危险动作处理、记忆和 mock LLM 测试。

### 迭代 2：目标技术栈

问题：

第一版是否以 Python + pytest 项目为目标？

决策：

是。

理由：

Python 和 pytest 让确定性测试、fixture 项目、CLI 行为、keyring 集成和 Docker 分发都更直接。这能让项目聚焦在 harness 机制，而不是多语言支持。

### 迭代 3：LLM 与凭据

问题：

是否把 OpenAI 作为可选真实 provider，同时让 mock LLM 成为默认和主要验证路径？

决策：

是。

理由：

作业要求移除真实 LLM 后核心机制仍可测试。Mock-first 设计直接满足这一点。可选 OpenAI 支持用于展示真实 provider 的准备度，但不让测试变得不稳定或依赖凭据。

### 迭代 4：分发方式

问题：

是否把 Docker 作为必做分发路径，把 editable pip install 作为开发路径？

决策：

是。

理由：

Docker 能清楚回答“别人如何在一台新机器上获取并运行项目”。本地 pip install 仍用于开发和测试。

### 迭代 5：核心模块

问题：

v1 是否限制为六个核心模块：loop、LLM provider、tool dispatcher、guardrails、feedback sensors 和 memory store？

决策：

是。

理由：

这个范围有足够工程深度，同时不会把项目变成过宽、失焦的 agent 产品。它也直接映射到作业要求的 harness 机制。

### 迭代 6：整体架构路线

问题：

应该采用哪种整体设计？

考虑过的选项：

- 确定性优先的 CLI Harness。
- 真实 LLM 优先的自动修复工具。
- 安全治理优先的 Shell Harness。

决策：

采用确定性优先的 CLI Harness。

理由：

它最适合 TDD、mock LLM 验证和评分标准。真实 LLM 行为作为可选扩展，而不是正确性的基础。

## 3. AI 建议中已采纳的部分

已采纳：

- 使用 `patchpilot` 作为项目名。
- 默认 provider 使用 mock LLM。
- OpenAI 作为可选 provider。
- 使用 JSONL 存储 memory 和事件日志。
- Docker 作为主要分发形态。
- v1 不做 Web UI、向量数据库、多 agent 并发和宽泛 shell 访问。

采纳理由：

这些建议降低范围风险，并让项目聚焦在作业要求的 harness 机制上。

## 4. AI 建议中暂缓或拒绝的部分

暂缓：

- 完整交互式可视化 UI。
- 多语言项目支持。
- 向量数据库记忆。
- 真实 PR 自动化。
- 任意 shell 命令执行。

暂缓理由：

这些功能都会增加复杂度，但不会显著增强核心评分信号。作业更重视机制深度、安全和可验证性，而不是宽泛产品表面。

## 5. 当前 SPEC 质量说明

当前 `SPEC.md` 已明确以下要求：

- 项目实现自己的 loop 和工具分发。
- 核心机制是确定性的，并且可用 mock LLM 测试。
- 真实 OpenAI 支持是可选项。
- 凭据绝不硬编码或写入日志。
- Docker 是主要分发路径。
- v1 面向使用 pytest 的 Python 项目。
- CLI 使用 `argparse`，降低实现歧义。
- 中风险动作可通过 `--interactive-approval` 人工审批，高风险动作始终拒绝。

## 6. 待执行的冷启动验证

正式实现前，应让另一个不同类型的 agent 只读取 `SPEC.md` 和 `PLAN.md`，尝试完成 1-2 个 task，不提供任何额外上下文。验证结果必须记录在本文档中。

冷启动提示草稿：

```text
你是一个全新的 coding agent，不能访问先前设计对话。只能使用 SPEC.md 和 PLAN.md。请从 PLAN.md 中选择一到两个早期实现任务。必须遵循 TDD：先写失败测试并运行，确认失败后，再实现最少代码使测试通过。如果任何需求存在歧义，请暂停提问，不要猜测。
```

验证后需要记录：

- 第二个 agent 在哪里暂停。
- SPEC 或 PLAN 缺少了哪些假设。
- 是否出现了与原意不同的解读。
- 根据反馈对 SPEC/PLAN 做了哪些修订。
- 关键修订前后 diff 片段。

## 7. 冷启动验证记录

使用的第二 agent 类型：

- 使用 multi-agent 工具启动的新鲜子 agent，模型为 `gpt-5.6-luna`。
- `fork_context=false`，不继承本会话历史。
- 只要求它使用 `SPEC.md` 和 `PLAN.md`，尝试 Task 1 与 Task 2。

执行结果：

- 子 agent 在派生工作区 `/private/tmp/patchpilot-task12` 中完成 Task 1 与 Task 2。
- 子 agent 提交 hash：`91c0254014cd13748d95594289c6e2cd7d193a9c`。
- TDD 红灯记录：
  - `pytest tests/test_models.py -v`：按预期因缺少 `patchpilot` 失败。
  - `pytest tests/test_guardrails.py -v`：按预期失败。
- 最终验证：
  - `PYTHONDONTWRITEBYTECODE=1 pytest -v`：`8 passed`。
  - `git diff --check`：通过。
  - 子 agent 工作区干净。

它是否暂停提问：

- 没有暂停提问。它完成了 Task 1 与 Task 2，但在最终报告中列出了 3 个 SPEC/PLAN 缺陷。

暴露的 SPEC/PLAN 缺陷：

- `PLAN.md` 的 Task 1 创建 `src/patchpilot/__main__.py`，但 `__main__.py` 引用尚未实现的 `patchpilot.cli`。Task 1 没有入口导入测试，因此冷启动 agent 可以完成单测，但留下了潜在导入问题。
- `PLAN.md` 的 Task 2 测试指定 `pytest --maxfail=1` 为中风险，但 `SPEC.md` 没有解释哪些动作属于中风险。
- `SPEC.md` 和 `PLAN.md` 没有定义未知 action 类型应允许、拒绝还是报错。

产出与预期差距：

- 产出满足 Task 1 与 Task 2 的局部测试，但暴露出 plan 中跨 task 依赖边界不够清楚的问题。
- 子 agent 对 guardrail 的默认未知 action 策略没有明确依据，只能从测试和实现习惯推断。

根据反馈做出的修订：

- 将 `src/patchpilot/__main__.py` 从 Task 1 移到 Task 9，在 `cli.py` 存在后再创建。
- 将 `[project.scripts] patchpilot = "patchpilot.cli:main"` 从 Task 1 移到 Task 9，避免安装后入口指向尚未存在的模块。
- 在 `SPEC.md` 明确：未知 action 默认按高风险拒绝，并计为一次无效 action。
- 在 `SPEC.md` 明确：v1 中风险 action 仅包括仍在 `pytest` allowlist 内、但会改变测试运行完整性的参数，例如 `pytest --maxfail=1`。
- 在 `PLAN.md` Task 2 增加未知 action 拒绝测试和对应实现片段。

关键修订前后 diff 摘要：

```diff
- Task 1: Create src/patchpilot/__main__.py
+ Task 9: Create src/patchpilot/__main__.py

- [project.scripts]
- patchpilot = "patchpilot.cli:main"
+ Task 9 创建 CLI 后再加入 [project.scripts]

+ 未知 action 默认按高风险拒绝，并计为一次无效 action。
+ v1 中风险 action 仅包括仍在 pytest allowlist 内、但会改变测试运行完整性的参数，例如 pytest --maxfail=1。
```

## 8. Task 10 文档与分发记录

Task 10 使用 `superpowers:using-superpowers` 确认技能流程，并使用
`superpowers:verification-before-completion` 在提交前执行新鲜验证。按照
`.superpowers/sdd/PLAN/task-10-brief.md`，先运行 documentation acceptance check；由于
`README.md` 尚不存在，该检查以退出码 2 失败。随后新增中文 `README.md` 和
`AGENT_LOG.md`，并保留本文件已有的 brainstorming、计划与冷启动证据。

README 明确记录：Mock 模式无需 key；OpenAI 模式优先读取 keyring，`.env` 仅作为明文开发回退；
`auth status` 不打印明文 key；支持本地 editable 安装、Docker 命令和 v1 的 Python + pytest 已知限制。

后续任务必须在 `AGENT_LOG.md` 追加时间戳、task number、skill、prompt/context、result、human
intervention 和 lesson，不得记录真实凭据。
