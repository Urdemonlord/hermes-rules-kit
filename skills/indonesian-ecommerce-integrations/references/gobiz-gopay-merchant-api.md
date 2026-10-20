# GoBiz (GoPay Merchant) API — Reverse-Engineered Reference

Source: open-source `gobiz-pay` v1.0.1 (MIT License, github.com/ItsAzni/gobiz-pay).

## Base URLs

| Service | URL |
|---|---|
| Auth & User | `https://api.gobiz.co.id` |
| Transaction Analytics | `https://api.gojekapi.com/merchant-analytics/v2/merchants/transactions` |
| Transaction Journal | `https://api.gobiz.co.id/journals/search` |

## Auth Headers (Required on Every Request)

```
accept: application/json, text/plain, */*
accept-language: id
authentication-type: go-id
authorization: Bearer <access_token>
gojek-country-code: ID
gojek-timezone: Asia/Jakarta
x-appid: go-biz-web-dashboard
x-appversion: platform-v3.108.1-66161c15
x-deviceos: Web
x-phonemake: Linux 64-bit
x-phonemodel: Chrome 203.0.113.10 on Linux 64-bit
x-platform: Web
x-uniqueid: <random UUID, persist across sessions>
x-user-locale: en-US
x-user-type: merchant
referrer: https://portal.gofoodmerchant.co.id/
origin: https://portal.gofoodmerchant.co.id
```

The `x-uniqueid` must be stable per client (stored in cache file). It's sent with every request.

## Auth Flow

### 1. Password Login

```
POST /goid/login/request
Body: {
  "email": "user@example.com",
  "login_type": "password",
  "client_id": "go-biz-web-new"
}

POST /goid/token
Body: {
  "client_id": "go-biz-web-new",
  "grant_type": "password",
  "data": {
    "email": "user@example.com",
    "password": "password_here"
  }
}
Response: {
  "access_token": "eyJ...",
  "refresh_token": "...",
  "expires_in": 86400
}
```

### 2. OTP Login (Email)

```
POST /goid/login/request
Body: {
  "email": "user@example.com",
  "client_id": "go-biz-web-new"
}
Response: { "data": { "otp_token": "..." } }

POST /goid/token
Body: {
  "client_id": "go-biz-web-new",
  "grant_type": "otp",
  "data": {
    "otp": "123456",
    "otp_token": "..."
  }
}
```

### 3. OTP Login (Phone)

```
POST /goid/login/request
Body: {
  "phone_number": "85123456789",
  "country_code": "62",
  "client_id": "go-biz-web-new"
}
  → otp_token

POST /goid/token
Body: { "client_id": "go-biz-web-new", "grant_type": "otp", "data": { "otp": "...", "otp_token": "..." } }
```

### 4. Get Merchant Info

```
GET /v1/users/me
Response: {
  "user": {
    "merchant_id": "G490526303",
    "full_name": "Merchant Name"
  }
}
```

## Transaction History

### Analytics View (simpler)

```
GET /merchant-analytics/v2/merchants/transactions
  ?from=0
  &size=50
  &statuses=SETTLEMENT,CAPTURE,REFUND,PARTIAL_REFUND
  &payment_types=QRIS,GOPAY,OFFLINE_CREDIT_CARD,OFFLINE_DEBIT_CARD,CREDIT_CARD
  &start_time=2026-07-17T00:00:00.000Z
  &end_time=2026-07-24T00:00:00.000Z
  &merchant_ids=G490526303
```

### Journal View (detailed, Elasticsearch query)

```
POST /journals/search
Body: {
  "from": 0,
  "size": 50,
  "sort": { "time": { "order": "desc" } },
  "included_categories": { "incoming": ["transaction_share", "action"] },
  "query": [{
    "op": "and",
    "clauses": [
      { "op": "not", "clauses": [{
        "op": "or", "clauses": [
          { "field": "metadata.source", "op": "in", "value": ["GOSAVE_ONLINE", "GoSave", "GODEALS_ONLINE"] },
          { "field": "metadata.gopay.source", "op": "in", "value": ["GOSAVE_ONLINE", "GoSave", "GODEALS_ONLINE"] }
        ]
      }]},
      { "field": "metadata.transaction.status", "op": "in", "value": ["settlement", "capture", "refund", "partial_refund"] },
      { "field": "metadata.transaction.payment_type", "op": "in", "value": ["qris", "gopay", "offline_credit_card", "offline_debit_card", "credit_card"] },
      { "field": "metadata.transaction.transaction_time", "op": "gte", "value": "..." },
      { "field": "metadata.transaction.transaction_time", "op": "lte", "value": "..." },
      { "field": "metadata.transaction.merchant_id", "op": "equal", "value": "G490526303" }
    ]
  }]
}
```

## QRIS Dynamic Generation — EMVCo String Manipulation

### QRIS EMVCo Format (simplified)

```
0002 01 01 02 11  ...  010211 = static, 010212 = dynamic
26   <merchant account info>  (GoPay: "COM.GO-JEK.WWW...")
52   <merchant category code>
53   <transaction currency>
54   <transaction amount>      ← FIELD INSERTED FOR DYNAMIC
58   <country code>            (always "ID" = 5802ID)
59   <merchant name>
60   <merchant city>
61   <postal code>
62   <additional data>
63   <CRC>                     (6304 + 4 hex digits)
```

### Algorithm

