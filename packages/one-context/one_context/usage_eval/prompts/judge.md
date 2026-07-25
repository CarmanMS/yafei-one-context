你是 skill 现场使用的评审。严格按下面 rubric 给本次调用打分。

# SKILL.md（评估对象的当前版本）

{skill_md}

# Rubric

{rubric_md}

# 本次调用现场

{slot_summary}

# 后续上下文（用于判断 dim_correction / dim_satisfaction）

{surrounding}

---

按 rubric 输出 JSON（**只输出 JSON，不要任何前后文字**）：

```json
{
  "per_dimension": {
    "dim_match":        {"score": 0..1, "reason": "..."},
    "dim_path":         {"score": 0..1, "reason": "..."},
    "dim_completeness": {"score": 0..1, "reason": "..."},
    "dim_correction":   {"score": 0..1, "reason": "..."},
    "dim_satisfaction": {"score": 0..1, "reason": "..."}
  },
  "score": 0..1,
  "verdict": "good" | "needs-work" | "broken",
  "reason": "总评 1-2 句",
  "suggested_patch_md": "如果 SKILL.md 有改进空间，给 markdown 改进建议；无则空字符串"
}
```

> ⚠️ suggested_patch_md 强约束（评审 A-04 最小做）：
> 如果你给改进建议，**每条**建议必须包含**至少一个 unified-diff fenced block**：
>
> ````
> ```diff
> @@ -line,count +line,count @@
> -原文行
> +改后行
> ```
> ````
>
> 没有 diff 块就**不**算合格的 suggested_patch。如果只是定性吐槽（"应该说更清楚"），
> 不要写在 suggested_patch_md，整字段留空字符串。
