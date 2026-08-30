# yafei-one-context

面向数学科研的 one-context 个人分支：把论文工作、数学可视化项目、知识库和 AI 工具放在同一套可追踪的上下文中，同时保留各子仓库独立的 Git 历史。

本仓库是控制面，不承载业务源码：

- `meta/`：仓库、工作区、Agent 和行为配置。
- `packages/one-context/`：`onecxt` Python CLI。
- `features/`：跨仓科研或工程事项的规格与评审记录。
- `skills/`：可执行工作流。
- `knowledge/`：个人 Obsidian vault，以 Git submodule 固定版本。
- `repos/`：由 `onecxt sync` 初始化的独立仓库，本仓不跟踪其内容。

当前默认工作区是 `math-research`，关联 `paperwork` 与 `FunctionCanvas`。

## 快速开始

```powershell
git clone --recurse-submodules git@github.com:CarmanMS/yafei-one-context.git
cd yafei-one-context

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e "./packages/one-context[dev]"

python -m one_context doctor
python -m one_context sync paperwork FunctionCanvas
python -m one_context workspace list
```

macOS/Linux 激活虚拟环境时使用 `source .venv/bin/activate`。

导出数学科研上下文：

```powershell
python -m one_context context export math-research --format markdown
```

按需在本机生成某个 AI 工具的配置：

```powershell
python -m one_context adapt math-research --dry-run
python -m one_context adapt math-research
```

适配器输出是本地生成物，不提交到 Git。权威来源始终是 `AGENTS.md`、`meta/`、`docs/`、`features/` 与 `skills/`。

## 知识库边界

`knowledge/` 是个人 Obsidian vault，不是 Agent 规范目录。笔记只能经 Obsidian Local REST API 访问：

- 入口：`https://127.0.0.1:27124`
- 工作流：`skills/obsidian-knowledge/SKILL.md`
- 本地密钥：`skills/obsidian-knowledge/api-key.txt`，已忽略，禁止提交

禁止通过文件系统直接读取、搜索或修改 `knowledge/**`。这样可避免绕过 Obsidian 索引，也避免把私人笔记内联到生成配置中。

## 常用命令

```powershell
python -m one_context repo list
python -m one_context sync [repo-id ...]
python -m one_context workspace list
python -m one_context profile list
python -m one_context agent list
python -m one_context doctor
```

命令详情见 `packages/one-context/README.md`；清单字段见 `docs/manifests.md`。

## 开发验证

```powershell
python -m one_context doctor
python -m pytest packages/one-context/tests -q
```

项目仍处于 `0.1` 阶段。只有通过清单校验和测试的能力才视为可用；文档不提前宣称生产就绪。

## 与上游的关系

本项目源自 [harnessworld/one-context](https://github.com/harnessworld/one-context)，并针对个人数学科研、Obsidian API 边界和精简维护做持续调整。当前仓库为 [CarmanMS/yafei-one-context](https://github.com/CarmanMS/yafei-one-context)。

## License

MIT，见 `LICENSE`。保留上游版权与许可声明。
