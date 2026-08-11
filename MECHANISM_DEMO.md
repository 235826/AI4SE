# 机制演示

本项目的机制演示使用 mock / stub LLM 与确定性单元测试完成，不依赖网络、真实 LLM 或 API key。

## 运行全部演示

```bash
pytest \
  tests/test_guardrails.py::test_blocks_dangerous_test_command \
  tests/test_agent.py::test_context_aware_llm_changes_action_after_failed_feedback \
  tests/test_tools.py::test_interactive_approval_callback_rejection_blocks_action \
  -q
```

## 演示 1：治理护栏拦截危险动作

```bash
pytest tests/test_guardrails.py::test_blocks_dangerous_test_command -q
```

该测试直接构造 `Action(type="run_tests", args={"command": "rm -rf ."})`，断言 `GuardrailPolicy` 返回高风险拒绝。拦截发生在确定性代码中，不依赖提示词或真实模型自觉遵守规则。

## 演示 2：失败反馈驱动下一步动作变化

```bash
pytest tests/test_agent.py::test_context_aware_llm_changes_action_after_failed_feedback -q
```

该测试使用一个 stub LLM：第一步运行失败测试，第二步检查 agent loop 回灌的 `feedback` 与 `last_result`，确认收到失败信号后再返回 `finish`。这演示了 pytest 反馈被解析、写入上下文，并影响下一轮动作。

## 演示 3：重点维度的 HITL 治理行为

```bash
pytest tests/test_tools.py::test_interactive_approval_callback_rejection_blocks_action -q
```

该测试把 `pytest --maxfail=1` 作为中风险动作，并注入拒绝审批的 callback。断言工具不会执行命令，返回 `blocked=True`。这对应 PatchPilot 的重点维度：治理护栏与人工审批边界。
