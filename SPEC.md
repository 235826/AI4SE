# PatchPilot 规格说明

## 1. 问题陈述

PatchPilot 是一个面向 Python 项目的、测试驱动的 Coding Agent Harness。它帮助开发者在本地工作区中运行一个受控的修复循环：查看文件、应用补丁、运行 `pytest`、读取客观反馈，并在测试通过或触发安全/迭代边界时停止。

目标用户是希望理解 coding agent harness 在 LLM 之外如何工作的学生或工程师。本项目值得做，是因为它把一个可靠 agent 所依赖的工程机制显性化：工具分发、确定性反馈、治理护栏、记忆、凭据管理和分发。项目目标不是做一个生产级 IDE agent，而是实现一个最小但真实的 harness 内核，并保证核心行为在使用 mock LLM 时仍可测试。

## 2. 用户故事

1. 作为开发者，我希望在 Python 项目中运行 `patchpilot run --task "fix failing tests" --test-cmd "pytest"`，以便 harness 能启动一个有边界的测试修复循环。
2. 作为开发者，我希望 PatchPilot 默认使用 mock LLM，以便在没有付费 API 的情况下测试和演示 harness。
3. 作为开发者，我希望可选接入 OpenAI，并通过安全凭据存储读取 key，以便尝试真实模型驱动的动作，同时不把凭据硬编码进源码。
4. 作为 reviewer，我希望每个工具动作和结果都被结构化记录，以便审计 agent 做过什么。
5. 作为关注安全的用户，我希望危险命令和敏感文件访问被阻止或要求人工批准，以免 agent 破坏项目或泄露秘密。
6. 作为维护者，我希望 agent loop、工具、反馈、护栏、记忆、凭据和 CLI 都有确定性单元测试，以便在没有真实 LLM 的情况下验证 harness 机制。

## 3. 功能规约

### 3.1 CLI

输入：

- `patchpilot run --task <text> --test-cmd <command>`
- `--provider mock|openai`
- `--max-steps <n>`
- `--workspace <path>`
- `--interactive-approval`
- `patchpilot auth status|set|clear`

行为：

- 校验工作区和参数。
- 默认使用 `mock` provider。
- 只有用户显式指定时才使用 OpenAI。
- 当测试通过或 agent 成功 `finish` 时退出码为 `0`。
- 当修复失败、动作被阻止、配置无效或步数耗尽时退出码非 `0`。

边界条件：

- 缺少 task：以用法错误拒绝。
- 测试命令不在 allowlist：在 loop 启动前拒绝。
- 工作区路径不在允许访问范围内：拒绝。

### 3.2 Agent Loop

输入：

- 任务文本。
- 工作区元数据。
- 记忆片段。
- 上一步工具结果。
- LLM provider。

行为：

1. 构建上下文。
2. 调用 `LLMProvider.next_action(context)`。
3. 解析结构化 action。
4. 执行 guardrail 检查。
5. 将 action 分发给工具。
6. 把工具输出转换为结构化 feedback。
7. 将 feedback 加入下一轮上下文。
8. 达到终止条件时停止。

输出：

- 最终运行状态。
- 结构化事件日志。
- 更新后的记忆条目。

停止条件：

- 收到 `finish` action。
- `pytest` 通过。
- 达到 `--max-steps`。
- 连续两次无效 action。
- 危险 action 被拒绝。
- 工具执行超时。

### 3.3 LLM Provider

Provider：

- `MockLLM`：用于测试和演示的确定性脚本化动作。
- `OpenAILLM`：可选真实 provider，使用单次 chat completion 风格调用。

输入：

- 结构化上下文对象。

输出：

- 一个结构化 action：
  - `list_files`
  - `read_file`
  - `apply_patch`
  - `run_tests`
  - `remember`
  - `finish`

错误处理：

- provider 配置无效时，在 loop 启动前返回配置错误。
- LLM 输出无效时，计为一次无效 action。

### 3.4 Tool Dispatcher

工具：

- `list_files`：列出工作区内非敏感文件。
- `read_file`：读取工作区文件，除非被 guardrail 阻止。
- `apply_patch`：对允许路径应用 unified patch。
- `run_tests`：运行允许的测试命令。
- `remember`：写入一条记忆事件。
- `finish`：产生终止状态。

所有工具输入和输出都必须结构化。日志必须对疑似秘密值做脱敏。

### 3.5 Guardrails

Guardrail 必须是确定性代码，而不是 prompt 里的提醒。

