#!/bin/bash
# ==============================================================
# deploy.sh — Dify 一键部署脚本（在服务器上运行）
# 用法: bash deploy.sh
# ==============================================================
set -e

echo "========================================"
echo "  Dify 一键部署"
echo "========================================"

# 1. 安装 Docker
echo "[1/5] 安装 Docker..."
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | bash
  systemctl enable docker
  systemctl start docker
else
  echo "  ✅ Docker 已安装"
fi

# 2. 安装 Docker Compose
echo "[2/5] 检查 Docker Compose..."
if ! docker compose version &>/dev/null; then
  echo "  ⚠️  Docker Compose 未安装，尝试安装..."
  DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
  mkdir -p $DOCKER_CONFIG/cli-plugins
  curl -SL "https://github.com/docker/compose/releases/download/v2.29.0/docker-compose-$(uname -s)-$(uname -m)" -o $DOCKER_CONFIG/cli-plugins/docker-compose
  chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
fi
echo "  ✅ Docker Compose 就绪"

# 3. 下载 Dify
echo "[3/5] 下载 Dify..."
if [ ! -d "/opt/dify" ]; then
  git clone https://github.com/langgenius/dify.git /opt/dify
else
  echo "  ✅ Dify 已存在，拉取更新"
  cd /opt/dify && git pull
fi

# 4. 配置环境变量
echo "[4/5] 配置环境..."
cd /opt/dify/docker
if [ ! -f ".env" ]; then
  cp .env.example .env
  # 生成随机密钥
  SECRET=$(openssl rand -base64 42 | tr -d /=+ | cut -c1-32)
  sed -i "s/^SECRET_KEY=.*/SECRET_KEY=${SECRET}/" .env
  echo "  ✅ 已生成密钥"
else
  echo "  ✅ .env 已存在"
fi

# 5. 启动
echo "[5/5] 启动 Dify..."
docker compose up -d

echo ""
echo "========================================"
echo "  🎉 Dify 部署完成!"
echo "========================================"
echo ""
echo "  访问地址: http://$(curl -s ifconfig.me || echo '你的服务器IP')"
echo "  初始账号: admin@dify.ai"
echo "  初始密码: admin123"
echo ""
echo "  常用命令:"
echo "    查看状态:  docker compose ps"
echo "    查看日志:  docker compose logs -f api"
echo "    停止:      docker compose down"
echo "    重启:      docker compose up -d"
echo "========================================"
