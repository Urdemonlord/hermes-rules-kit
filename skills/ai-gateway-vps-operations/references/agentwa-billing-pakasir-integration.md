# AgentWA + Pakasir Billing Integration (2026-06-23)

## Pakasir API Base URL
- **Base**: `https://app.pakasir.com` (NOT `pasarintegration.com`)
- **SDK endpoint** (`pakasir-sdk/dist/index.js`): hardcoded to `https://app.pakasir.com`

## Payment Method: `'all'` Does NOT Exist
- `method: 'all'` → `{message:"metode pembayaran tidak valid"}`
- Valid methods: `qris`, `paypal`, `cimb_niaga_va`, `bni_va`, `bri_va`, `permata_va`, `maybank_va`, `sampoerna_va`, `bnc_va`, `artha_graha_va`, `atm_bersama_va`
- **`qris` works**: creates payment, returns `payment_number` (QRIS string) and `payment_url`
- Fee for qris: `amount > 105000` → `round(0.01 * amount)`, else `round(0.007 * amount + 310)`
- Minimum amount: Rp500

## Pakasir Transaction Create (direct API, no SDK)
```bash
curl -X POST "https://app.pakasir.com/api/transactioncreate/qris" \
  -H "Content-Type: application/json" \
  -d '{"project":"<slug>","api_key":"<key>","order_id":"<id>","amount":<amount>,"redirect_url":"<url>"}'
```

Response:
```json
{
  "payment": {
    "project": "agentwa",
    "order_id": "TEST-...",
    "amount": 50000,
    "total_payment": 50000,
    "fee": 660,
    "received": 49340,
    "payment_method": "qris",
    "payment_number": "00020101021226670016...",
    "expired_at": "2026-06-22T22:08:57.612760043Z"
  }
}
```

## Payment Status Values
- `pending` — order created, awaiting payment
- `completed` — payment confirmed
- `canceled` — payment cancelled/expired

## AgentWA Billing Flow
- **Plan purchase** (`/topup?plan=starter`): amount = plan price (99000/299000/799000)
- **Add-on credits** (`/topup?amount=50000`): amount = credit price (25000/50000/125000/250000)
- Webhook handler at `/api/webhooks/pakasir` updates `payments.status` on `completed/canceled/expired`

## Credits Pricing (consistent everywhere)
| Credits | Price |
|---------|-------|
| +1.000 reply | Rp 25.000 |
| +2.000 reply | Rp 50.000 |
| +5.000 reply | Rp 125.000 |
| +10.000 reply | Rp 250.000 |

**Rule**: 1.000 reply = Rp25.000 everywhere (pricing page, topup buttons, topup page).

## Bugs Fixed (2026-06-23)
1. `method: 'all'` → changed to `'qris'` (only valid method that works)
2. Pakasir instance dupe inside `createPayment()` → module-level singleton
3. Topup route hardcoded `amount=50000` → reads `body.amount`
4. Auth check `!user` (object always truthy) → `!user?.ok`
5. Frontend `data.paymentUrl` → `data.url` (SDK returns `payment_url`)
6. Price mismatch: old `+10.000 Credits = Rp200.000` → fixed to Rp250.000
7. Topup page: added plan/addon mode toggle for plan purchase vs credit topup

## Nginx Config Lock
- Deploy script was overwriting nginx `proxy_pass` to port 3001 (the auth service)
- Fix: `sudo chattr +i /etc/nginx/sites-enabled/agentwa.meowlabs.id` (immutable, survives deploy scripts)
- Verify: `lsattr /etc/nginx/sites-enabled/agentwa.meowlabs.id` should show `----i---------e`
