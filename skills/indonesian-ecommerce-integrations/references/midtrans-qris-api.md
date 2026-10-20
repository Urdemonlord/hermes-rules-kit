# Midtrans QRIS API — Full Contract & Notes

## Endpoints

| Environment | Base URL |
|---|---|
| Sandbox | `https://api.sandbox.midtrans.com/v2` |
| Production | `https://api.midtrans.com/v2` |

## QRIS Charge

```
POST /v2/charge
```

### Supported Acquirers

| Acquirer Code | Provider | Notes |
|---|---|---|
| `gopay` | GoPay | Most common. Must be activated first on dashboard |
| `airpay shopee` | ShopeePay (via AirPay Shopee) | Separate activation required |

If no `qris.acquirer` is specified, Midtrans auto-selects based on your merchant configuration.

### Full Request Schema

```json
{
  "payment_type": "qris",
  "transaction_details": {
    "order_id": "string (required, unique)",
    "gross_amount": "number (required, in IDR)"
  },
  "item_details": [
    {
      "id": "string",
      "price": "number",
      "quantity": "number",
      "name": "string",
      "brand": "string (optional)",
      "category": "string (optional)",
      "merchant_name": "string (optional)"
    }
  ],
  "customer_details": {
    "first_name": "string",
    "last_name": "string",
    "email": "string",
    "phone": "string",
    "billing_address": {},
    "shipping_address": {}
  },
  "qris": {
    "acquirer": "gopay"
  }
}
```

### POS Integration Header

For POS / IoT use cases, add:
```
X-Override-Notification: https://your-backend.com/webhook
```
This overrides the dashboard-configured notification URL per-transaction.

### Response Fields

| Field | Type | Description |
|---|---|---|
| `status_code` | string | `"201"` = created successfully |
| `transaction_id` | string | Midtrans internal ID (use for status checks) |
| `order_id` | string | Your order ID |
| `gross_amount` | string | Amount as string with `.00` suffix |
| `transaction_status` | string | `"pending"` on creation |
| `fraud_status` | string | `"accept"` on creation |
| `acquirer` | string | `"gopay"` or `"airpay shopee"` |
| `actions` | array | Contains `generate-qr-code` URL |
| `qr_string` | string | Raw QRIS data string (may not be present on older API) |

### QR Code URL

The `actions[0].url` returns a PNG image of the QRIS code. Hotlink it:
```html
<img src="https://api.sandbox.midtrans.com/v2/qris/{transaction_id}/qr-code" />
```
No additional auth needed — the URL is pre-authenticated.

## Notifications

### HTTP POST Webhook

Sent to the URL configured in:
1. `X-Override-Notification` header (per-transaction, POS use case)
2. Dashboard > Settings > Payment Notification URL (global)

### Notification Body (QRIS settlement)

```json
{
  "transaction_type": "on-us",
  "transaction_time": "2021-06-23 15:45:42",
  "transaction_status": "settlement",
  "transaction_id": "1015a919-b03f-450a-bc85-b38202a79a96",
  "status_message": "midtrans payment notification",
  "status_code": "200",
  "signature_key": "5d40504728eb96686bd5926299768a6496547f70dbd1e19d583ef4e780fe9dd5c38d0db45ec0f06dafa5c56caa6cf8358ead1523882b5fb3e102c52345d41850",
  "settlement_time": "2021-06-23 15:46:00",
  "payment_type": "qris",
  "order_id": "order102",
  "merchant_id": "G490526303",
  "issuer": "gopay",
  "gross_amount": "789000.00",
  "fraud_status": "accept",
  "currency": "IDR",
  "acquirer": "gopay",
  "shopeepay_reference_number": "144854469038383602",
  "reference_id": "QR-ZbbffKucJPEksDmXMFChZa"
}
```

### Signature Verification

```
expected = SHA512(order_id + status_code + gross_amount + server_key)
if (expected !== signature_key) → discard (not authentic)
```

### Status Cycle

```
pending → settlement (paid, success)
pending → expire (unpaid, QR timed out)
settlement → refund (if refunded)
```

### Pending Notification

When transaction is first created:
```json
{
  "transaction_time": "2020-09-29 11:18:06",
  "transaction_status": "pending",
  "transaction_id": "ce0a3584-5a0c-4049-ad88-5590a96be4fe",
  "status_message": "midtrans payment notification",
  "status_code": "201",
  "signature_key": "b1798748303cf0817733c1e312d630793b84d8125a96af0cb7251f8266d5c525...",
  "payment_type": "qris",
  "order_id": "order03",
  "merchant_id": "M099098",
  "gross_amount": "275000.00",
  "fraud_status": "accept",
  "currency": "IDR",
  "acquirer": "gopay"
}
```

### Expire Notification

```json
{
  "transaction_time": "2020-09-29 11:31:39",
  "transaction_status": "expire",
  "transaction_id": "9728e0fd-a49c-4c25-8c88-404ef1c45e0e",
  "status_message": "midtrans payment notification",
  "status_code": "202",
  "signature_key": "4580d8fc6c4a8dca3319efc1f629b8b33e923ec62b2e6ad7254ed6230ef0e579...",
  "payment_type": "qris",
  "order_id": "order03",
  "merchant_id": "M099098",
  "gross_amount": "275000.00",
  "fraud_status": "accept",
  "currency": "IDR",
  "acquirer": "gopay"
}
```

## QRIS Refund Limitations

Per Midtrans docs:
- GoPay: refund full amount only, within 24 hours of payment completion
- ShopeePay (AirPay): refund full amount & after 24 hours only
- Partial refunds: currently limited/varies by acquirer

## Testing on Sandbox

- Sandbox endpoint: `https://api.sandbox.midtrans.com/v2/charge`
- Use sandbox Server Key from dashboard
- No real payment occurs — use test QR codes
- Sandbox webhooks still fire to your configured notification URL

## Activation Flow

1. Register at https://dashboard.midtrans.com/register
2. Activate GoPay payment method (prerequisite)
3. Activate QRIS — automatic for existing GoPay merchants
4. For Static QRIS: additional onboarding, ~1 working day

## QRIS Transaction Fee

~0.7% - 1% per transaction (Midtrans cut). Varies by agreement. Check: https://docs.midtrans.com/docs/what-is-the-applicable-transaction-fee-for-qris

## Apps That Can Pay QRIS

Any QRIS-compatible app: GoPay, ShopeePay, OVO, Dana, LinkAja, and mobile banking apps (BCA, Mandiri, BNI, BRI, CIMB, Sinarmas, Maybank, etc.) — all scan the same QR code.

## Key Pitfalls (from real implementation)

1. **`gross_amount` is string**: Response returns `"275000.00"` not `275000`. Parse before math.
2. **`qr_string` field optional**: Added in later API version. Always check presence; fallback to `actions[0].url`.
3. **Webhook not guaranteed**: Always implement a GET status fallback. Midtrans recommends relying on webhook first, polling as backup.
4. **Do NOT deliver goods on `pending`**: Even if customer shows "success" screen on their app — wait for `settlement` webhook.
5. **Signature verification is mandatory**: Always check `signature_key` before updating order status.
6. **Base64 encoding for auth**: `base64(server_key + ":")` — note the trailing colon, no password field.
