#!/usr/bin/env bash
# Drive a real checkout against a scratch container, on its own volume, before deploy.
# Proves the order-creation path that no unit test covers.
#
# Usage: ./drive-checkout.sh [port]
set -uo pipefail

PORT="${1:-3302}"
APP=iki-tenun-test
IMAGE="${IMAGE:-iki-tenun-app:latest}"
B="http://127.0.0.1:${PORT}"
VOL="${VOL:-client-site_scratch}"
JAR="$(mktemp)"

# Never mount the production volume here: the seed writes users and products.
docker rm -f "$APP" >/dev/null 2>&1
docker volume rm "$VOL" >/dev/null 2>&1

docker run -d --name "$APP" -p "127.0.0.1:${PORT}:3000" \
  -v "${VOL}:/data" \
  -e DATABASE_URL=file:/data/dev.db -e DATABASE_FILE=/data/dev.db \
  -e NODE_ENV=production -e ORIGIN="$B" \
  -e ADMIN_PASSWORD="${ADMIN_PASSWORD:?set ADMIN_PASSWORD for the seed}" \
  "$IMAGE" >/dev/null

echo "waiting for container..."
for _ in $(seq 30); do
  curl -sf -o /dev/null --max-time 2 "$B/" && break
  sleep 1
done

# The seed is best-effort in the entrypoint, so check it actually produced a catalogue.
echo "--- seed row counts ---"
docker exec "$APP" node -e '
  const {DatabaseSync} = require("node:sqlite");
  const db = new DatabaseSync("/data/dev.db", {readonly:true});
  for (const t of ["Product","ProductVariant","User","Order"])
    console.log(t, db.prepare(`SELECT COUNT(*) c FROM "${t}"`).get().c);
'
echo "All-zero Product/ProductVariant means the seed crashed - read docker logs $APP."

# SvelteKit rejects cross-origin form POSTs without an Origin header (403 CSRF).
post() { curl -s -b "$JAR" -c "$JAR" -X POST "$1" -H "Origin: $B" \
         -H 'Content-Type: application/x-www-form-urlencoded' -d "$2" --max-time 20 \
         -w '\nHTTP %{http_code}\n'; }

echo "--- login ---"
post "$B/login" "email=${ADMIN_EMAIL:user@example.com}&password=<redacted>" | tail -3

PID=$(docker exec "$APP" node -e '
  const {DatabaseSync} = require("node:sqlite");
  console.log(new DatabaseSync("/data/dev.db",{readonly:true})
    .prepare("SELECT id FROM \"Product\" WHERE isActive=1 LIMIT 1").get().id);
')

echo "--- add to cart (product $PID) ---"
post "$B/cart?/add" "productId=${PID}&quantity=1" | tail -2

echo "--- checkout ---"
post "$B/checkout" \
  "name=Smoke Test&phone=08123456789&address=Jl Test 1&city=Semarang&province=Jawa Tengah&zip=50123&shipping_courier=jne&shipping_service=REG&shipping_cost=15000" \
  | tail -2

OID=$(docker exec "$APP" node -e '
  const {DatabaseSync} = require("node:sqlite");
  const r = new DatabaseSync("/data/dev.db",{readonly:true})
    .prepare("SELECT id FROM \"Order\" ORDER BY createdAt DESC LIMIT 1").get();
  if (r) console.log(r.id);
')

if [ -z "$OID" ]; then
  echo "FAIL: no order row - the create-order action did not commit."
  docker logs "$APP" 2>&1 | tail -30
  exit 1
fi

echo "--- order $OID persisted, rendering it ---"
curl -s -b "$JAR" -o /dev/null -w "GET /order/<id> -> %{http_code}\n" "$B/order/$OID" --max-time 10

cat <<EOF

Order \$OID is in the scratch DB. Confirm the variant/price split in the admin
UI before deleting. Clean up when done:
  docker rm -f $APP && docker volume rm $VOL
EOF
