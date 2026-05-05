# 测试报告 — 算子空间论文表述规范（范本蒸馏 + Skill）

关联：`spec.md`

## 范围

- 产物与 `onecxt adapt --check` 一致性。
- `.cursor/rules/skill-operator-space-paper-prose.mdc` 是否包含触发说明与 `knowledge/references/operator-space-paper-prose.md` 路径。
- Cursor 内对话行为：仅能人工在新会话中验证（本仓库无法替代 IDE 执行）。

## 用例与结果

| 用例 | 结果 | 备注 |
|------|------|------|
| knowledge 存在且可读 | ✅ | `knowledge/references/operator-space-paper-prose.md` |
| Skill 源文件 | ✅ | `skills/operator-space-paper-prose/SKILL.md` |
| `adapt --all` + `adapt --check --all` | ✅ | 2026-05-05：`adapt --check: all generated files are up-to-date.`（`PYTHONPATH=packages/one-context`，`py -3.11`） |
| Cursor 规则含触发语与 kb 路径 | ✅ | `.cursor/rules/skill-operator-space-paper-prose.mdc` 内「写算子空间论文」、`operator-space-paper-prose.md`、`revisedoperatorspace.tex` |
| SKILL 标题重复 | ✅ 已修 | 去掉正文重复 `# Skill:`，避免 mdc 双标题 |
| `onecxt doctor` | N/A | 未改 `meta/` |

## Cursor 内人工抽检（请你本地执行）

1. **新开 Agent 对话**，输入：
   > 写算子空间论文。先读取 `knowledge/references/operator-space-paper-prose.md`，再用英文写 120 词以内的 introduction，主题是 completely bounded maps 与 \(M_n\)。
2. 检查：英文、少禁用套话、未抄书评句子。
3. **同线程第二条**（不提触发词）：「把上一段压缩到约 80 词。」检查是否仍紧缩、学术语气。

## 已知问题

- 文风无自动化断言；模型未必每次都主动 `Read` kb，可在提示里写明「先读 kb 文件」。

## 说明

勿在此文件存放密钥、token 或未脱敏敏感信息。
