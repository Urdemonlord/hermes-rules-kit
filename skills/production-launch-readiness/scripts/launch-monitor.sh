#!/bin/bash
# Production launch monitor — silent on OK, alert on problem
# Place at ~/.hermes/scripts/launch-monitor.sh
# Schedule via: hermes cron --schedule '*/5 * * * *' --script launch-monitor.sh

CONTAINER="${1:-iki-tenun-app-1}"
PORT="${2:-3301}"
URL="http://127.0.0.1:${PORT}"

DISK_USAGE=$(df -h / | awk 'NR==2{print $5}' | tr -d '%')
DISK_AVAIL=$(df -h / | awk 'NR==2{print $4}')
DISK_FREE=$(df -h / | awk 'NR==2{print $3}')

APP_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "not_found")
APP_RUNNING=$(docker inspect --format='{{.State.Running}}' "$CONTAINER" 2>/dev/null || echo "false")

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$URL/" 2>/dev/null || echo "000")
HTTP_SIZE=$(curl -s -o /dev/null -w "%{size_download}" --max-time 5 "$URL/" 2>/dev/null || echo "0")

LOG_ERRORS=$(docker logs "$CONTAINER" 2>&1 | grep -c -E "Error:|error:|SqliteError|ENOENT|ECONNREFUSED")

ALERTS=""
ALERTS_THRESHOLD_CRIT=false

[ "$DISK_USAGE" -gt 85 ] && { ALERTS="${ALERTS}🔴 DISK CRIT: ${DISK_USAGE}% (${DISK_AVAIL} free)\n"; ALERTS_THRESHOLD_CRIT=true; }
[ "$DISK_USAGE" -gt 75 ] && ALERTS="${ALERTS}🟡 DISK WARN: ${DISK_USAGE}%\n"
[ "$APP_RUNNING" != "true" ] && { ALERTS="${ALERTS}🔴 CONTAINER DOWN\n"; ALERTS_THRESHOLD_CRIT=true; }
[ "$APP_HEALTH" = "unhealthy" ] && { ALERTS="${ALERTS}🔴 UNHEALTHY: $CONTAINER\n"; ALERTS_THRESHOLD_CRIT=true; }
[ "$HTTP_STATUS" != "200" ] && { ALERTS="${ALERTS}🔴 HTTP ${HTTP_STATUS} on ${URL}\n"; ALERTS_THRESHOLD_CRIT=true; }
[ "$LOG_ERRORS" -gt 20 ] && ALERTS="${ALERTS}🟡 ${LOG_ERRORS} errors in recent log\n"

# Summary line always included with alerts
if [ "$ALERTS_THRESHOLD_CRIT" = true ]; then
  echo -e "⚠️ LAUNCH ALERT — ${CONTAINER}"
  echo -e "$ALERTS"
  echo "Time: $(TZ=Asia/Jakarta date '+%Y-%m-%d %H:%M WIB')"
  echo "Disk: ${DISK_USAGE}% | Health: ${APP_HEALTH} | HTTP: ${HTTP_STATUS} | Errors: ${LOG_ERRORS}"
  exit 1
elif [ -n "$ALERTS" ]; then
  echo -e "⚠️ LAUNCH WARNING — ${CONTAINER}"
  echo -e "$ALERTS"
  echo "Disk: ${DISK_USAGE}% | Health: ${APP_HEALTH} | HTTP: ${HTTP_STATUS}"
  exit 0
fi
# Silent exit on OK
exit 0
