# This directory contains Prometheus configuration files.
#
# IMPORTANT: The nifi_token file is NOT committed to this repository.
# It is generated at runtime by monitoring/scripts/refresh_nifi_token.sh
# and stored at /tmp/nifi_token on the host system.
#
# To set up monitoring:
#   1. Source your environment: source .env.monitoring
#   2. Generate initial token: ./scripts/refresh_nifi_token.sh
#   3. Start monitoring: docker compose -f docker-compose.monitor.yml up -d
#
# See: monitoring/scripts/refresh_nifi_token.sh
