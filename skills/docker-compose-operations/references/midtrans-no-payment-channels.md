# Midtrans "No Payment Channels Available" — Merchant Dashboard Not Configured

## Symptom

Checkout flow works but the Midtrans Snap payment modal displays:

> **No payment channels available**
> Please contact Iki Tenun to discuss payment procedure.

All product pages load, cart works, checkout page renders — but the actual payment selection shows zero channels.

## Root Cause

The Midtrans merchant account (`midtrans_dashboard_settings` → Payment Channels) has no active payment channels enabled. This is a Midtrans **dashboard configuration issue**, not a code bug.

**Why this is confusing**: Midtrans Snap API itself works (returns a valid snap token + redirect URL), so the integration looks correct. The error only appears when the Snap UI loads and discovers the merchant has no payment channels configured on Midtrans's side.

### The three conditions that cause this

1. `midtrans_mode` in the DB is set to `live` — so the code hits production Midtrans (`https://app.midtrans.com`)
2. The merchant has not enabled any payment channels (BCA VA, BNI VA, GoPay, QRIS, etc.) in the Midtrans dashboard
3. Or: the merchant's KYC/activation is incomplete

A merchant in **sandbox mode** usually has all channels available by default, which is why it works in development but fails in production.

## Detection

```bash
# Check what mode the app is in
docker exec <container> node -e '
const D = require("better-sqlite3");
const db = new D("/data/dev.db");
const row = db.prepare("SELECT value FROM Setting WHERE key = '\''midtrans_mode'\''").get();
console.log("midtrans_mode:", row?.value);
db.close();
'

# Check the active Midtrans keys
docker exec <container> node -e '
const D = require("better-sqlite3");
const db = new D("/data/dev.db");
const row = db.prepare("SELECT value FROM Setting WHERE key = '\''midtrans_mode'\''").get();
console.log("mode:", row?.value);
console.log("env.MIDTRANS_SERVER_KEY_LIVE exists:", !!process.env.MIDTRANS_SERVER_KEY_LIVE);
console.log("env.MIDTRANS_SERVER_KEY_SANDBOX exists:", !!process.env.MIDTRANS_SERVER_KEY_SANDBOX);
'
```

## Fix

### Immediate — switch to sandbox (if production channels not ready)

```bash
docker exec <container> node -e '
const D = require("better-sqlite3");
const db = new D("/data/dev.db");
db.prepare("UPDATE Setting SET value = '\''sandbox'\'' WHERE key = '\''midtrans_mode'\''").run();
console.log("Switched to sandbox mode");
db.close();
'
```

No restart needed — `getSetting()` reads from DB each request.

### Long-term — enable channels in Midtrans dashboard

1. Go to [Midtrans Dashboard](https://dashboard.midtrans.com/)
2. Login with the merchant credentials for `M283228709`
3. Navigate to **Settings → Payment Channels**
4. Enable at minimum: BCA VA, BNI VA, Bri VA, Mandiri VA, QRIS, GoPay, Shopeepay
5. Confirm each channel (some require KYC verification first)
6. Switch back to live mode in the DB:
   ```bash
   docker exec <container> node -e "
   const D = require('better-sqlite3');
   const db = new D('/data/dev.db');
   db.prepare(\"UPDATE Setting SET value = 'live' WHERE key = 'midtrans_mode'\").run();
   db.close();
   "
   ```

### Verify after enabling channels

```bash
# Create a test transaction
curl -s -X POST http://127.0.0.1:3301/api/checkout/create-transaction \
  -H "Content-Type: application/json" \
  -d '{"items":[{"name":"Test","price":10000,"quantity":1}],"amount":10000,"customer":{"name":"Test","phone":"08123456789"}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('token:', d.get('token','MISSING')[:20]+'...' if d.get('token') else d)"
```

## Related

- `references/sveltekit-midtrans-production-cutover.md` — full production cutover checklist
- `references/midtrans-domain-whitelist-misconception.md` — domain whitelist confusion (BI-SNAP vs regular Snap)
- `references/sveltekit-midtrans-snap-vs-bisnap.md` — Snap vs BI-SNAP distinction
