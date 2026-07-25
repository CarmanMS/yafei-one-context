# Skill 使用后异步自评估闭环 — 设计文档

| 字段 | 值 |
|---|---|
| feature-id | `skill-self-evolution-loop` |
| spec | [`features/core/skill-self-evolution-loop/spec.md`](../../features/core/skill-self-evolution-loop/spec.md) |
| 类型 | core / 仓内 skill 治理基础设施 |
| 状态 | draft（待 writing-plans 出实施计划） |
| owner | 水猿 |
| 创建日期 | 2026-06-03 |

## 1. 背景与边界

### 1.1 问题

仓内 30+ 个 skill 修改后**没有真实使用反馈的沉淀通路**。`skill-eval-runner` 解决了「修改后跑预定义 scenario 回归」，但有两个空白：

- **真实使用现场没沉淀**：cc 在真实会话里调用某 skill 后，调对没、绕远没、SKILL.md 漏写没——这些信号丢失在 `~/.claude/projects/<hash>/<sid>.jsonl` 里
- **手动触发回归不能反映"用得对吗"**：scenario 是设计者预期的成功路径，与真实使用现场不重叠

### 1.2 解决思路（与水猿对齐结果）

| 维度 | 决策 |
|---|---|
| 触发模式 | SessionEnd hook（会话结束、上下文完整、版本明确无漂移） |
| 评估对象 | 现场单次调用（input / SKILL.md / tool-call 链 / output / 后续上下文） + 出 SKILL.md 改进建议 |
| 范围 | 仅仓内 `skills/<name>/`（30+） |
| rubric 形态 | AI 看 SKILL.md 自动生成、缓存到 RUBRIC.md、SKILL.md 哈希变则重生 |
| 改进建议形态 | 仅 markdown 报告，不自动合入 |
| 复用 skill-eval-runner | 不复用（不跑 sandbox / scenario，仅可能共享 LLM judge 工具函数） |

## 2. 架构总览

```
┌────────────── one-context 仓 ──────────────┐
│ .claude/settings.json                       │
│   hooks.SessionEnd:                         │
│     onecxt usage-eval daemon-spawn          │ ← hook，唯一入口
│       --session-id $CLAUDE_SESSION_ID       │
└────────────────────┬────────────────────────┘
                     │ double-fork（不阻塞 cc 退出）
                     ▼
┌──────────── usage-eval daemon ──────────────┐
│ 1. 解析 ~/.claude/projects/<hash>/<sid>.jsonl │
│    抽 Skill tool_use 片段                     │
│ 2. 按 skill 分组 → 跳过非仓内 skill            │
│ 3. 对每个 (skill × slot)：                     │
│    a. 加载/生成 RUBRIC.md（哈希校验）          │
│    b. spawn cheap judge 打分                   │
│    c. 写 __usage_eval/<runId>/...              │
│    d. atomic append __usage_eval/INDEX.md       │
└────────────────────┬────────────────────────┘
                     ▼
┌─────────── onecxt usage-eval ───────────────┐
│  daemon-spawn  ← hook 调用                  │
│  trend         ← 横向 dashboard             │
│  inspect       ← 单 skill / 单 runId 查看   │
└─────────────────────────────────────────────┘
```

## 3. 组件细节

### 3.1 hook 入口（`.claude/settings.json`）

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "onecxt usage-eval daemon-spawn --session-id \"$CLAUDE_SESSION_ID\" --cwd \"$CLAUDE_PROJECT_DIR\""
          }
        ]
      }
    ]
  }
}
```

**注意**（开放问题 1）：SessionEnd 是否真存在需先实证；不存在则降级到 `Stop` hook + 静默检测。

### 3.2 daemon 模块（`packages/one-context/one_context/usage_eval/`）

| 文件 | 职责 |
|---|---|
| `cli.py` | onecxt 子命令入口（daemon-spawn / trend / inspect） |
| `daemon.py` | double-fork、PID 文件、信号处理、超时熔断 |
| `session_parser.py` | jsonl 路径反推（cwd → hash） + tool_use 抽取 |
| `rubric.py` | 加载 / 生成 / 哈希校验 RUBRIC.md |
| `judge.py` | spawn `claude -p` cheap judge，封装重试与降级 |
| `report.py` | 渲染 report.md + suggested_patch.md + INDEX.md atomic append |
| `trend.py` | 跨 skill 扫 INDEX.md → HTML dashboard |
| `tests/` | 单测 + 集成测 + e2e |

### 3.3 数据流细化

```
SessionEnd
  ↓ env: $CLAUDE_SESSION_ID, $CLAUDE_PROJECT_DIR