阻止的动作：

- 未知 action 类型。
- 读写工作区外路径。
- 读取 `.env`、`.ssh/`、私钥、`*.pem`、`*token*` 或 `*secret*`。
- 运行不在 allowlist 中的命令。
- 运行危险 shell 模式，例如 `rm -rf`、`curl | sh`、发布命令、`git push` 或包发布命令。
- 对禁止路径应用 patch。

默认行为：

- 未知 action 默认按高风险拒绝，并计为一次无效 action。
- 非交互模式直接拒绝危险 action。
- `--interactive-approval` 模式会对中风险 action 暂停并请求人工批准。v1 中风险 action 仅包括仍在 `pytest` allowlist 内、但会改变测试运行完整性的参数，例如 `pytest --maxfail=1`。
- 高风险 action 即使在交互模式下也始终拒绝。

### 3.6 Feedback Sensors

`pytest` sensor 解析：

- exit code。
- passed、failed、error 数量。
- 失败测试名。
- 简短 traceback 摘要。
- 测试命令是否满足通过标准。

这些 feedback 以结构化对象回灌给 agent loop，而不是只把原始终端文本塞回上下文。

### 3.7 Memory Store

存储：

- `.patchpilot/memory.jsonl`。

条目：

- 项目规则。
- 用户决策。
- 已尝试动作。
- 最近失败摘要。
- 运行摘要。

Context builder 只注入相关的近期记忆，不把完整历史全量加载给 LLM。

### 3.8 Credentials

命令：

- `patchpilot auth status`
- `patchpilot auth set`
- `patchpilot auth clear`

行为：

- `status` 绝不打印明文 key。
- `set` 使用隐藏输入。
- `clear` 删除已存储 key。

凭据来源优先级：

1. 通过 Python `keyring` 读取操作系统钥匙串。
2. `.env` 仅作为开发 fallback。
3. 隐藏交互式输入，并保存到 keyring。

## 4. 非功能性需求

### 4.1 性能

- 默认运行必须在配置的 step limit 内结束。
- 工具 timeout 防止测试命令无限运行。
- 通过记忆摘要和近期结果选择控制上下文大小。

### 4.2 安全

威胁模型：

- LLM 可能请求不安全的文件访问或 shell 命令。
- 工作区可能包含秘密。
- 日志可能意外捕获敏感值。
- API key 可能通过源码、命令历史、日志或明文配置泄露。

对策：

- 默认 mock provider 不需要任何凭据。
- OpenAI key 尽可能存储在操作系统钥匙串中。
- `.env` 只作为开发 fallback，并明确记录其明文风险。
- key 录入使用隐藏输入。
- 日志对秘密值脱敏。
- 敏感路径由确定性 guardrail 代码阻止。
- 测试命令执行使用 allowlist。

### 4.3 可用性

- CLI 错误应说明失败前置条件和下一步修复动作。
- README 必须包含本地和 Docker 工作流。
- Mock 模式必须无需外部服务即可运行。

### 4.4 可观测性

- 每次运行都记录结构化事件：请求的 action、guardrail 结果、工具结果、feedback 摘要和停止原因。
- 日志不包含明文 API key。

## 5. 系统架构

组件：

- `cli`：参数解析、auth 命令、run 命令。
- `agent`：主循环、context builder、停止策略。
- `llm`：provider 接口、mock provider、OpenAI provider。
- `tools`：文件系统工具、patch 应用、测试 runner。
- `guardrails`：路径策略、命令策略、审批策略。
- `feedback`：pytest parser 和 feedback model。
- `memory`：JSONL 存储和检索。
- `credentials`：keyring 与 `.env` 凭据加载。
- `logging`：结构化事件日志和脱敏。

数据流：

1. CLI 构造 run request。
2. Context builder 组合任务、工作区摘要、记忆和上一轮 feedback。
3. LLM provider 返回结构化 action。
4. Guardrails 批准、拒绝或请求人工批准。
5. Tool dispatcher 执行已批准 action。
6. Feedback sensors 把结果转换为结构化 feedback。
7. Agent loop 记录事件，并决定继续或停止。

外部依赖：

- Python 3.11+。
- `pytest` 用于测试。
- `keyring` 用于操作系统凭据存储。
- `python-dotenv` 用于开发环境 `.env` fallback。
- OpenAI API 作为可选 provider。
- Docker 用于容器分发。

## 6. 数据模型

### Action

