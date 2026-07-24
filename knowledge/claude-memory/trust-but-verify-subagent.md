---
name: trust-but-verify-subagent
description: "subagent 报\"完毕\"后主管必做 grep 静态核查 + 抽样读关键文件 + 真跑 e2e 验证，不直接信任 subagent 自陈"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ce7d53d4-fc00-47e0-a147-ef5f0a7c84f8
---

派 subagent 干活，subagent 报"完毕"+总结后，**主管不直接信任**。必须三层验证：

1. **静态核查**：`git diff --stat` 看改动规模合理性 + `grep -n <关键字符串>` 核查关键改动点是否真落到位
2. **抽样读**：`Read` 关键文件的关键段落（通常 ≤30 行/文件），看实现选择是否符合 brief
3. **真跑 e2e**：能跑就跑（CLI / pytest / 真实 fleet 调用），不要靠"subagent 说 pytest 全过"——subagent 可能跑的是 mock

**Why**：2026-05-30 skill-eval-runner Phase 1 三轮 subagent（architect / PM / dev）每个都报"完毕"，每次主管 trust-but-verify 都发现需澄清细节：
- architect 把字段加错位置（但 grep 一次就发现），PM 用错 ISS 行 grep 字串导致 Edit 失败
- dev 写的"5 种失败模式集成测"实际是 mock unit test（按 brief 等价但术语差异，主管验收时判定算关 ISS-019）
- 最严重情况：若 subagent 真有 bug，直接信任 commit 后下次 e2e 才暴露，回滚成本指数级高

**How to apply**：
- 每个 subagent 交付后最少 3 个并行 Bash/Read 验证（不要全串行，浪费时间）
- 验证项数量按改动规模 scale：单文件改动 1-2 项；多文件 + 新增模块 3-5 项；涉 CLI / e2e 必跑真验证
- 验证完成前**不 commit**，发现问题先回 subagent 修（SendMessage 而非新 spawn，保留 context）
- 这条偏好与 [[cost-no-limit]] 一致：水猿"无限 token"等于"多跑一次 e2e 验证不必省"

**不适用场景**：
- 纯只读/搜索的 subagent（Explore / search-specialist）— 答案对错容易判，不必再跑
- 主管已亲自读完所有相关代码 — 此时 subagent 等于辅助而非主力，验证可降级
