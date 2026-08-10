# PatchPilot SPEC Process

## 1. Brainstorming Context

The assignment requires using Superpowers to complete an AI4SE final project. The selected track is Project A: Coding Agent Harness. The project must implement its own harness kernel rather than configuring an existing agent framework. It must include deterministic mechanisms for tools, feedback, guardrails, memory, TDD, credentials, distribution, and process documentation.

Superpowers skills used so far:

- `superpowers:using-superpowers`: established that relevant skills must be invoked before task actions.
- `superpowers:brainstorming`: used to clarify project purpose, scope, architecture, safety, credentials, distribution, and testing before implementation.

## 2. Key Brainstorming Decisions

### Iteration 1: Project Type

Question:

Which type of Coding Agent Harness should be built?

Options considered:

- TDD Patch Agent Harness.
- Safe Shell Coding Agent.
- Memory-Aware Coding Agent.

Decision:

The selected direction is TDD Patch Agent Harness.

Reason:

It best matches the assignment's Project A requirements. It naturally exercises the agent loop, tool dispatch, objective test feedback, dangerous action handling, memory, and mock LLM testing.

### Iteration 2: Target Stack

Question:

Should the first supported target be Python plus pytest?

Decision:

Yes.

Reason:

Python and pytest make deterministic tests, fixture projects, CLI behavior, keyring integration, and Docker distribution straightforward. This keeps the project focused on harness mechanisms rather than multi-language support.

### Iteration 3: LLM And Credentials

Question:

Should OpenAI be the optional real provider while mock LLM remains the default and primary verification path?

Decision:

Yes.

Reason:

The assignment requires that core mechanisms remain testable after removing the real LLM. Mock-first design satisfies this directly. Optional OpenAI support demonstrates real-provider readiness without making tests flaky or credential-dependent.

### Iteration 4: Distribution

Question:

Should Docker be the required distribution path, with editable pip install only as a development path?

Decision:

Yes.

Reason:

Docker gives a clear answer to how another user can get and run the project from a fresh machine. Local pip install remains useful for development and tests.

### Iteration 5: Core Modules

Question:

Should v1 be limited to six core modules: loop, LLM provider, tool dispatcher, guardrails, feedback sensors, and memory store?

Decision:

Yes.

Reason:

This gives enough engineering depth without turning the project into a broad, unfocused agent product. It also maps directly to the assignment's required harness mechanisms.

### Iteration 6: Architecture Route

Question:

Which overall approach should be used?

Options considered:

- Deterministic-first CLI Harness.
- Real-LLM-first automatic repair tool.
- Security-governance-first shell harness.

Decision:

Use the deterministic-first CLI Harness.

Reason:

It is the strongest fit for TDD, mock LLM verification, and grading criteria. Real LLM behavior becomes an optional extension rather than the foundation of correctness.

## 3. AI Suggestions Adopted

Adopted:

- Use `patchpilot` as the project name.
- Make mock LLM the default provider.
- Keep OpenAI as optional.
- Use JSONL for memory and event logs.
- Use Docker as the primary distribution form.
- Avoid web UI, vector database, multi-agent concurrency, and broad shell access in v1.

Why adopted:

These suggestions reduce scope risk and keep the project centered on the required harness mechanisms.

## 4. AI Suggestions Deferred Or Rejected

Deferred:

- Full interactive visual UI.
- Multi-language project support.
- Vector database memory.
- Real PR automation.
- Arbitrary shell command execution.

Why deferred:

Each would add complexity without improving the core grading signal. The assignment values mechanism depth, safety, and verification more than broad product surface.

## 5. Current Spec Quality Notes

The current `SPEC.md` intentionally makes these requirements explicit:

- The project implements its own loop and tool dispatch.
- Core mechanisms are deterministic and mock-testable.
- Real OpenAI support is optional.
- Credentials are never hardcoded or logged.
- Docker is the main distribution path.
- v1 is scoped to Python projects using pytest.

## 6. Pending Cold-Start Validation

Before implementation, a different agent type should receive only `SPEC.md` and `PLAN.md` and attempt 1-2 tasks without extra context. The result must be recorded here.

Cold-start prompt draft:

```text
You are a fresh coding agent with no access to prior design conversation. Use only SPEC.md and PLAN.md. Pick one or two early implementation tasks from PLAN.md. Follow TDD: write the failing test first, run it, then implement the minimum code to pass. If any requirement is ambiguous, stop and ask instead of guessing.
```

To record after validation:

- Where the second agent paused.
- What assumptions were missing from SPEC or PLAN.
- Whether any interpretation differed from the intended design.
- What SPEC/PLAN revisions were made.
- Key before/after diff snippets.
