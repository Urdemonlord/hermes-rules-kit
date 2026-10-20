# Midtrans Webhook — Common Pitfalls & Fixes

## Test Notification Failure

Midtrans sends test notifications with dummy order IDs like `payment_notif_test_M283228709_...`.

**Symptom**: "Tes gagal" in Midtrans dashboard when testing notification URL.

**Root cause**: Webhook returns 404 for non-existent order IDs. Midtrans interprets any non-200 response as failure.

**Fix**:
```typescript
const order = await prisma.order.findUnique({ where: { id: orderId } })
if (!order) {
    console.log('[midtrans-webhook] Order not in DB (test/unknown):', orderId)
    return json({ status: 'ok', note: 'test order, not found in db' })
}
```

**Also**: `getTransactionStatus()` call (double-verify via Midtrans API) will fail with empty JSON for test IDs. Wrap in try/catch, don't let it throw:
```typescript
try {
    const apiStatus = await getTransactionStatus(orderId)
    // ...
} catch (e) {
    console.warn('[midtrans-webhook] Could not verify via API (test order?):', orderId)
}
```

## Webhook IP Verification

Midtrans publishes their IP ranges. Verify `x-forwarded-for` origin to prevent spoofed payment notifications:

```
Midtrans IPs (as of 2026):
- 203.0.113.10/23
- 203.0.113.10/23
- 203.0.113.10/24
- 203.0.113.10/24
```

Note: Sandbox may use different IPs. Log but don't reject in sandbox mode.

## Signature Verification

Midtrans signature is SHA512:
```
SHA512(order_id + status_code + gross_amount + server_key)
```

Verify this BEFORE any DB operations. Reject with 403 on mismatch.

## Status Mapping

| Midtrans status | paymentStatus | orderStatus |
|----------------|---------------|-------------|
| settlement | paid | processing |
| capture + fraud:accept | paid | processing |
| capture + fraud:fraud | failed | cancelled |
| pending | pending | — |
| deny | failed | cancelled |
| expire | expired | cancelled |
| cancel | cancelled | cancelled |

## Stock Restore

Only restore stock on payment failure/expiry if it was previously set to `paid` (idempotent guard to prevent double-restore on Midtrans retries).
