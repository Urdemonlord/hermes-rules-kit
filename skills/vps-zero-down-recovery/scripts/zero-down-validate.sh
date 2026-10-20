#!/usr/bin/env bash
# Quick validation: all services UP and healthy after reboot
# Usage: ./zero-down-validate.sh

set -u

echo "=== ZERO-DOWN VALIDATION ==="
echo ""

issues=0

echo "1. SWAP STATUS:"
swapon --show
echo ""

echo "2. DOCKER CONTAINERS:"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | head -15
echo ""

echo "3. SYSTEMD SERVICES (user):"
systemctl --user list-units --type=service --state=running | grep -E 'hermes-gateway|the gateway|agentwa|video' || echo "  (none found)"
echo ""

echo "4. SYSTEMD SERVICES (system):"
systemctl list-units --type=service --state=running | grep -E 'docker|nginx|video' || echo "  (none found)"
echo ""

echo "5. PORT HEALTH CHECK:"
for port in 3101 8890 8765 8080 3301 20129; do
  status=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:$port/ 2>/dev/null || echo "000")
  if [[ "$status" == "000" ]]; then
    echo "  ❌ :$port → UNREACHABLE"
    ((issues++))
  elif [[ "$status" =~ ^(200|301|302|307|308)$ ]]; then
    echo "  ✓ :$port → HTTP $status"
  else
    echo "  ⚠ :$port → HTTP $status (unexpected)"
    ((issues++))
  fi
done
echo ""

echo "6. PUBLIC ENDPOINTS:"
for domain in security-gateway.meowlabs.id client-site.id deploy.meowlabs.id; do
  status=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 https://"$domain"/ 2>/dev/null || echo "000")
  if [[ "$status" == "000" ]]; then
    echo "  ❌ $domain → UNREACHABLE"
    ((issues++))
  elif [[ "$status" =~ ^(200|301|302|307|308)$ ]]; then
    echo "  ✓ $domain → HTTPS $status"
  else
    echo "  ⚠ $domain → HTTPS $status (unexpected)"
    ((issues++))
  fi
done
echo ""

echo "7. RESOURCE STATE:"
free -h | grep -E 'Mem|Swap'
df -h / | tail -1
echo ""

echo "8. UPTIME:"
uptime
echo ""

if [ "$issues" -eq 0 ]; then
  echo "✅ ZERO-DOWN: All systems healthy"
  exit 0
else
  echo "⚠️ ISSUES FOUND: $issues problem(s) detected"
  exit 1
fi
