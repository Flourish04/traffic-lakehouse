#!/bin/bash
# =============================================================================
# Deploy Script - NiFi Monitoring Stack (Prometheus + Grafana + Node Exporter)
# Usage: sudo bash deploy.sh
# =============================================================================

set -e

MONITORING_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER_COMPOSE_FILE="docker-compose.monitor.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "============================================="
echo "  NiFi Monitoring Stack - Deployment"
echo "============================================="

# --- Kiểm tra Docker ---
if ! command -v docker &> /dev/null; then
    log_error "Docker chưa được cài đặt!"
    exit 1
fi

log_info "Docker ready"

# --- Tạo network ---
log_info "Tạo Docker network..."
docker network create monitoring_net 2>/dev/null || true

# --- Refresh NiFi token ---
log_info "Refresh NiFi JWT Token..."
chmod +x "$MONITORING_DIR/scripts/refresh_nifi_token.sh" 2>/dev/null || true

if "$MONITORING_DIR/scripts/refresh_nifi_token.sh" 2>&1; then
    log_info "Token refreshed thành công"
else
    log_warn "Token refresh thất bại - NiFi có thể chưa sẵn sàng"
fi

# --- Khởi chạy ---
log_info "Khởi chạy Monitoring Stack..."
cd "$MONITORING_DIR"
docker compose -f "$DOCKER_COMPOSE_FILE" up -d

sleep 10

# --- Kiểm tra targets ---
echo ""
echo "============================================="
echo "  Prometheus Targets"
echo "============================================="
curl -s http://localhost:9090/api/v1/targets 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    targets = d.get('data', {}).get('activeTargets', [])
    if not targets:
        print('  Chưa có active targets (chờ thêm vài giây)')
    for t in targets:
        job = t.get('labels', {}).get('job', '?')
        health = t.get('health', '?')
        err = t.get('lastError', '')[:60]
        if err:
            print(f'  {job:20s} {health:8s} {err}')
        else:
            print(f'  {job:20s} {health:8s}')
except: print('  Prometheus chưa sẵn sàng')
"

echo ""
echo "============================================="
echo "  TRIỂN KHAI HOÀN TẤT!"
echo "============================================="
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000"
echo "  Login:      admin / changeme123"
echo ""
echo "  LƯU Ý: Cập nhật <STORAGE_VPS_IP> trong prometheus.yml"
echo "          nếu muốn giám sát Storage VPS"
echo "============================================="
