#!/bin/bash
# =============================================================================
# NiFi JWT Token Refresh Script for Prometheus
# Cron: mỗi 2 tiếng + @reboot
# =============================================================================

NIFI_URL="${NIFI_URL:-https://localhost:8443}"
NIFI_USER="${NIFI_USER:?NIFI_USER environment variable is required}"
NIFI_PASS="${NIFI_PASS:?NIFI_PASS environment variable is required}"
TOKEN_FILE="${TOKEN_FILE:-/tmp/nifi_token}"
MAX_RETRIES=3

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1"
}

check_nifi() {
    curl -k -s --connect-timeout 5 "${NIFI_URL}/nifi-api/access/config" > /dev/null 2>&1
}

if ! check_nifi; then
    log "WARNING - NiFi not reachable"
    exit 1
fi

for i in $(seq 1 $MAX_RETRIES); do
    TOKEN=$(curl -k -s --connect-timeout 10 --max-time 15 -X POST \
        "${NIFI_URL}/nifi-api/access/token" \
        -H 'Content-Type: application/x-www-form-urlencoded' \
        -d "username=${NIFI_USER}&password=${NIFI_PASS}")

    if [ -n "$TOKEN" ] && [[ "$TOKEN" =~ ^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$ ]]; then
        # Ensure Prometheus can read the token file (run as prometheus user inside container)
        printf '%s' "$TOKEN" > "$TOKEN_FILE"
        chmod 640 "$TOKEN_FILE"
        chown root:prometheus "$TOKEN_FILE" 2>/dev/null || chmod 644 "$TOKEN_FILE"
        log "SUCCESS - Token refreshed (attempt $i)"
        exit 0
    fi
    log "Attempt $i/$MAX_RETRIES failed"
    sleep 10
done

log "CRITICAL - All attempts failed"
exit 1
