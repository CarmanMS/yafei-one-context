# 交接说明 — MATH1027 B 卷

**一句话**：A 卷含 **54 个 WPS 公式 OLE**；`replace_text` 改不到选项公式。**当前可行路径**：**行内 OMML**（`skills/docx-mcp/lib/`），非 Word COM。

---

## 当前状态（2026-05-30）

| 项 | 状态 |
|---|---|
| 换题内容 | `tech_design.md`（20 题 + 选择答案 B,A,B,A,A） |
| 自动化 pilot | **v4 已生成**（完美集成积分被积表达式消费，消除虚线占位框）：`…-inline-omml-pilot-v4.docx` — 待用户 WPS 目视 |
| 定稿 B-paper / B-answer | **未完成**；旧 `B-paper.docx` 勿当定稿 |
| 用户验收 | pilot **未通过** — 卷面仍是 A 题（OLE 未换） |

**结论与八条核心心得**：见 **`tech_design.md` →「核心心得」**（含 skill 库路径）。

---

## 下一步

1. 打开 **`2025-2026-2-MATH1027-final-B-paper-inline-omml-pilot-v4.docx`**（旧 `v3` / `v2` / `v1` 可忽略）
2. 核对：页眉 **试卷类型 B**；选择 **第 1 题** 为变上限积分题；**第 2 题** 仍应为 A 卷原题（对照用）
3. 通过 → 按 `tech_design.md` 为每题补 paraId 补丁，整卷 paper + answer

**复用命令**：

```powershell
python skills/docx-mcp/lib/rewrite_inline_omml.py `
  --src …/final-A-paper.docx `
  --dst …/final-B-paper.docx `
  --patches my-patches.json
```

---

## 真源与问题清单

| 文件 | 用途 |
|------|------|
| `tech_design.md` | 题目内容 + **结论/心得** |
| `issue_checklist.md` | 问题追踪、文件状态 |
| `…/final-A-paper.docx` | 母版（只读） |

---

## 用户原话（摘要）

- 「不要和 A 一模一样」
- 段后 OMML pilot **题目可以、公式格式不可接受**
- 接受 Word 安装，但 **Word COM OMath 在本模板卡死** → 已弃用

---

## 人工兜底（若自动化仍不满意）

1. 复制 A → B；页眉改「试卷类型 B」
2. 按 `tech_design.md` 在 WPS **公式编辑器** 逐题重录
3. 同步改 answer；通读无 A 卷残留表述
