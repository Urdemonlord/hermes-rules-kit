# Midtrans Webhook: Test Notification Must Return 200

## The Problem

Midtrans dashboard has a "Tes URL notifikasi" button. It sends a test POST to your webhook URL with a real signed payload. If your webhook returns **anything other than 200 OK**, Midtrans reports "Gagal mengirim notifikasi HTTP karena terdapat kendala pada URL" — even if the URL is accessible and your code works.

## Root Cause

Midtrans test tool expects 200 OK. Common failure modes:

1. **403 on invalid signature**: Your webhook verifies the signature and throws `error(403, 'Invalid signature')` — Midtrans sees 403 and reports failure.

2. **405 on GET**: Midtrans might ping with GET first. Only POST is handled → 405 → "kendala pada URL".

3. **500 on missing server key**: Webhook code checks `if (!SERVER_KEY) throw error(500)` — 500 is not 200.

4. **Cloudflare blocking**: Cloudflare WAF can block Midtrans IPs before they reach your server.

## The Fix

```typescript
// Verify signature
const valid = verifySignature(orderId, statusCode, grossAmount, SERVER_KEY, signatureKey)
if (!valid) {
  // Log for debugging, but return 200 so Midtrans test tool passes
  console.error('[midtrans-webhook] Invalid signature:', { orderId, statusCode })
  return json({ status: 'ignored', reason: 'invalid_signature' })
  // NOT: throw error(403, 'Invalid signature') ← THIS BREAKS THE TEST TOOL
}

// Handle test orders that don't exist in DB
const order = await prisma.order.findUnique({ where: { id: orderId } })
if (!order) {
  console.log('[midtrans-webhook] Order not in DB (test/unknown):', orderId)
  return json({ status: 'ok', note: 'test order, not found in db' })
  // NOT: throw error(404) ← THIS ALSO BREAKS THE TEST TOOL
}
```

## The Principle

Midtrans test notification tool is a connectivity + basic auth check. It does NOT require the notification to be fully processed. Just return 200 OK. Real production notifications will have valid signatures and real order IDs — those WILL be processed normally.

## Testing Locally

```bash
# Should return 200, not 403
curl -X POST https://client-site.meowlabs.id/api/midtrans/webhook \
  -H "Content-Type: application/json" \
  -d '{"order_id":"test","status_code":"200","gross_amount":"10000","signature_key":"test","transaction_status":"settlement"}'
# {"status":"ignored","reason":"invalid_signature"}
```

## Also Check

- **GET must return 405** (Method Not Allowed), not 500. Some tools probe with GET first.
- If behind Cloudflare, ensure no WAF rules block Midtrans IPs.
- The `MIDTRANS_IS_PRODUCTION` env var only affects Snap.js URL and API base URL — not the webhook.
