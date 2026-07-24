---
name: cost-no-limit
description: 水猿明确不要刻意为他省 token；选模型/工具/并行规模时按效果选不按成本选
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ce7d53d4-fc00-47e0-a147-ef5f0a7c84f8
---

水猿明确：**「我有无限 token，不要刻意给我省」**。

**Why**：2026-05-30 skill-eval-runner Phase 1 推进时，水猿主动说这句话。前文我倾向小心控费（推荐 haiku judge 而非 opus、问要不要跑 e2e 等），他纠偏。

**How to apply**：
- spawn 多个 subagent 并行、跑 e2e、用 opus 而非 haiku、批量 fleet 调用 时**不必征询成本**
- 不要在回答里反复强调"消耗 ~$X"作为决策影响因素
- 只在明显浪费（重复跑相同任务无新信号、循环 spawn 同一逻辑）时才主动节制
- 但**不等于乱花**：水猿说"也不意味着浪费"——按效果定，能用 sonnet 解决就不必上 opus 4 次
- 用法变化触发 revisit：若水猿换环境 / 换团队 / 明确撤回该偏好，更新此 memory

相关：[[trust-but-verify-subagent]]（trust-but-verify 多跑一次 e2e 也别省）
