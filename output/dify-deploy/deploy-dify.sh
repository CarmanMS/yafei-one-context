#!/bin/bash
# Dify 一键部署脚本
# 前提：Docker Desktop 已安装并正在运行
# 用法：bash deploy-dify.sh

set -e

# ===== 配置 =====
DIFY_VERSION="main"
INSTALL_DIR="$HOME/dify"
PORT_WEB=3000      # Dify Web 界面端口
PORT_API=5001      # Dify API 端口

# ===== 颜色 =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ===== 前置检查 =====
echo ""
echo "========================================"
echo "  Dify 社区版 一键部署脚本"
echo "========================================"
echo ""

# 检查 Docker
if ! command -v docker &>/dev/null; then
    err "Docker 未安装或未在 PATH 中！"
    echo ""
    echo "请先安装 Docker Desktop："
    echo "  1. 下载: https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
    echo "  2. 运行安装程序"
    echo "  3. 启动 Docker Desktop，等待 Docker Engine 就绪"
    echo "  4. 重新运行此脚本"
    echo ""
    exit 1
fi

# 检查 Docker Engine 是否运行
if ! docker info &>/dev/null; then
    err "Docker Engine 未运行！请先启动 Docker Desktop 并等待其就绪。"
    exit 1
fi

ok "Docker 已就绪: $(docker --version)"
ok "Docker Compose: $(docker compose version --short)"

# 检查端口占用
check_port() {
    local port=$1
    if command -v netstat &>/dev/null; then
        if netstat -an 2>/dev/null | grep -q ":$port .*LISTEN"; then
            warn "端口 $port 已被占用，Dify 可能无法正常启动"
            return 1
        fi
    fi
    return 0
}

check_port $PORT_WEB
check_port $PORT_API

# ===== 克隆 Dify =====
if [ -d "$INSTALL_DIR" ]; then
    warn "目录 $INSTALL_DIR 已存在"
    read -p "是否更新现有部署？(y/n) " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "拉取最新代码..."
        cd "$INSTALL_DIR"
        git pull origin $DIFY_VERSION 2>/dev/null || warn "Git pull 失败，继续使用现有代码"
    else
        info "使用现有代码继续部署"
    fi
else
    info "克隆 Dify 仓库到 $INSTALL_DIR ..."
    git clone --depth 1 -b $DIFY_VERSION https://github.com/langgenius/dify.git "$INSTALL_DIR"
    ok "仓库克隆完成"
fi

# ===== 配置环境变量 =====
DOCKER_DIR="$INSTALL_DIR/docker"
ENV_FILE="$DOCKER_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    info "生成 .env 配置文件..."
    cd "$DOCKER_DIR"
    cp .env.example .env

    # 生成随机密钥
    SECRET_KEY=$(openssl rand -hex 42 2>/dev/null || head -c 42 /dev/urandom | xxd -p 2>/dev/null || echo "change-me-to-random-secret-key-please")
    INIT_PASSWORD=$(openssl rand -hex 8 2>/dev/null || head -c 8 /dev/urandom | xxd -p 2>/dev/null || echo "dify2024")

    # 写入配置
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "mingw64" ]]; then
        # Windows Git Bash
        sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE"
        sed -i "s/^CONSOLE_API_URL=.*/CONSOLE_API_URL=http:\/\/localhost:$PORT_API/" "$ENV_FILE"
        sed -i "s/^CONSOLE_WEB_URL=.*/CONSOLE_WEB_URL=http:\/\/localhost:$PORT_WEB/" "$ENV_FILE"
        sed -i "s/^SERVICE_API_URL=.*/SERVICE_API_URL=http:\/\/localhost:$PORT_API/" "$ENV_FILE"
        sed -i "s/^APP_API_URL=.*/APP_API_URL=http:\/\/localhost:$PORT_API/" "$ENV_FILE"
        sed -i "s/^APP_WEB_URL=.*/APP_WEB_URL=http:\/\/localhost:$PORT_WEB/" "$ENV_FILE"
    else
        # Linux/Mac
        sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE"
        sed -i "s/^CONSOLE_API_URL=.*/CONSOLE_API_URL=http:\/\/localhost:$PORT_API/" "$ENV_FILE"
        sed -i "s/^CONSOLE_WEB_URL=.*/CONSOLE_WEB_URL=http:\/\/localhost:$PORT_WEB/" "$ENV_FILE"
        sed -i "s/^SERVICE_API_URL=.*/SERVICE_API_URL=http:\/\/localhost:$PORT_API/" "$ENV_FILE"
        sed -i "s/^APP_API_URL=.*/APP_API_URL=http:\/\/localhost:$PORT_API/" "$ENV_FILE"
        sed -i "s/^APP_WEB_URL=.*/APP_WEB_URL=http:\/\/localhost:$PORT_WEB/" "$ENV_FILE"
    fi

    ok ".env 配置文件已生成"
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  初始管理员密码: $INIT_PASSWORD${NC}"
    echo -e "${YELLOW}  （请在首次访问时使用此密码注册）${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
else
    info ".env 已存在，跳过配置"
fi

# ===== 启动服务 =====
info "启动 Dify 服务（首次启动需要下载镜像，请耐心等待 5-15 分钟）..."
cd "$DOCKER_DIR"
docker compose up -d

# ===== 等待服务就绪 =====
info "等待服务启动..."
echo ""
echo "  服务启动状态："
docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null || docker compose ps

echo ""
echo "  服务正在后台启动中，请等待 1-3 分钟让所有服务就绪。"
echo ""
echo "  查看启动日志:  cd $DOCKER_DIR && docker compose logs -f"
echo "  查看服务状态:  cd $DOCKER_DIR && docker compose ps"
echo "  停止服务:      cd $DOCKER_DIR && docker compose down"
echo "  重启服务:      cd $DOCKER_DIR && docker compose restart"
echo ""
ok "部署脚本执行完成！"
echo ""
echo "========================================"
echo "  Dify 访问地址"
echo "========================================"
echo ""
echo "  Web 界面:  http://localhost:$PORT_WEB"
echo "  API 地址:  http://localhost:$PORT_API"
echo ""
echo "  首次访问请注册管理员账号。"
echo "========================================"
echo ""
