---
name: feidex
description: 启动飞书 ↔ Claude Code 桥接服务。feidex serve 前台运行，飞书群 @机器人 即转发到 Claude Code 处理；也支持 daemon 模式安装为 Windows 服务。
triggers:
  - feidex
  - 飞书
  - feishu
  - 启动飞书
  - 飞书机器人
  - 飞书服务
---

# Feidex — 飞书 ↔ Claude Code 桥接

## 安装位置

```
C:\Users\wucha\AppData\Local\Programs\feidex\feidex.exe
```

配置文件（已在 PATH 可用时直接调用 `feidex`）：

```
D:\赵亚菲\yafei-one-context\config.toml
```

> ⚠️ **本机现状（2026-07-25 同步时校验）**：上述 `feidex.exe` 与 `config.toml` **均未找到**，`feidex` 也不在 PATH。
> 首次使用前需：① 安装 feidex 到上面的路径（或加入 PATH）；② 在仓库根 `D:\赵亚菲\yafei-one-context` 创建 `config.toml`（可用 `feidex feishu setup` 生成）。

## 启动方式

### 前置：选择模型

启动前**必须**询问用户要使用哪个模型。从 ZenMux API 获取可用模型列表：

```bash
curl -s "https://zenmux.ai/api/v1/models" | python -c "
import json, sys
from datetime import datetime, timedelta
data = json.load(sys.stdin)
models = data.get('data', [])
# 过滤条件：context_length >= 1M、发布日期在 3 个月内、价格 <= $0.5/MT
cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
def get_price(m):
    try: return m['pricings']['prompt'][0]['value']
    except: return 999
models = [m for m in models if m.get('context_length', 0) >= 1000000 and m.get('publish_time', '2000-01-01') >= cutoff and get_price(m) <= 0.5]
def get_time(m):
    try: return m.get('publish_time', '2000-01-01')
    except: return '2000-01-01'
# 主排序：价格低→高；同价格：新→旧（时间降序）
models_sorted = sorted(models, key=lambda m: (get_price(m), get_time(m)))
# 二次排序：同价格组内按 publish_time 降序
from itertools import groupby
result = []
for price, group in groupby(models_sorted, key=get_price):
    grp = list(group)
    grp.sort(key=lambda m: get_time(m), reverse=True)  # 新→旧
    result.extend(grp)
for i, m in enumerate(result, 1):
    price = get_price(m)
    ctx = m.get('context_length', 0) // 1000000
    pub = m.get('publish_time', '?')
    print(f\"{i:3d}. {m['id']:50s} \${price}/MT  [{ctx}M ctx]  {pub}\")
"
```

向用户展示模型列表（至少展示前 20 个最便宜的），询问用户选择。获取用户选择后：

1. 修改 `config.toml` 的 `[claude]` 段，**模型 ID 后加 `[1m]` 后缀**：
   ```toml
   [claude]
     model = "用户选择的模型 ID[1m]"
   ```
   例如用户选 `deepseek/deepseek-v4-flash`，则写入 `model = "deepseek/deepseek-v4-flash[1m]"`
2. 然后再执行启动命令。

**如果用户说"用默认的"或"不用问"，则跳过询问，直接使用 config.toml 中现有的 model 值。**

### 前台运行（推荐调试用）

启动前自动清理旧进程，一条命令搞定：

```bash
taskkill /F /IM feidex.exe 2>/dev/null; feidex serve --config config.toml
```

在 `config.toml` 所在目录（`D:\赵亚菲\yafei-one-context`）执行。启动后飞书群里 @机器人 消息会转发到 Claude Code 处理。

### Windows 服务（后台常驻）

```bash
# 安装为 Windows 服务
feidex daemon install

# 启动 / 停止 / 重启 / 查看状态
feidex daemon start
feidex daemon stop
feidex daemon restart
feidex daemon status

# 卸载服务
feidex daemon uninstall
```

## 配置概要（config.toml）

| 段 | 关键字段 | 说明 |
|---|---------|------|
| `[feishu]` | `app_id`, `app_secret` | 飞书应用凭证 |
| `[feishu]` | `group_at_only = true` | 群聊仅响应 @机器人 |
| `[feishu]` | `reply_in_thread = true` | 在消息线程内回复 |
| `[claude]` | `command = "claude"` | Claude Code CLI 命令 |
| `[claude]` | `model` | 使用的模型 |
| `[claude]` | `dangerously_skip_permissions = true` | 跳过权限确认（自动模式） |
| `[[workspace]]` | `cwd` | 工作目录 |

## 其他命令

```bash
feidex feishu setup     # 交互式飞书应用配置
feidex feishu new       # 创建新飞书应用
feidex feishu bind      # 绑定飞书应用
feidex version          # 查看版本
```

## 注意事项

- 前台运行时 Ctrl+C 停止服务
- `dangerously_skip_permissions = true` 意味着 Claude Code 不会弹权限确认，所有工具调用自动批准
- 飞书消息中的 @mention 会被转发为 Claude Code 输入
- `reply_in_thread = true` 时回复在飞书消息线程内，不会刷屏主群