onecxt usage-eval daemon-spawn --session-id <sid> --cwd <repo_root>
  ├─ 父进程：double-fork → 立即返回（< 100ms）
  └─ 子进程（daemon）：
       ↓ jsonl_path = ~/.claude/projects/<sha256(cwd)>/<sid>.jsonl
       ↓ events = parse_jsonl(jsonl_path)
       ↓ slots = [(skill_name, slot_idx, slot) for slot in events if slot.tool_name == "Skill"]
       ↓ for (skill_name, slot_idx, slot) in slots:
       ↓     skill_dir = repos_root / "skills" / skill_name
       ↓     if not skill_dir.exists(): continue  ← 仓内 only
       ↓     skill_md = read(skill_dir / "SKILL.md")
       ↓     skill_sha = sha256(skill_md)
       ↓
       ↓     rubric = load_or_generate_rubric(skill_dir, skill_sha)
       ↓                └── miss/sha-mismatch → AI 生成（opus，一次性投入）
       ↓
       ↓     ctx = surrounding_turns(events, slot_idx, n=3)
       ↓     judge_out = judge_skill_call(skill_md, rubric, slot, ctx)
       ↓                 ├── score: 0..1
       ↓                 ├── per_dimension: dict[5 维 → score + reason]
       ↓                 ├── reason: 总评
       ↓                 └── suggested_patch_md: markdown 形式的 SKILL.md 修改建议
       ↓
       ↓     runId = f"{int(time.time())}-{sid[:8]}-{slot_idx:03d}"
       ↓     out_dir = skill_dir / "__usage_eval" / runId
       ↓     write out_dir / "report.md" (含 frontmatter: skill, score, runId, sid, slot_idx, judge_model, ts)
       ↓     write out_dir / "suggested_patch.md"
       ↓     write out_dir / "slot.json"  (debug 用，原始 tool_use 片段)
       ↓     atomic_append(skill_dir / "__usage_eval" / "INDEX.md", index_line)
       ↓
       ↓ (并发限 4，简单线程池；失败的 slot 单独记 log，不阻断其他 slot)
```

### 3.4 文件结构

```
skills/<name>/
  SKILL.md                          # 不动（被评估对象）
  __usage_eval/
    RUBRIC.md                       # 入 git；frontmatter 含 skill_md_sha256
    INDEX.md                        # 入 git；append-only，单行格式
    <runId>/                        # .gitignore（运行时产物）
      report.md
      suggested_patch.md
      slot.json
```

`runId` 格式：`<unix_ts>-<sid_short>-<slot_idx>`，例：`1748940000-3a9f8b21-007`

`.gitignore` 增量规则：

```gitignore
# skill-self-evolution-loop 运行时产物
skills/*/__usage_eval/[0-9]*/
!skills/*/__usage_eval/RUBRIC.md
!skills/*/__usage_eval/INDEX.md
```

### 3.5 RUBRIC.md 模板

```markdown
---
skill: cover-prompt
skill_md_sha256: 7a3c9d...
generated_at: 2026-06-03T14:22:11+08:00
generator_model: claude-opus-4-7
schema_version: 1
---

# Rubric: cover-prompt

## 5 维度

### 1. 调对了吗（dim_match, weight=0.25）

如果用户在问 X 类问题但选了本 skill 则 -0.5...
（AI 看 SKILL.md 后填具体打分线）

### 2. 路径合理（dim_path, weight=0.20）

调用链有无明显绕远...

### 3. 指令充分（dim_completeness, weight=0.20）

SKILL.md 是否给了正确指引、有无漏写关键步骤...

### 4. 后续是否纠错（dim_correction, weight=0.15）

主 agent 之后是否回头补救（含纠错次数 / 关键性）...

### 5. 最终满足度（dim_satisfaction, weight=0.20）

用户后续轮次有无抱怨 / 不满...

## 阈值

- ≥ 0.8: 表现良好
- 0.5..0.8: 有改进空间，看 suggested_patch
- < 0.5: 显著问题，建议优先迭代

## 输出格式约束

judge 必须输出 JSON：

```json
{
  "per_dimension": {
    "dim_match": {"score": 0.9, "reason": "..."},
    ...
  },
  "score": 0.82,
  "verdict": "good",
  "reason": "...",
  "suggested_patch_md": "## 建议修改 SKILL.md\n\n在 ## 触发条件 段后追加：\n..."
}
```
```

### 3.6 report.md 模板

```markdown
---
skill: cover-prompt
runId: 1748940000-3a9f8b21-007
sid: 3a9f8b21-...
slot_idx: 7
score: 0.82
verdict: good
judge_model: claude-sonnet-4-6
rubric_sha256: 7a3c9d...
ts: 2026-06-03T14:25:33+08:00
---

# 评估：cover-prompt @ runId

## 总评（score: 0.82, verdict: good）

调对了 skill，但 tool-call 链中第 3 步重复读了同一文件（绕远 0.1）。
SKILL.md「图片输出位置」段写得不够明确（指令充分 -0.15）。

## 各维度分

| 维度 | 分 | 理由 |
|---|---|---|
| 调对了吗 | 0.95 | 用户问题与 skill 职责完全匹配 |
| 路径合理 | 0.75 | 第 3 步重复 Read 同文件 |
| 指令充分 | 0.70 | 「图片输出位置」描述模糊 |
| 后续是否纠错 | 0.90 | 仅 1 次微调，无大改 |
| 最终满足度 | 0.85 | 用户在后续轮次未抱怨 |

## 现场片段（slot 摘要）

input: ...
tool-call 链: Read(...) → Read(...) → Glob(...) → Write(...)
output: ...

