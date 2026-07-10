#!/usr/bin/env bash
# =============================================================================
# Octop Docker 一键部署脚本
#
# 在全新机器上使用，只需要本脚本 + octop-latest.tar.gz 镜像文件。
#
# 用法:
#   bash docker_deploy.sh
#   bash docker_deploy.sh --port 9090
#   bash docker_deploy.sh --password mypass123
#   bash docker_deploy.sh --port 9090 --password mypass --api-key sk-xxx
#
# 前提: 镜像文件 octop-latest.tar.gz 与本脚本在同一目录（或已 docker load）。
# =============================================================================
set -euo pipefail

PORT="8088"
PASSWORD="octop"
USERNAME="admin"
API_KEY=""
DASHSCOPE_KEY=""
IMAGE_FILE=""
CONTAINER_NAME="octop"
IMAGE_NAME="octop:latest"

BOLD="\033[1m" GREEN="\033[0;32m" YELLOW="\033[0;33m" RED="\033[0;31m" RESET="\033[0m"
info()  { printf "${GREEN}[octop]${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}[octop]${RESET} %s\n" "$*"; }
error() { printf "${RED}[octop]${RESET} %s\n" "$*" >&2; }
die()   { error "$@"; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)          PORT="$2"; shift 2 ;;
        --password)      PASSWORD="$2"; shift 2 ;;
        --username)      USERNAME="$2"; shift 2 ;;
        --api-key)       API_KEY="$2"; shift 2 ;;
        --dashscope-key) DASHSCOPE_KEY="$2"; shift 2 ;;
        --image)         IMAGE_FILE="$2"; shift 2 ;;
        --name)          CONTAINER_NAME="$2"; shift 2 ;;
        -h|--help)
            cat <<EOF
Octop Docker 一键部署脚本

用法: bash docker_deploy.sh [选项]

选项:
  --port <端口>           访问端口（默认: 8088）
  --password <密码>       初始登录密码（默认: octop，仅首次生效）
  --username <用户名>     初始管理员用户名（默认: admin）
  --api-key <key>         OpenAI API Key
  --dashscope-key <key>   阿里云通义千问 API Key
  --image <文件>          镜像 tar.gz 文件路径
  --name <名称>           容器名称（默认: octop）
  -h, --help              显示帮助
EOF
            exit 0 ;;
        *) die "未知选项: $1（尝试 --help）" ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    die "请使用 root 用户运行此脚本：sudo bash docker_deploy.sh"
fi

if ! command -v docker &>/dev/null; then
    info "Docker 未安装，正在自动安装..."
    if command -v apt-get &>/dev/null; then
        apt-get update -qq
        apt-get install -y -qq docker.io docker-compose-plugin 2>/dev/null || \
        apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    elif command -v dnf &>/dev/null; then
        dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null || \
        dnf install -y docker docker-compose-plugin
    elif command -v yum &>/dev/null; then
        yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null || \
        yum install -y docker docker-compose-plugin
    else
        die "无法自动安装 Docker，请手动安装后重试"
    fi
fi

systemctl start docker 2>/dev/null || service docker start 2>/dev/null || true
systemctl enable docker 2>/dev/null || true
docker --version || die "Docker 安装失败"
info "Docker 就绪: $(docker --version)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$IMAGE_FILE" ]; then
    for candidate in \
        "$SCRIPT_DIR/octop-latest.tar.gz" \
        "$PWD/octop-latest.tar.gz" \
        "/root/octop-latest.tar.gz" \
        "/tmp/octop-latest.tar.gz"; do
        if [ -f "$candidate" ]; then
            IMAGE_FILE="$candidate"
            break
        fi
    done
fi

if docker image inspect "$IMAGE_NAME" &>/dev/null; then
    info "镜像 $IMAGE_NAME 已存在，跳过加载"
elif [ -n "$IMAGE_FILE" ] && [ -f "$IMAGE_FILE" ]; then
    info "正在加载镜像: $IMAGE_FILE..."
    docker load < "$IMAGE_FILE"
    info "镜像加载完成"
else
    die "未找到镜像文件。请将 octop-latest.tar.gz 放到当前目录，或使用 --image 指定路径"
fi

docker image inspect "$IMAGE_NAME" &>/dev/null || die "镜像 $IMAGE_NAME 不存在"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    info "发现已有容器 $CONTAINER_NAME，正在停止并移除..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
fi

info "正在启动 Octop（端口: $PORT，用户: $USERNAME）..."

ENV_ARGS=()
[ -n "$API_KEY" ]       && ENV_ARGS+=(-e "OPENAI_API_KEY=$API_KEY")
[ -n "$DASHSCOPE_KEY" ] && ENV_ARGS+=(-e "DASHSCOPE_API_KEY=$DASHSCOPE_KEY")

docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "${PORT}:${PORT}" \
    -v octop-data:/data/.octop \
    -e HOME=/data \
    -e OCTOP_BIND_HOST=0.0.0.0 \
    -e OCTOP_PORT="$PORT" \
    -e OCTOP_DEFAULT_PASSWORD="$PASSWORD" \
    -e OCTOP_ADMIN_USERNAME="$USERNAME" \
    "${ENV_ARGS[@]}" \
    "$IMAGE_NAME"

info "等待服务启动..."
for _ in $(seq 1 30); do
    if curl -sf "http://localhost:${PORT}/api/health" &>/dev/null; then
        break
    fi
    sleep 2
done

if curl -sf "http://localhost:${PORT}/api/health" &>/dev/null; then
    LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo ""
    printf "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${RESET}\n"
    printf "${GREEN}${BOLD}║   Octop 部署成功！                               ║${RESET}\n"
    printf "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${RESET}\n"
    echo ""
    printf "  访问地址:   ${BOLD}http://${LOCAL_IP:-localhost}:${PORT}${RESET}\n"
    printf "  用户名:     ${BOLD}${USERNAME}${RESET}\n"
    printf "  登录密码:   ${BOLD}${PASSWORD}${RESET}\n"
    printf "  容器名称:   ${BOLD}${CONTAINER_NAME}${RESET}\n"
    printf "  数据卷:     ${BOLD}octop-data${RESET}\n"
    echo ""
    printf "  ${YELLOW}请登录后立即修改默认密码！${RESET}\n"
    echo ""
    printf "  常用命令:\n"
    printf "    查看日志:   docker logs -f ${CONTAINER_NAME}\n"
    printf "    停止服务:   docker stop ${CONTAINER_NAME}\n"
    printf "    重启服务:   docker restart ${CONTAINER_NAME}\n"
    echo ""
else
    warn "服务启动可能较慢，请稍后检查："
    echo "  docker logs -f $CONTAINER_NAME"
fi
