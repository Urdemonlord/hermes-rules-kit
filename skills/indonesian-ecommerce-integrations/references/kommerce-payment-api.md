# Komerce Payment API — Virtual Account & QRIS

Base URL (sandbox): `https://api-sandbox.collaborator.komerce.id/user`
Base URL (production): `https://api.collaborator.komerce.id/user`
Auth: `x-api-key: YOUR_API_KEY` header (DIFFERENT from shipping `key:` header)

## Endpoints

### POST /api/v1/user/payment/create — Create Payment

```json
// Request
{
  "order_id": "string (required, your internal order ID)",
  "payment_type": "bank_transfer | qris",
  "channel_code": "BCA | BNI | BRI | MANDIRI | QRIS",
  "amount": 25000,
  "customer": {
    "name": "string (required)",
    "email": "string (required)",
    "phone": "string (required, minimum 8 digits)"
  },
  "items": [
    {
      "name": "string",
      "price": 25000,
      "quantity": 1
    }
  ]
}

// Response
{
  "meta": { "message": "success create payment", "code": 200, "status": "success" },
  "data": {
    "payment_id": "KPAY-0a36/KM/2026",
    "external_id": "openapi-c506...",
    "payment_url": "https://pay-sandbox.komerce.my.id/11d2f...",
    "va_number": "381659999775217",       // empty for QRIS
    "qr_string": "some-random-qr-string",  // empty for VA
    "bank_code": "BCA",                    // empty for QRIS
    "bank_name": "Bank Central Asia",      // empty for QRIS
    "amount": 25000,
    "status": "PENDING",
    "expired_at": "2026-07-17T06:58:41+07:00",
    "created_at": "2026-07-17T05:58:41+07:00"
  }
}
```

### GET /api/v1/user/payment/status/{payment_id} — Check Status

Response:
```json
{
  "meta": { "message": "success get payment", "code": 200, "status": "success" },
  "data": {
    "payment_id": "KPAY-0a36/KM/2026",
    "order_id": "your-internal-order-id",
    "bank_code": "BCA",
    "va_number": "381659999775217",
    "amount": 25000,
    "merchant_receives": 22750,
    "currency": "IDR",
    "payment_type": "bank_transfer",
    "status": "PENDING",           // PENDING | PAID | EXPIRED | CANCELED | FAILED
    "sender_name": "",
    "expired_at": "2026-07-17 06:58:41",
    "created_at": "2026-07-17 05:58:41",
    "paid_at": "",
    "cancel_reason": "",
    "canceled_at": ""
  }
}
```

### POST /api/v1/user/payment/cancel — Cancel Payment

```json
// Request
{ "payment_id": "KPAY-0a36/KM/2026" }

// Response
{
  "meta": { "message": "success cancel payment", "code": 200, "status": "success" },
  "data": {
    "payment_id": "KPAY-0a36/KM/2026",
    "status": "CANCELED",
    "canceled_at": "2026-07-16T22:58:43.315Z",
    "reason": "User requested cancellation"
  }
}
```

### POST /api/v1/user/payment/callback — Webhook (Komerce → You)

Komerce POSTs to your configured webhook URL:
```json
{
  "payment_id": "KPAY-0a36/KM/2026",
  "status": "PAID",
  "order_id": "your-internal-order-id"
}
```

**Always double-check** by calling GET status endpoint — never trust webhook body alone.

## Status Mapping

| Komerce Status | Your paymentStatus | Your orderStatus |
|---------------|-------------------|-----------------|
| PENDING | pending | pending |
| PAID | paid | processing |
| EXPIRED | failed | cancelled |
| CANCELED | failed | cancelled |
| FAILED | failed | cancelled |

## Available Payment Channels

| Code | Name | Type |
|------|------|------|
| BCA | BCA Virtual Account | bank_transfer |
| BNI | BNI Virtual Account | bank_transfer |
| BRI | BRI Virtual Account | bank_transfer |
| MANDIRI | Mandiri Virtual Account | bank_transfer |
| QRIS | QRIS | qris |

## Phone Validation

Komerce validates `customer.phone` must be at least **8 digits**. Phone numbers like `0812` will fail with:
```json
{ "meta": { "message": "customer.phone must be at least 8 digits", "code": 422, "status": "failed" } }
```

## Minimum Amount

Minimum payment amount is Rp10,000 (validated server-side).

## QR Code Display

For QRIS payments, generate a QR image from the `qr_string`:
```html
<img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={encodeURIComponent(qrString)}" alt="QRIS" />
```