后续 3 轮上下文摘要: ...

## 改进建议

详见同目录 [suggested_patch.md](./suggested_patch.md)

[原始数据](./slot.json)
```

### 3.7 suggested_patch.md 模板

```markdown
# SKILL.md 改进建议（cover-prompt @ runId）

## 建议修改 1：明确「图片输出位置」

**位置**：SKILL.md 第 3 节「输出规范」
**理由**：本次评估 dim_completeness 0.70，主 agent 在 Read 步骤来回找输出位置。
**unified-diff 草稿**：

```diff
@@ -45,7 +45,9 @@
 ## 输出规范

-图片应输出到合适位置。
+图片输出到 `production/cover/<scene>.png`。
+如果 scene 编号未指定，按 `production/timing/scene-boundaries.md` 推断。
+输出前先 ls 该目录，避免覆盖已有产物。
```

**dry-apply 校验**：✅ git apply --check 通过

---

（多条建议依次列出）
```

### 3.8 INDEX.md 行格式（atomic append）

```
# skills/cover-prompt/__usage_eval/INDEX.md
1748940000-3a9f8b21-007 | 0.82 | good        | sid=3a9f8b21 | tools=Read,Glob,Write | suggestions=2
1748940120-3a9f8b21-008 | 0.55 | needs-work  | sid=3a9f8b21 | tools=Read           | suggestions=4
```

## 4. 错误处理

| 错误源 | 处理 |
|---|---|
| daemon 内部异常 | catch → `~/.claude/logs/usage-eval/<sid>.log` + 退出码非零；不传播 |
| jsonl 路径反推失败 | 落日志「session not found」+ 优雅退出 |
| jsonl 解析失败 | 跳过 corrupted event + 落日志，继续处理后续 |
| RUBRIC 生成失败 | 该 skill 跳过本轮，不阻断其他 skill |
| LLM judge 超时 / 失败 | 指数退避（1s / 4s / 16s）最多 3 次；仍失败 → 写 `report.md` 标记 `status: error` 并 INDEX 记录 |
| 写文件冲突 | runId 含时间戳 + slot_idx 天然唯一；INDEX.md 用 flock 保证原子追加 |
| 单次评估超 5min | daemon 强制 kill 该 slot，记 timeout |

## 5. 测试策略

| 层 | 内容 |
|---|---|
| unit | session_parser（解析 jsonl fixture）/ rubric 哈希校验 / report 渲染 / atomic append |
| integration | 构造 fake jsonl + mock LLM judge → 验证 RUBRIC 生成、文件落地、INDEX 增量 |
| e2e | 真 cc 会话调一次 cover-prompt → SessionEnd → 等待 daemon → 验产出 + RUBRIC.md 一致 + INDEX.md 增量正确 |
| 不引入 | 新测试框架；沿用 packages/one-context/tests pytest |

## 6. 验收标准

见 [`spec.md` § 验收标准](../../features/core/skill-self-evolution-loop/spec.md#验收标准)，按 Phase 1 / 2 / 3 划分。

## 7. 里程碑（粗）

| 阶段 | 内容 | 退出条件 |
|---|---|---|
| M0 | 实证 hook + jsonl 路径反推 | 在真实 cc 上确认 SessionEnd 是否触发、jsonl 路径算法 |
| M1 | session_parser + rubric 模块 + 单测 | 能从 fixture jsonl 抽 slot；能哈希校验 RUBRIC |
| M2 | judge 模块 + report 模块 + integration | mock LLM 跑通 fake jsonl → 完整产物落地 |
| M3 | daemon + cli daemon-spawn + e2e | 真跑 cover-prompt 一个 skill |
| M4 | trend 子命令 + dashboard | 5 skill / 30 record 后 dashboard 跑通 |
| M5 | 健壮性：超时熔断 / 重试 / 失效重生 | 主动模拟故障验证不阻塞主流程 |

## 8. 开放问题（同 spec）

1. SessionEnd hook 名实证
2. jsonl 路径反推算法（cwd → hash）
3. RUBRIC.md 是否进 git track（倾向：进）
4. trend dashboard 历史回放（MVP 不做）
5. judge 模型选择（cheap = sonnet-4-6 / rubric 生成 = opus）
6. 多 slot 并发上限（倾向：4）
7. suggested_patch dry-apply 校验（倾向：做）

## 9. 与既有 feature 的边界

| 既有 feature | 关系 |
|---|---|
| `skill-eval-runner` | 平行；不复用 sandbox / scenario / __reports；可能共享 LLM judge 调用工具函数 |
| `claudecode-skill-auto-evolution` | 上层调研；本需求是其下一种具体落地形态（自学 rubric + 仅人工 gate 路线） |
| `skill-self-evolution-survey` | 调研基础（SkillsBench / EvoSkill / Skills-Coach 等开源项目对照） |
| `google-skillos-self-evolving-agent-mid-video` | 灵感来源（中视频解说 SkillOS 论文） |

## 10. 下一步

本设计文档完成后，调用 `superpowers:writing-plans` skill 产出阶段化实施计划（implementation_plan.md）。
