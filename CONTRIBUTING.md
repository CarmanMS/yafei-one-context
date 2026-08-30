# Contributing

本仓是 `CarmanMS/yafei-one-context` 的数学科研分支。改动应保持小、可验证，并尊重个人知识库边界。

## 环境

```bash
git clone --recurse-submodules git@github.com:CarmanMS/yafei-one-context.git
cd yafei-one-context
python -m venv .venv
```

激活环境：

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

安装唯一的 Python 项目及开发依赖：

```bash
python -m pip install -e "./packages/one-context[dev]"
```

根目录没有独立 `requirements.txt` 或 Node 项目；`packages/one-context/pyproject.toml` 是 CLI 依赖的事实来源。

## 开发流程

1. 从 `main` 创建短生命周期分支。
2. 只修改任务所需文件，保留已有的无关改动。
3. 对非平凡逻辑补最小测试。
4. 运行：

```bash
python -m one_context doctor
python -m pytest packages/one-context/tests -q
git diff --check
```

5. 使用清晰的 Conventional Commit，例如 `fix(sync): report partial failures`。

## 目录边界

- CLI：`packages/one-context/`
- 清单：`meta/`
- 跨仓规格：`features/`
- 工作流：`skills/`
- 架构文档：`docs/`
- 子仓工作副本：`repos/`，不提交
- 个人 vault：`knowledge/` submodule

`knowledge/**` 只能经 Obsidian Local REST API 访问。不要通过文件系统读取、搜索或修改笔记；详见 `AGENTS.md` 和 `skills/obsidian-knowledge/SKILL.md`。

`onecxt adapt` 产生的工具配置只在本地使用，不加入提交。

## Pull Request

PR 应说明：

- 问题与最小改动
- 验证命令及结果
- 对清单、兼容性或知识边界的影响
- 尚未解决的限制

不要提交密钥、私人笔记、个人会话日志、生成媒体或子仓内容。安全问题按 `SECURITY.md` 私下报告。

## License

贡献按 `LICENSE` 中的 MIT License 授权。