1. Strip existing CRC16 (last 4 chars after `6304` marker)
2. Replace `010211` (static) with `010212` (dynamic) in header
3. Split string at `5802ID` → `before` + `after`
4. Build amount field: `"54" + length2digits(amount_string) + amount_string`
5. Example: amount=50000 → `"54" + "05" + "50000"` = `"540550000"`
6. Reassemble: `before + nominalField + "5802ID" + after + "6304"`
7. Calculate CRC16-CCITT over the reassembled string
8. Append CRC16 as 4 uppercase hex digits

### CRC16 Implementation

```typescript
import crc from "crc";
function convertCRC16(str: string): string {
  const hex = crc.crc16ccitt(Buffer.from(str, "utf8")).toString(16).toUpperCase();
  return ("0000" + hex).slice(-4);
}
```

### Example

Static QRIS (244 chars):
```
00020101021126570014COM.GO-JEK.WWW011893600914349052630340210G4905263030303UKE51440014ID.CO.QRIS.WWW0215AID0607336128660303UKE5204341453033605802ID5904Test6007BANDUNG610540284540978900062475036c032f87c-f773-4619-aefa-675e1f06f9210703A016304A623
```

Dynamic QRIS for Rp 50.000 (253 chars, +9 from field 54 insertion):
```
00020101021226570014COM.GO-JEK.WWW011893600914349052630340210G4905263030303UKE51440014ID.CO.QRIS.WWW0215AID0607336128660303UKE5204341453033605405500005802ID5904Test6007BANDUNG610540284540978900062475036c032f87c-f773-4619-aefa-675e1f06f9210703A01630420ED
```

Differences:
- `010211` → `010212`
- `540550000` inserted before `5802ID` (field 54 = amount 50000)
- CRC16 changed from `A623` to `20ED`

### Verifying correctness

1. Flag byte 6-7 must be `010212` (dynamic)
2. Field `54` must be present with correct amount
3. Length increases by `2 + amount_digit_count + amount_digit_count_chars` (9 for Rp 50.000)
4. QR code image must be scannable by Gojek/ShopeePay apps

## Transaction Monitoring (Polling)

GoBiz has **no push webhook**. Use polling:

```typescript
class GoPayWatcher {
  async waitForPayment(expectedAmount: number, opts: {
    timeout?: number;    // default 300000 (5 min)
    tolerance?: number;  // default 0 (exact match)
  }): Promise<PaymentEvent> {
    const start = Date.now();
    while (Date.now() - start < (opts.timeout || 300000)) {
      const history = await merchant.getHistory({ days: 1, size: 10 });
      for (const tx of history.data?.histories || []) {
        const txAmount = parseFloat(tx.amount.displayed_text.replace(/[^0-9]/g, ''));
        if (Math.abs(txAmount - expectedAmount) <= (opts.tolerance || 0)) {
          return { amount: txAmount, txId: tx.raw.transaction_id, entry: tx };
        }
      }
      await sleep(3000); // poll interval
    }
    throw new Error('Timeout waiting for payment');
  }
}
```

## Cache/Session Management

Credentials cached in `.gobiz-cache.json` (permissions 0600):
```json
{
  "gopay_token": "eyJ...",
  "gopay_merchant_id": "G490526303",
  "unique_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Token reuse: on 401, clear cache, re-login, retry. The library handles this automatically.

## Pitfalls

1. **"No API call" applies to QR GENERATION only.** Making the QR is free because it is a local EMVCo rewrite; knowing it was PAID still costs API calls, because GoBiz has no push webhook and no order reference in the notification. Split the user's ask into three separate features and answer each: (1) QR with amount embedded = the rewrite above, free; (2) automatic detection = polling the transactions endpoint, which needs a SERVER-side worker, never a browser timer; (3) webhook fan-out to N subscribers = code you write. Only (1) comes free, so a repo shipping only (1) satisfies a third of what "panel + webhook otomatis" implies.

2. **The webhook fan-out rules, when you do write it:** verify an HMAC/HMAC-SHA256 per-subscriber secret against the RAW body; make the handler idempotent on the provider's delivery/event id; **ACK the provider before fan-out** — a slow subscriber otherwise triggers provider retries that double-deliver to customers; persist pending sends in a real queue, not an in-memory array.

3. **No unique suffix means collision.** Tag `54` written verbatim (no base + random 1-999 in the low digits) leaves two customers paying the same amount inside one window indistinguishable. An in-memory claimed-transaction map hides that only until the process restarts, at which point an already-paid transaction can be claimed twice.

4. **Token expiry** — access tokens expire. Always wrap API calls with retry-on-401 logic.
5. **ESM-only** — gobiz-pay is `"type": "module"`. Use `.mjs` extension or `"type": "module"` in package.json. `tsx` may fail on import; use `node` directly.
6. **QRIS static string must be valid** — the `buildDynamicQris` function assumes `5802ID` separator exists. An invalid QRIS string will throw `"Invalid QRIS format"`.
7. **Field 54 insertion position** — always after merchant info, before country code. The `5802ID` split ensures this.
8. **Amount field length encoding** — `"54" + 2_digit_length + amount`. For Rp 50.000: `"05"` (5 digits) + `"50000"` = `"540550000"`. For Rp 1.500: `"04"` (4 digits) + `"1500"` = `"54041500"`.
9. **CRC16 must be recalculated** after every string change — or QR will fail validation on scan.
10. **Not all QR libraries handle EMVCo** — use `qrcode` npm package (works). The `generateQrisImage` from gobiz-pay uses it internally.
