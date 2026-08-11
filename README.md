# PatchPilot

PatchPilot 是一个面向 Python 项目的 TDD Coding Agent Harness。它用确定性的工具、pytest 反馈、护栏和记忆组成 agent loop；默认使用 Mock provider，因此本地验证不需要外部服务或 API key。

## 本地安装

需要 Python 3.11 或更高版本。开发安装和测试命令如下：

```bash
python -m pip install -e ".[dev]"
make test
```

## Mock 模式

Mock 模式是默认模式，**无需 key**，适合没有凭据的本地开发、演示和自动化测试：

```bash
patchpilot run --task "fix failing tests" --test-cmd "pytest"
```

运行时可用 `--workspace` 指定目标工作区，也可用 `--max-steps` 限制 agent loop 的步数。

## 机制演示

作业 A.6 要求的机制演示见 [MECHANISM_DEMO.md](MECHANISM_DEMO.md)。演示使用 mock / stub LLM 和确定性测试覆盖：危险动作拦截、失败反馈回灌后改变下一步动作、以及 HITL 治理行为。

## OpenAI 模式与凭据

OpenAI 模式会先从系统 keyring 读取 key；只有 keyring 不可用或没有 key 时，才把当前目录 `.env` 中的 `OPENAI_API_KEY` 作为明文开发回退。生产环境不应把 key 写入 `.env`、源代码或日志。

安装 OpenAI 可选依赖后，可显式选择 provider：

```bash
python -m pip install -e ".[dev,openai]"
patchpilot run --provider openai --task "fix failing tests" --test-cmd "pytest"
```

`OpenAILLM` 使用 chat completions 风格接口并要求模型返回 JSON action。provider 输出会经过 action schema 校验；无效 JSON、字段类型错误和未知 action 都会作为无效动作处理。单元测试使用注入的 fake client，不访问网络或真实 API key。

凭据命令不会打印明文 key；`auth status` 只显示是否已配置：

```bash
patchpilot auth status
patchpilot auth set
patchpilot auth clear
```

`auth clear` 只删除 keyring 中的值。如果当前目录 `.env` 或进程环境仍配置 fallback，命令会明确提示 fallback 仍生效，`auth status` 仍显示 `configured`。

## 目录结构

```text
src/patchpilot/
  agent.py        agent loop、context 和停止策略
  llm.py          Mock 与 OpenAI provider
  guardrails.py   路径、命令和风险决策
  tools.py        受控工具分发、审批和 timeout
  feedback.py     pytest 结构化反馈
  memory.py       JSONL 近期记忆
  credentials.py keyring 与开发 fallback
  redaction.py    文本和结构化数据脱敏
  cli.py          argparse 命令入口
tests/            离线单元与回归测试
```

## 安全边界

- **Workspace**：文件读取、patch 和 pytest 目标必须位于 `--workspace` 内；敏感路径和工作区外路径由确定性 guardrail 拒绝。
- **命令**：仅允许受限的 `pytest` 命令和参数；危险 shell 模式、未知参数及非 pytest 命令不会执行。
- **审批**：`pytest --maxfail=1` 属于中风险。非交互模式直接阻止；`--interactive-approval` 会在执行前询问，拒绝后以 `blocked_action` 停止。高风险动作不可通过审批放行。
- **脱敏**：工具输出、结构化事件 action args 和 JSONL memory 在持久化前会清理疑似 key、token、secret、password 和 bearer credential。
- **停止策略**：测试通过、finish、步数耗尽、动作被阻止、工具 timeout 或连续两次无效 action 都会终止 loop，并返回结构化 reason。

## Docker

容器分发已支持以下构建和运行命令：

```bash
docker build -t patchpilot .
docker run --rm -v "$PWD:/workspace" patchpilot run --task "fix failing tests" --test-cmd "pytest"
```

容器内可以使用 Mock 模式而无需 key。使用 OpenAI provider 时，应通过安全的运行时
凭据配置向容器提供 key；不要把真实凭据写入镜像构建上下文或提交到仓库。

## 已知限制

- v1 只支持 Python + pytest 项目。
- v1 不提供 Web UI、向量数据库、多 agent 并发或任意 shell 命令执行。
- Mock provider 用于确定性验证，不代表真实 OpenAI 模型的修复能力。
- OpenAI provider 需要网络、有效凭据和兼容 chat completions JSON 输出的模型；离线测试只验证 client 调用与 schema parsing。
- 工具动作受 pytest allowlist 与护栏策略限制，高风险动作不会执行。
