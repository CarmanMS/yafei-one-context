# Features

`features/` 保存跨仓科研或工程事项的规格、设计和评审记录。实现仍位于 `meta/repos.yaml` 登记的独立仓库中。

## 结构

```text
features/
├── README.md
├── INDEX.md
├── _template/
└── <category>/
    └── <feature-id>/
        ├── spec.md
        ├── tech_design.md
        ├── review_record.md
        ├── test_report.md
        └── deliver.md
```

只创建任务实际需要的文件，不为完整目录形状预建空文档。

## 索引不变量

- `INDEX.md` 只列磁盘上真实存在的 feature 目录。
- `id` 与 `<feature-id>` 保持一致并使用 kebab-case。
- `path` 使用相对本仓根目录的路径。
- `primary_repo_id` 必须来自 `meta/repos.yaml`；没有明确实现仓时填 `—`。
- 创建、移动、归档或删除 feature 时，同步修改索引。

建议状态：`draft` → `in_progress` → `review` → `done` → `archived`。

## 最小规格

`spec.md` 至少说明：

- 背景与问题
- 目标和非目标
- 相关 workspace
- 相关 repo id
- 可验证的完成条件
- 风险、隐私与可复现要求

数学科研事项还应区分：

- 已证明结论、猜想与待核实断言
- 文献来源和版本
- 符号、假设与证明依赖
- 计算实验、代码和数据的复现命令

不要把模型生成文本当作证明或文献事实；评审记录应保留核验结果。

## 模板

`_template/spec.md` 是通用起点。其他模板只在对应流程真实存在且仍受维护时使用。模板中的 repo、命令和路径必须在当前仓库可解析。

## 知识库边界

个人 Obsidian vault 不属于 feature 指令层。需要引用或更新笔记时，先读 `skills/obsidian-knowledge/SKILL.md`，并仅经 Local REST API 操作；不得把 vault 全文复制进 feature 或生成配置。
