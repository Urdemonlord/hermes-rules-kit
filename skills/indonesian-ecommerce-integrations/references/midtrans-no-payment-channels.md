# Midtrans "No Payment Channels Available" Error

## Error text

> **No payment channels available**
> Please contact <merchant> to discuss payment procedure.

## Root cause

The merchant account switched to **production mode** (`MIDTRANS_IS_PRODUCTION=true` or DB setting `midtrans_mode=live`) but has **not activated any payment channels** in the Midtrans dashboard. Midtrans Snap returns this error because the production merchant ID has zero enabled payment methods.

Merchant account states that cause this:
- Fresh account, never completed KYC/onboarding
- KYC done but no payment channels selected/activated
- Channels were activated but later disabled (billing issue, expired agreement)
- Account is in "sandbox-only" status — production merchant ID not fully provisioned

## Debug steps

### 1. Check which mode the app is using

```bash
# DB setting (if app uses runtime toggle)
docker exec <container> node -e "
const Database = require('better-sqlite3');
const db = new Database('/data/dev.db');
const s = db.prepare(\"SELECT key, value FROM Setting WHERE key LIKE '%midtrans%'\").all();
s.forEach(r => console.log(r.key + ' = ' + r.value));
db.close();
"
```

### 2. Check server key prefix

```bash
# Server key prefix determines environment
docker exec <container> node -e "console.log(process.env.MIDTRANS_SERVER_KEY?.slice(0,4))"
# "Mid-"       = production (will fail without channels)
# "SB-Mid-"    = sandbox (always works with dummy channels)
```

### 3. Check compose env vars

The `MIDTRANS_IS_PRODUCTION` flag or `midtrans_mode` DB setting controls:
- API base URL (`app.midtrans.com` vs `app.sandbox.midtrans.com`)
- It does NOT control payment channels

## Fix

### Option A — Switch to sandbox (for testing)

```bash
# Via DB setting (if app supports runtime toggle)
docker exec <container> node -e "
const Database = require('better-sqlite3');
const db = new Database('/data/dev.db');
db.prepare(\"UPDATE Setting SET value = 'sandbox' WHERE key = 'midtrans_mode'\").run();
console.log('Switched to sandbox');
db.close();
"
# Then restart
docker restart <container>
```

### Option B — Activate payment channels (for production)

1. Login to [Midtrans Dashboard](https://dashboard.midtrans.com/)
2. Go to **Settings → Payment Channels**
3. Enable the channels your store needs:
   - `credit_card` (requires 3D Secure setup)
   - `bca_va`, `bni_va`, `bri_va`, `mandiri_va`, `permata_va` (virtual accounts)
   - `gopay`, `shopeepay`, `qris` (e-wallet/QR)
   - `cstore` (convenience store)
   - `akulaku` (BNPL)
4. Wait 5–15 minutes for activation to propagate
5. Test with a real transaction flow

### Option C — Verify account fully provisioned

If channels are active but error persists:
- Contact Midtrans support: user@example.com
- Check if KYC/verification documents are still pending
- Account may be restricted due to incomplete business verification

## What the app code does

The SvelteKit integration in this project passes an `enabled_payments` array to the Snap API:

```typescript
enabled_payments: [
  'credit_card',
  'bca_va', 'bni_va', 'bri_va', 'mandiri_va', 'permata_va',
  'other_va',
  'gopay', 'shopeepay', 'qris',
  'cstore', 'akulaku'
]
```

Midtrans Snap then filters this list against what's actually activated on the merchant account. If **none** of the requested channels are active, Snap returns "No payment channels available."

The request itself is valid — the error is purely at the merchant account level.

## Prevention

- Before switching to production, activate at least one payment channel in the Midtrans dashboard
- Test with sandbox first (sandbox has dummy channels always available)
- Keep a runtime mode toggle (sandbox/live) for quick fallback during production cutover
