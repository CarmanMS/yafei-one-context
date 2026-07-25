你是 onecxt eval 录制器的 **finalize 起草员**。任务：基于一次刚录完的 cc skill 跑动产物，
起草一份「判定维度候选清单」（markdown），供用户在 `commit_finalize` 阶段挑选 / 修改 /
补充。

# 输入

## skill / scenario

- **skill**: `{{ skill_name }}`
- **scenario**: `{{ scenario_name }}`

## 本次录制的外部 tool 调用谱（rounds_summary）

```
{{ rounds_summary }}
```

## 本次录制的产物文件树（baseline/artifacts/）

```
{{ artifacts_tree }}
```

## cc 最后一段输出（final_text 前 500 字 · 可能为空）

```
{{ final_text_head }}
```

## 候选 query 草稿（供你判断"用户要的是什么"）

```
{{ query_draft }}
```

## 虚假通过反例库（**硬约束 · 必须逐条覆盖**）

{{ negative_case_library }}

---

# 输出要求（严格 markdown · 直接复用 §3.4 schema）

请按以下结构输出，不要任何前后缀解释、不要代码块包裹整体输出。

```markdown
# Judge Prompt Draft — {{ skill_name }} / {{ scenario_name }}

## 这次录制为什么算成功

<2-3 段自然语言。结合 final_text + artifacts_tree 描述「这次跑通了什么 / 用户能拿到什么」。
不要照抄 SKILL.md，要总结**这次跑动**的具体产物。>

## 候选 query

<给一个候选 query 字符串（用户在 `commit_finalize` 阶段会确认或修改）。
推导依据：观察 rounds_summary 里第一个外部 tool 的 input 关键词 + 产物文件名。
若推导不出，直接写 `TBD: 请用户在 commit_finalize 时给出`。>

## 判定维度（LLM 给 0-1 分）

### D1: <维度名>
**判定标准**：<具体可观察标准，引用 baseline/artifacts/ 中具体文件名 / 字段>
**权重**：<0.0-1.0>
**covers**: [<F-NN 列表，若不针对反例则空>]

### D2: ...
...

## 虚假通过反例（出现任一即 FAIL）

### F1: <反例名 · 复刻自反例库，或基于本次产物补充新反例>
**特征**：<具体可观察特征>
**反例数据来源**：<例：baseline/artifacts/... 不应出现 X 字符串>
**covers**: [<F-NN 反例库 ID 列表>]

### F2: ...
...

## 未覆盖反例

<如果反例库中有未在 D / F 章节里覆盖的 F-NN，全部列在这里，让用户决定是否补。
形如：「F-04 source 字段错标 — 本次录制 mock_rounds 全部来自同一个源，复现意义低，建议跳过」
如果全部覆盖，写 `（全覆盖）`。>

## 总分阈值

`pass_threshold: 0.7`（加权和。建议值，用户可在 commit_finalize 时调整。）
```

# 硬约束

1. **必须输出标准的 D1/D2/.../F1/F2/... 编号章节**（D / F 各至少 2 条）。
2. **反例库每条 F-NN 必须在候选清单里至少配 1 个 D 维度或 1 个 F 反例**，并在
   对应条目的 `covers` 里标注 F-NN。未覆盖的列入「未覆盖反例」章节。
3. **D 的判定标准必须引用本次 baseline 中具体文件路径或字段**，不要写空泛断语。
4. **不要输出 JSON / 代码块包裹整体响应**，直接输出 markdown 正文。
