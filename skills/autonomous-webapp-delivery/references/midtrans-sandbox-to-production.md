# Midtrans Snap: Sandbox → Production Migration

## Key Insight: No Domain Whitelist for Snap

Midtrans Snap Client Key does **not** require domain whitelisting/registration. The old docs and older MAP versions had this feature, but in current Midtrans Snap:
- Client Key is safe to expose on any domain (only used to init the Snap popup)
- Server Key handles actual transaction creation (never exposed to frontend)
- No domain registration step needed in MAP dashboard

The user corrected this after I suggested Settings > Access Keys > Domains — that menu doesn't exist for Snap. The `getting-started-1` docs page is for BI-SNAP Core API (not regular Snap), which has a different onboarding flow with IP whitelisting and public/private key exchange.

## Sandbox → Production Checklist

### 1. Environment Variables
```env
MIDTRANS_SERVER_KEY=Mid-server-...     # production key (no "SB-" prefix)
MIDTRANS_IS_PRODUCTION=true            # switches API base + Snap.js URL
PUBLIC_MIDTRANS_CLIENT_KEY=Mid-client-...  # production key (no "SB-" prefix)
MIDTRANS_MERCHANT_ID=M...              # starts with "M" for prod
```

### 2. Snap.js URL auto-detection
The `midtrans.ts` module derives the correct Snap.js URL from `MIDTRANS_IS_PRODUCTION`:
- `true` → `https://app.midtrans.com/snap/snap.js`
- `false` → `https://app.sandbox.midtrans.com/snap/snap.js`

The order page uses `data.isSandbox = SNAP_JS_URL.includes('sandbox')` to gate sandbox-only UI. This auto-corrects when switching to production.

### 3. Sandbox UI cleanup
Things that MUST NOT show in production:
- **CSP headers**: Remove `*.sandbox.midtrans.com` from `script-src`, `connect-src`, `frame-src`. Use dynamic CSP derived from `SNAP_JS_URL`.
- **Hardcoded fallback URLs**: The order page fallback `'https://app.sandbox.midtrans.com/snap/snap.js'` is dead code when `data.snapJsUrl` is always server-provided. Remove it.
- **Sandbox simulator section**: Already gated behind `{#if data.isSandbox && ...}` — no code changes needed if `isSandbox` is correct.
- **Sandbox payment instructions**: Lines like "Ini environment sandbox — tidak perlu bayar beneran" and simulator links are inside the `isSandbox` block — auto-hidden in production.

### 4. Webhook URL
Midtrans webhook needs to be registered in MAP dashboard:
- Settings > Webhook URL
- Set to `https://client-site.meowlabs.id/api/midtrans/webhook`

### 5. Verification
After switching to production:
```bash
curl -sI https://client-site.meowlabs.id/ | grep content-security-policy
# Should NOT contain "sandbox.midtrans.com"
```