- `type`：action 名称。
- `args`：action 参数。
- `reason`：provider 给出的简短理由。

### ToolResult

- `action_type`
- `ok`
- `exit_code`
- `stdout_summary`
- `stderr_summary`
- `changed_files`
- `error`

### Feedback

- `kind`：`pytest`、`guardrail`、`tool` 或 `loop`。
- `passed`
- `failed_tests`
- `counts`
- `summary`

### MemoryEntry

- `timestamp`
- `kind`
- `content`
- `source`
- `run_id`

### RunEvent

- `timestamp`
- `run_id`
- `step`
- `event_type`
- `payload`

## 7. 凭据与分发设计

凭据设计：

- Mock 模式不需要 key。
- OpenAI 模式需要从 keyring 或 `.env` 获取 key。
- 首次配置使用 `patchpilot auth set`，通过隐藏输入录入。
- status 和日志绝不显示明文 key。
- 用户可以通过 auth 命令更新或清除凭据。

分发：

- 主分发方式：Docker 镜像。
- 开发方式：editable Python install。

Docker 命令：

```bash
docker build -t patchpilot .
docker run --rm -it -v "$PWD:/workspace" patchpilot run --task "fix failing tests" --test-cmd "pytest"
```

已知限制：

- Docker 内的 keyring 集成依赖平台，因此容器运行应优先使用 mock 模式，或使用文档中明确说明的非秘密演示配置。
- Docker 内真实 OpenAI 使用需要用户显式进行安全配置。
- v1 只面向使用 pytest 的 Python 项目。

## 8. 技术选型与理由

- 语言：Python。理由是项目目标是 pytest 修复循环，并且 Python 在 CLI、测试、keyring 和 Docker 支持上都直接。
- CLI 框架：标准库 `argparse`。理由是减少运行时依赖，降低冷启动实现歧义。
- 测试框架：pytest。
- 凭据库：keyring。
- LLM provider：默认 mock，可选 OpenAI API。
- 存储：JSONL。理由是简单、可审计、易测试，适合 memory 和 run event。
- 分发：Docker 作为必做路径，editable pip install 用于开发。
- UI：无前端，因此 Open Design 不适用。

## 9. 验收标准

1. `make test` 或等价命令可一键运行全部测试。
2. Mock LLM 测试可在无网络情况下验证 agent loop。
3. Guardrail 测试证明危险路径和危险命令会被阻止。
4. Pytest feedback parser 测试覆盖通过、失败、error 和 timeout。
5. Credential 测试使用 mock keyring，且不打印明文 key。
6. CLI 测试覆盖 `run` 和 `auth` 命令。
7. Docker 镜像能在 CI 中成功构建。
8. README 说明安装、运行、Docker、凭据和已知限制。
9. `SPEC.md`、`PLAN.md`、`SPEC_PROCESS.md`、`AGENT_LOG.md` 和 `REFLECTION.md` 存在。
10. 源码、测试、日志和配置中不得出现真实秘密。

## 10. 领域与机制设计

PatchPilot 实现作业要求的四类 harness 机制。

### 10.1 动作与工具

Action 是由 LLM provider 产生的结构化对象，只能通过 dispatcher 执行。Agent 不能直接运行任意代码。

### 10.2 客观反馈信号

`pytest` sensor 是确定性代码。它解析命令结果，返回 pass/fail 状态、失败测试和摘要。该 feedback 驱动下一轮 loop。

### 10.3 危险动作

Guardrail 层在执行前检测危险文件路径、shell 命令和 patch 目标。阻止决策可通过 mock action 单测验证，不依赖 LLM 自觉遵守提示词。

### 10.4 记忆

Memory 是显式本地数据。Context builder 为下一次 LLM 调用选择有界的 memory 条目。测试可以在没有真实 LLM 的情况下验证读、写、过滤和上下文注入。

## 11. 风险与对策

风险：

- 真实 LLM 输出可能不符合 action schema。
- 如果 diff 与工作区不匹配，patch 应用可能失败。
- Docker 凭据存储在不同平台上表现不同。
- 过宽的 shell 支持会削弱安全边界。

对策：

- 将无效 provider 输出计为 invalid action，并设置停止阈值。
- v1 工具保持窄而确定。
- Docker 演示默认使用 mock 模式。
- README 明确记录 OpenAI-in-Docker 限制。

已决实现选择：

- CLI 使用 `argparse`。
- v1 包含 `--interactive-approval`，用于中风险动作审批。
- 高风险动作始终不可覆盖。
