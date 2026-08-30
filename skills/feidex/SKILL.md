---
name: feidex
description: 配置、启动和诊断飞书/Lark 与 Codex 或 Claude Code 的 feidex 桥接服务。
---

# Feidex

## 安全边界

- 先用 `Get-Command feidex` 定位程序；不要假设用户名、安装目录或仓库盘符。
- `config.toml` 可能含 `app_secret`。不要打印、提交或把凭证放进命令行、日志和回复。
- 不默认启用 `dangerously_skip_permissions` 或同类跳过审批选项；仅在用户明确理解风险并要求时修改。
- `feishu setup/new/bind`、启动服务和 `daemon install/start/stop/restart/uninstall` 都会改变本机或外部状态，执行前须有用户对该动作的明确授权。
- 不用 `taskkill /F` 清理旧实例。若端口或实例冲突，先查看状态，再让用户选择停止哪个实例。

## 定位与只读检查

在仓库根执行：

```powershell
$Feidex = (Get-Command feidex -ErrorAction Stop).Source
$RepoRoot = (git rev-parse --show-toplevel).Trim()
$ConfigPath = Join-Path $RepoRoot 'config.toml'
& $Feidex version
if (Test-Path -LiteralPath $ConfigPath) {
  & $Feidex daemon status --config $ConfigPath
}
```

若 `Get-Command` 失败，报告未安装或未加入 `PATH`，不要猜安装路径。若配置不存在，先说明将创建的位置和所选后端，再经用户同意运行交互式配置：

```powershell
& $Feidex feishu setup --config $ConfigPath --backend codex
# 或由用户明确选择：--backend claude
```

让 feidex 生成配置；不要臆造飞书凭证或模型 ID。

## 前台运行

适合首次联调；用户明确要求启动后执行：

```powershell
& $Feidex serve --config $ConfigPath
```

前台运行用 `Ctrl+C` 停止。若需排障，先读取命令报错和 `feidex daemon status`，不要强杀所有 `feidex.exe` 进程。

## 后台服务

只读命令（日志可能含聊天内容，引用到回复前先脱敏）：

```powershell
& $Feidex daemon status --config $ConfigPath
& $Feidex daemon logs -n 100 --config $ConfigPath
```

以下命令会改变服务状态，逐项获得授权后再执行：

```powershell
& $Feidex daemon install --config $ConfigPath
& $Feidex daemon start --config $ConfigPath
& $Feidex daemon stop --config $ConfigPath
& $Feidex daemon restart --config $ConfigPath
& $Feidex daemon uninstall --config $ConfigPath
```

交付时报告：feidex 版本、实际配置路径、前台或 daemon 模式、最终状态；不得回显密钥。
