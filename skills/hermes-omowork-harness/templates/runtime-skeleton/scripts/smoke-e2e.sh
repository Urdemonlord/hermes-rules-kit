#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8787}"
MISSION_ID="${1:-m_demo_$(date +%s)}"

echo "[smoke] mission_id=$MISSION_ID"

echo "[smoke] create mission"
curl -sS -X POST "$API_BASE/missions" \
  -H 'content-type: application/json' \
  -d "{\"mission_id\":\"$MISSION_ID\",\"objective\":\"Smoke test runtime flow\",\"mode\":\"AUTONOMOUS\",\"chat_target\":\"telegram:-\",\"budget\":{\"max_total_tokens\":10000,\"max_total_cost_usd\":1,\"max_wall_clock_minutes\":30}}" | jq .

echo "[smoke] wait 2s"
sleep 2

echo "[smoke] mission status"
curl -sS "$API_BASE/missions/$MISSION_ID" | jq .

echo "[smoke] events"
curl -sS "$API_BASE/missions/$MISSION_ID/events" | jq .

echo "[smoke] report"
curl -sS "$API_BASE/missions/$MISSION_ID/report" | jq .

echo "[smoke] done"
