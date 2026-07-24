---
name: subagent-task-tool-registry
description: Task tool 注册表不含项目级 .claude/agents/ 角色；多 subagent 协作要用 general-purpose 在 prompt 里扮演
metadata: 
  node_type: memory
  type: reference
  originSessionId: ce7d53d4-fc00-47e0-a147-ef5f0a7c84f8
---

**陷阱**：one-context 项目 `.claude/agents/` 下有 architect / pm / dev / qa / reviewer / knowledge-keeper / sre / ai-infra 自定义角色。**但 Task tool 的 `subagent_type` 参数走的是另一套注册表**，里面只有：

```
ai-engineer, backend-architect, claude, claude-code-guide, code-reviewer,
code-simplifier:code-simplifier, debugger, Explore, frontend-developer,
general-purpose, get-current-datetime, init-architect, javascript-pro,
mcp-expert, Plan, planner, prompt-engineer, search-specialist,
statusline-setup, superpowers:code-reviewer, ui-ux-designer
```

直接 `subagent_type: "architect"` 或 `"pm"` 会报 `Agent type 'X' not found`。

**正确用法**：想让 subagent 扮演项目级角色（如 PM / architect / dev / qa）：

```
Agent({
  subagent_type: "general-purpose",
  prompt: "你扮演 one-context 的 PM agent（角色定义见 .claude/agents/pm.md）。..."
})
```

在 prompt 里指明角色 + 引用 `.claude/agents/<role>.md` 让 subagent 自己读定义。

**首次撞坑**：2026-05-30 skill-eval-runner Phase 1，主管派 architect + PM 两个 subagent，直接传 `subagent_type: "architect"` / `"pm"` 双双 fail；改 general-purpose 后通过。

**revisit 触发**：one-context 接 MCP 注册项目级 agent / Claude Code 升级把 .claude/agents/ 接入 Task 注册表 → 此 memory 作废，可直接 spawn。
