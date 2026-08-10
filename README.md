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

## OpenAI 模式与凭据

OpenAI 模式会先从系统 keyring 读取 key；只有 keyring 不可用或没有 key 时，才把当前目录 `.env` 中的 `OPENAI_API_KEY` 作为明文开发回退。生产环境不应把 key 写入 `.env`、源代码或日志。

凭据命令不会打印明文 key；`auth status` 只显示是否已配置：

```bash
patchpilot auth status
patchpilot auth set
patchpilot auth clear
```

设置 key 后，可以显式选择 OpenAI provider：

```bash
patchpilot run --provider openai --task "fix failing tests" --test-cmd "pytest"
```

## Docker

使用 Docker 构建并在挂载的项目工作区运行：

```bash
docker build -t patchpilot .
docker run --rm -it -v "$PWD:/workspace" patchpilot run --task "fix failing tests" --test-cmd "pytest"
```

容器内同样可以使用 Mock 模式而无需 key。使用 OpenAI provider 时，应通过安全的运行时凭据配置向容器提供 key，不要把真实凭据写入镜像或提交到仓库。

## 已知限制

- v1 只支持 Python + pytest 项目。
- v1 不提供 Web UI、向量数据库、多 agent 并发或任意 shell 命令执行。
- Mock provider 用于确定性验证，不代表真实 OpenAI 模型的修复能力。
- OpenAI provider 需要用户自行配置有效凭据和网络访问。
- 工具动作受 pytest allowlist 与护栏策略限制，高风险动作不会执行。
