# Midtrans Snap Redirect — Session Reference (iki-tenun)

## Diagnostic: empty paymentRef detection

```sql
-- Check how many Midtrans orders are broken (no snap token saved)
SELECT 
  CASE WHEN paymentRef IS NULL OR paymentRef = '' THEN 'empty_ref' ELSE 'has_ref' END as ref_status,
  COUNT(*) as cnt
FROM 'Order' 
WHERE paymentMethod = 'midtrans_snap'
GROUP BY ref_status;

-- See all orders with payment details
SELECT 
  datetime(createdAt, 'localtime') as created,
  total,
  paymentMethod,
  CASE WHEN paymentRef IS NULL OR paymentRef = '' THEN 'EMPTY' ELSE substr(paymentRef,1,10) END as ref,
  paymentStatus
FROM 'Order' 
ORDER BY createdAt DESC 
LIMIT 20;
```

## Midtrans API test from Docker container

```bash
# Verify Midtrans API reachable from inside the container
docker exec iki-tenun-app-1 node -e "
const key = process.env.MIDTRANS_SERVER_KEY;
const auth = 'Basic ' + Buffer.from(key + ':').toString('base64');
fetch('https://app.sandbox.midtrans.com/snap/v1/transactions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: auth },
  body: JSON.stringify({
    transaction_details: { order_id: 'test-' + Date.now(), gross_amount: 10000 },
    customer_details: { first_name: 'Test', phone: '0812' }
  })
}).then(r => r.json()).then(d => console.log(d.token ? 'OK' : 'FAIL: ' + (d.status_message || 'unknown')))
  .catch(e => console.error('NETWORK ERROR:', e.message));
"
```

## End-to-end checkout verification (curl)

```bash
COOKIE_FILE="/tmp/iki-test.txt"
rm -f "$COOKIE_FILE"

# 1. Init session
curl -s -c "$COOKIE_FILE" 'https://client-site.meowlabs.id/' -o /dev/null

# 2. Add to cart
curl -s -b "$COOKIE_FILE" -c "$COOKIE_FILE" \
  'https://client-site.meowlabs.id/cart?/add' \
  -H 'Origin: https://client-site.meowlabs.id' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'productId=PRODUCT_ID&quantity=1' -o /dev/null

# 3. Checkout — should redirect to Midtrans
curl -s -b "$COOKIE_FILE" -c "$COOKIE_FILE" \
  'https://client-site.meowlabs.id/checkout' \
  -H 'Origin: https://client-site.meowlabs.id' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'name=Test&phone=0812&address=Addr&city=City&province=Prov&zip=12345'

# Expected: {"type":"redirect","status":302,"location":"https://app.sandbox.midtrans.com/snap/v4/redirection/..."}
```

## Changed files (iki-tenun)

| File | Change |
|------|--------|
| `src/lib/server/midtrans.ts` | Added `finishCallbackUrl` to `CreateTransactionParams`, `callbacks.finish` to request body |
| `src/routes/checkout/+page.server.ts` | Redirect to `snap.redirectUrl` (Midtrans) instead of `/order/{id}`; retry DB update 3x; `paymentMethod: 'pending'` default on order create; best-effort `paymentMethod: 'failed'` on all-gateways-fail |
| `src/routes/order/[id]/+page.server.ts` | Added `fromMidtrans` detection, `snapJsUrl` from `SNAP_JS_URL` |
| `src/routes/order/[id]/+page.svelte` | Removed auto-popup from `onMount`; dynamic Snap.js URL from server data; added return-from-Midtrans message |

## Known remaining debt

- `payment_channel` always defaults to `'BCA'` (no selector in checkout form) — Komerce fallback always uses BCA VA
- Komerce only supports 5 channels (BCA, BNI, BRI, MANDIRI, QRIS) vs Midtrans 12+
- Midtrans page shows only payment methods activated in dashboard (credit card, gopay, shopeepay may need activation)
