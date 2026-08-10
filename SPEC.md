# PatchPilot SPEC

## 1. Problem Statement

PatchPilot is a small, test-driven coding agent harness for Python projects. It helps a developer run a controlled repair loop over a local workspace: inspect files, apply patches, run `pytest`, read objective feedback, and stop when the tests pass or a safety/iteration boundary is reached.

The target user is a student or engineer who wants to understand how a coding agent harness works below the LLM layer. The project is worth building because it exposes the engineering mechanisms that make an agent reliable: tool dispatch, deterministic feedback, guardrails, memory, credential handling, and distribution. The goal is not to build a production IDE agent; the goal is to implement a minimal but real harness kernel whose core behavior remains testable with a mock LLM.

## 2. User Stories

1. As a developer, I want to run `patchpilot run --task "fix failing tests" --test-cmd "pytest"` in a Python project so that the harness can attempt a bounded repair loop.
2. As a developer, I want PatchPilot to run with a mock LLM by default so that I can test and demonstrate the harness without paid API access.
3. As a developer, I want optional OpenAI support with secure key storage so that I can try real model-driven actions without hardcoding credentials.
4. As a reviewer, I want every tool action and result to be recorded in structured logs so that I can audit what the agent did.
5. As a safety-conscious user, I want dangerous commands and sensitive file access to be blocked or require approval so that the agent cannot damage the project or expose secrets.
6. As a maintainer, I want deterministic unit tests for the loop, tools, feedback, guardrails, memory, credentials, and CLI so that the harness mechanisms can be verified without a real LLM.

## 3. Functional Specification

### 3.1 CLI

Inputs:

- `patchpilot run --task <text> --test-cmd <command>`
- `--provider mock|openai`
- `--max-steps <n>`
- `--workspace <path>`
- `--interactive-approval`
- `patchpilot auth status|set|clear`

Behavior:

- Validates workspace and arguments.
- Uses `mock` provider by default.
- Uses OpenAI only when explicitly requested.
- Exits with code `0` when tests pass or the agent finishes successfully.
- Exits with non-zero code for failed repair, blocked action, invalid configuration, or exhausted steps.

Boundary cases:

- Missing task: reject with usage error.
- Test command outside allowlist: reject before the loop starts.
- Workspace path outside current accessible directory: reject.

### 3.2 Agent Loop

Inputs:

- Task text.
- Workspace metadata.
- Memory snippets.
- Previous tool results.
- LLM provider.

Behavior:

1. Build context.
2. Call `LLMProvider.next_action(context)`.
3. Parse a structured action.
4. Run guardrail checks.
5. Dispatch the action to a tool.
6. Convert tool output into structured feedback.
7. Append feedback to the next context.
8. Stop when a terminal condition is reached.

Outputs:

- Final run status.
- Structured event log.
- Updated memory entries.

Stop conditions:

- `finish` action.
- `pytest` passes.
- `--max-steps` reached.
- Two consecutive invalid actions.
- Dangerous action rejected.
- Tool timeout.

### 3.3 LLM Provider

Providers:

- `MockLLM`: deterministic scripted actions for tests and demos.
- `OpenAILLM`: optional real provider, using a single chat completion style call.

Input:

- Structured context object.

Output:

- One structured action:
  - `list_files`
  - `read_file`
  - `apply_patch`
  - `run_tests`
  - `remember`
  - `finish`

Errors:

- Invalid provider configuration produces a configuration error before the loop.
- Invalid LLM output is counted as an invalid action.

### 3.4 Tool Dispatcher

Tools:

- `list_files`: list non-sensitive files under the workspace.
- `read_file`: read a workspace file unless guardrails block it.
- `apply_patch`: apply a unified patch to allowed files.
- `run_tests`: run the allowed test command.
- `remember`: write a memory event.
- `finish`: produce terminal status.

All tool inputs and outputs are structured. Logs must redact secret-like values.

### 3.5 Guardrails

Guardrails are deterministic code, not prompt instructions.

Blocked actions:

- Read or write outside workspace.
- Read `.env`, `.ssh/`, private keys, `*.pem`, `*token*`, or `*secret*`.
- Run commands outside the allowlist.
- Run dangerous shell patterns such as `rm -rf`, `curl | sh`, release commands, `git push`, or package publish commands.
- Patch forbidden paths.

Default behavior:

- Non-interactive mode rejects dangerous actions.
- Interactive approval mode pauses for human approval for configured medium-risk actions.
- High-risk actions are always rejected, even in interactive mode.

### 3.6 Feedback Sensors

The pytest sensor parses:

- Exit code.
- Passed, failed, and error counts.
- Failed test names.
- Short traceback summary.
- Whether the test command satisfies the pass criterion.

This feedback is returned to the agent loop as a structured object rather than as raw terminal text only.

### 3.7 Memory Store

Storage:

- JSONL in `.patchpilot/memory.jsonl`.

Entries:

- Project rules.
- User decisions.
- Attempted actions.
- Recent failure summaries.
- Run summaries.

The context builder injects only relevant recent memory, not the full history.

### 3.8 Credentials

Commands:

- `patchpilot auth status`
- `patchpilot auth set`
- `patchpilot auth clear`

Behavior:

- `status` never prints the plaintext key.
- `set` uses hidden input.
- `clear` removes the stored key.

Credential sources:

1. OS keychain through Python `keyring`.
2. `.env` for development fallback only.
3. Hidden interactive entry saved to keyring.

## 4. Non-Functional Requirements

### 4.1 Performance

- A default run must finish within the configured step limit.
- Tool timeouts prevent unbounded test execution.
- Context size is controlled by memory summarization and recent-result selection.

### 4.2 Security

Threat model:

