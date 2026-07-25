# Dify 部署指南 — 国内轻量云服务器版

> 目标：一台 34元/月 的轻量云服务器 → Dify + 知识库 + 对外智能体
> 包含你的 `knowledge/` 目录全部文档

---

## 第一步：购买服务器（5分钟）

### 推荐方案：阿里云轻量应用服务器

| 配置 | 价格 | 链接 |
|------|------|------|
| 2核 2G 50G 固定带宽 | **34元/月**（新用户首购价） | [阿里云轻量](https://www.aliyun.com/product/swas) |
| 2核 4G 60G | 约 60元/月 | 更宽裕 |

**购买要点：**
1. 地域选 **华东2（上海）** 或 **华南1（深圳）** — 离你近延迟低
2. 操作系统选 **Ubuntu 22.04** 或 **CentOS 7.9**
3. 防火墙/安全组 **放行端口：80、443、3000、5001**
4. 建议买 **3个月或1年**（新人价只有首购）

### 备选：腾讯云 Lighthouse

| 配置 | 价格 |
|------|------|
| 2核 2G 40G | 约 34元/月 |

同样安装 Ubuntu 22.04。

---

## 第二步：连接服务器

用 SSH 客户端连接（Windows 可用 PowerShell 或 Termius/Putty）：

```bash
ssh root@你的服务器IP
```

> Windows 11/10 自带 OpenSSH，直接在 PowerShell 运行上面命令即可
> 密码在购买成功后控制台能看到

---

## 第三步：一键部署 Dify

连上服务器后，逐条执行：

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | bash

# 2. 启动 Docker
systemctl enable docker && systemctl start docker

# 3. 下载 Dify 部署文件
git clone https://github.com/langgenius/dify.git /opt/dify
cd /opt/dify/docker

# 4. 复制配置
cp .env.example .env

# 5. 启动（后台运行）
docker compose up -d

# 6. 检查是否启动成功
docker compose ps
```

> ⏳ 第一次启动需要下载镜像，约 2-5 分钟（取决于网络）

启动成功后访问：**http://你的服务器IP**

初始账号：`admin@dify.ai`
初始密码：`admin123`

---

## 第四步：配置知识库

### 4.1 在 Dify Web 界面操作

1. 登录后 → 点击 **知识库**
2. 点击 **创建知识库**
3. 上传方式选择 **上传文件**
4. 将你本地的 `knowledge/` 目录**压缩成 zip**，直接拖拽上传
5. 选择分段策略（默认即可）
6. 创建成功后，记下 **知识库 ID**（URL 中可以看到）

### 4.2 或用脚本批量同步

在**你的电脑**上运行同步脚本：

```bash
# 安装依赖
pip install requests

# 运行同步（先获取 API Key）
python deploy/dify/sync-knowledge.py \
  --url http://你的服务器IP \
  --api-key 你的数据集APIKey \
  --dataset-id 你的知识库ID \
  --dir ../../knowledge
```

> API Key 获取：Dify → 知识库 → API 访问 → 创建密钥

---

## 第五步：创建智能体

1. Dify 中点击 **工作室 → 创建应用**
2. 类型选择 **对话型应用** 或 **Agent**
3. 名称：`one-context 知识助手`
4. **提示词设置**（示例）：

```markdown
你是 one-context 知识库助手。
请根据知识库文档回答用户问题。
如果你不知道答案，请明确说不知道，不要编造。
回答请用中文，简洁明了。
```

5. **知识库**：选择刚才创建的知识库
6. 模型选择（推荐）：

| 模型 | 推荐理由 |
|------|---------|
| DeepSeek V2 / V3 | 国内、便宜、中文好 |
| 通义千问 | 阿里云免费用量 |
| OpenAI GPT-4o | 效果最好但需要海外信用卡 |

7. 点击 **发布**

---

## 第六步：开放给外部用户

Dify 提供三种对外暴露方式：

### 方式 A：公开链接（最简单）

Dify 中 → 应用 → **概览** → **发布** → 开启 **公开链接**
→ 复制 URL 发给用户即可

### 方式 B：嵌入网页

```html
<iframe src="https://你的IP/chatbot/应用ID" width="100%" height="600px"></iframe>
```

### 方式 C：API 调用

```bash
curl -X POST https://你的IP/v1/chat-messages \
  -H "Authorization: Bearer 你的APIKey" \
  -H "Content-Type: application/json" \
  -d '{"query": "one-context 是什么？", "user": "test-user"}'
```

---

## 日常维护

### 查看日志
```bash
cd /opt/dify/docker
docker compose logs -f api
```

### 更新 Dify
```bash
cd /opt/dify
git pull
cd docker
docker compose pull
docker compose up -d
```

### 备份知识库
```bash
# 你的本地 knowledge/ 就是备份，用 git 管理即可
cd deploy/dify
python sync-knowledge.py --url http://你的IP --api-key xxx --dataset-id xxx
```

---

## 费用估算

| 项目 | 费用 |
|------|------|
| 轻量云服务器 | ~34元/月 |
| 域名（可选） | ~30元/年 |
| LLM 模型费用 | DeepSeek：约 0.5元/百万token ≈ 1000次对话=几毛钱 |
| **合计** | **约 34-50元/月** |

> 不需要域名 — 直接给用户 IP 地址就可以访问
> 模型走 DeepSeek 国内 API，无需海外信用卡

---

## 常见问题

**Q: 服务器重启后 Dify 会自动启动吗？**
A: 会。docker 已设置 `restart: always` + `systemctl enable docker`

**Q: 100 人同时问会卡吗？**
A: 2核2G 约支撑 10-20 并发。如果人数多了，升级到 4核4G 即可

**Q: 知识库文档更新了怎么办？**
A: 本地改完 → 跑 `sync-knowledge.py` 脚本同步到 Dify

**Q: 数据安全？**
A: 所有数据在你自己购买的服务器上，Dify 容器不向外部发送任何数据