- The LLM may request unsafe file access or shell commands.
- The workspace may contain secrets.
- Logs may accidentally capture sensitive values.
- API keys may be leaked through source code, command history, logs, or plaintext config.

Countermeasures:

- Default mock provider avoids credentials.
- OpenAI key is stored in the OS keychain where possible.
- `.env` is allowed only as a development fallback and is documented as plaintext risk.
- Hidden input is used for key entry.
- Secret values are redacted in logs.
- Sensitive paths are blocked by deterministic guardrail code.
- Test command execution is allowlisted.

### 4.3 Usability

- CLI errors should explain the failed precondition and the next corrective action.
- README must include local and Docker workflows.
- Mock mode must work without external services.

### 4.4 Observability

- Each run writes structured events for action requested, guardrail result, tool result, feedback summary, and stop reason.
- Logs do not include plaintext API keys.

## 5. System Architecture

Components:

- `cli`: argument parsing, auth commands, run command.
- `agent`: main loop, context builder, stop policy.
- `llm`: provider interface, mock provider, OpenAI provider.
- `tools`: filesystem tools, patch application, test runner.
- `guardrails`: path policy, command policy, approval policy.
- `feedback`: pytest parser and feedback model.
- `memory`: JSONL store and retrieval.
- `credentials`: keyring and `.env` credential loading.
- `logging`: structured event logging and redaction.

Data flow:

1. CLI constructs a run request.
2. Context builder combines task, workspace summary, memory, and previous feedback.
3. LLM provider returns a structured action.
4. Guardrails approve, reject, or request approval.
5. Tool dispatcher executes approved actions.
6. Feedback sensors convert results into structured feedback.
7. Agent loop records events and either continues or stops.

External dependencies:

- Python 3.11+.
- `pytest` for tests.
- `keyring` for OS credential storage.
- `python-dotenv` for development `.env` fallback.
- OpenAI API as an optional provider.
- Docker for container distribution.

## 6. Data Model

### Action

- `type`: action name.
- `args`: action-specific parameters.
- `reason`: brief explanation from provider.

### ToolResult

- `action_type`
- `ok`
- `exit_code`
- `stdout_summary`
- `stderr_summary`
- `changed_files`
- `error`

### Feedback

- `kind`: `pytest`, `guardrail`, `tool`, or `loop`.
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

## 7. Credential And Distribution Design

Credential design:

- Mock mode requires no key.
- OpenAI mode requires a key obtained from keyring or `.env`.
- First-run setup uses `patchpilot auth set` with hidden input.
- Status and logs never reveal plaintext keys.
- Users can update or clear credentials through auth commands.

Distribution:

- Primary: Docker image.
- Development: editable Python install.

Docker commands:

```bash
docker build -t patchpilot .
docker run --rm -it -v "$PWD:/workspace" patchpilot run --task "fix failing tests" --test-cmd "pytest"
```

Known limits:

- Docker keyring integration is platform-dependent, so container runs should prefer mock mode or documented environment injection for non-secret demos.
- Real OpenAI use inside Docker requires explicit secure configuration by the user.
- v1 targets Python projects using pytest.

## 8. Technology Choices

- Language: Python, because the project targets pytest repair loops and has straightforward CLI, testing, keyring, and Docker support.
- CLI framework: standard library `argparse`, to keep the harness small and avoid extra runtime dependency decisions during cold-start implementation.
- Test framework: pytest.
- Credential library: keyring.
- LLM provider: mock by default, OpenAI API optional.
- Storage: JSONL for memory and run events because it is simple, inspectable, and easy to test.
- Distribution: Docker as the required path, editable pip install for development.
- UI: no frontend, so Open Design does not apply.

## 9. Acceptance Criteria

1. `make test` or equivalent runs all tests in one command.
2. Mock LLM tests verify the agent loop without network access.
3. Guardrail tests prove dangerous paths and commands are blocked.
4. Pytest feedback parser tests cover pass, fail, error, and timeout cases.
5. Credential tests use mocked keyring and never print plaintext keys.
6. CLI tests cover `run` and `auth` commands.
7. Docker image builds successfully in CI.
8. README explains install, run, Docker, credentials, and known limits.
9. `SPEC.md`, `PLAN.md`, `SPEC_PROCESS.md`, `AGENT_LOG.md`, and `REFLECTION.md` exist.
10. No real secrets are present in source, tests, logs, or config.

## 10. Domain And Mechanism Design

PatchPilot implements the four required harness mechanism classes:

### 10.1 Actions And Tools

Actions are structured objects produced by the LLM provider and executed only through the dispatcher. The agent cannot run arbitrary code directly.

### 10.2 Objective Feedback Signals

The pytest sensor is deterministic code. It parses command result data and returns pass/fail status, failing tests, and summaries. This feedback drives the next loop step.

### 10.3 Dangerous Actions

The guardrail layer detects dangerous file paths, shell commands, and patch targets before execution. The block decision is testable with mock actions and does not depend on LLM compliance.

### 10.4 Memory

Memory is explicit local data. The context builder selects bounded memory entries for the next LLM call. Tests can verify read, write, filtering, and context injection without a real LLM.

## 11. Risks And Mitigations

Risks:

- Real LLM output may not follow the expected action schema.
- Patch application can be brittle if diffs do not match the workspace.
- Docker credential storage differs by platform.
- Overly broad shell support would weaken the safety story.

Mitigations:

- Treat invalid provider output as an invalid action with a stop threshold.
- Keep v1 tools narrow and deterministic.
- Make Docker mock mode the default demonstration.
- Document OpenAI-in-Docker limitations clearly.

Resolved implementation choices:

- CLI uses `argparse`.
- v1 includes an `--interactive-approval` flag for medium-risk actions.
- High-risk actions remain non-overridable.
