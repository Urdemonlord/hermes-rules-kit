# Minting a dynamic QRIS payload from a static one

The dynamic QR is **local TLV surgery**. You already hold a valid static payload
(NMID + merchant name, printed on the card). Three edits turn it into one a wallet
scans and pre-fills.

The separate, unsolved problem is the *notification*: a QR emits nothing. Decide
that independently.

## Algorithm

A QRIS payload is a flat sequence of `<2-digit tag><2-digit length><value>`, lengths
counted in **bytes** not characters (a merchant name with non-ASCII breaks a
char-based parser), terminated by `6304` + 4 hex chars of CRC16-CCITT.

```js
function crc16ccitt(s) {                       // poly 0x1021, init 0xFFFF
  let crc = 0xFFFF;
  for (let i = 0; i < s.length; i++) {
    crc ^= s.charCodeAt(i) << 8;
    for (let j = 0; j < 8; j++)
      crc = crc & 0x8000 ? (crc << 1) ^ 0x1021 : crc << 1;
  }
  return crc.toString(16).toUpperCase().padStart(4, '0');
}

function toDynamic(staticPayload, finalAmount) {
  if (!validChecksum(staticPayload)) throw new Error('source CRC invalid'); // see below
  // 1. strip existing CRC, 2. parse TLV, 3. 01: 11 -> 12, 4. tag 54 = finalAmount,
  // 5. re-serialize, 6. recompute CRC over body + "6304"
}
```

Node/TS has no stdlib CRC16 and adding a dependency for 15 lines is the wrong trade —
the loop above is the whole thing.

### Validate the source CRC before emitting

Most reimplementations do `payload.indexOf('6304')` then append a fresh checksum,
with no check that the *input* was valid. A one-byte corrupt `QRIS_STATIC` then gets
re-emitted as a perfectly valid-looking QR pointing payment at someone else's
merchant account. The check is three lines and it is the difference between a typo
and a misdirected payment.

Same reasoning as rejecting on a missing merchant credential: refuse loudly, never
synthesize something plausible.

### Tag-54 insert position

Emit tags in ascending numeric order, CRC last. `54` goes after `53`/before `58`. If
the source has no `54`, insert it there rather than appending before the CRC.

## Verify by decoding, not by reading

Do not assert "the payload looks right". Decode the generated image and assert the
amount tag round-trips:

```bash
pip install zxing-cpp pillow
python3 -c "
import zxingcpp; from PIL import Image
r = zxingcpp.read_barcodes(Image.open('qr.png').convert('RGB'))
print(r[0].text if r else 'NO QR')"
```

Decode the merchant's *existing* static QR too — that is how you confirm `01`=`11`,
absent `54`/`62`, and get ground truth for the NMID instead of trusting the UI text.

## What still needs a PJP / portal: the notification

A generated QR has no callback. Automatic confirmation needs a transaction feed,
which comes from exactly three places:

| Source | Gives you | Cost |
|--------|----------|------|
| PJP official API (Midtrans/Xendit/GoBiz) | webhook carrying `order_id` → deterministic match | signup, server key, MDR |
| Merchant-console poller (unofficial) | amount + timestamp, match by amount | account-suspension risk per ToS |
| Human (screenshot to admin chat) | nothing automatic | the current state |

Only the first carries `order_id`. Without it you must match by amount, which forces
a **unique-amount offset** (see `payment-signal-matching.md`) or accepts ambiguity.

Never conflate "I can build the QR" with "I know when it was paid". State both.

## Unique amount without a PJP

Local dynamic QR + amount offset = working auto-match, no PJP. Order Rp 25.000 →
tag 54 = 25.100. Rules that must hold together:

- **Check uniqueness on the final amount, not the offset.** `3500+1` and `3499+2`
  both settle at `3501`; scoping per base amount is not enough.
- **Store the offset on the order, never re-allocate at verify time.** Re-allocating
  reshuffles every other order when one shifts.
- **One transaction settles at most one order** — a consumed-set keyed by tx id.
- **Exhausted pool = error, never reuse.** Otherwise a collision credits the wrong
  customer, which is worse than a failed order.
- **Persist claims across restart.** An in-memory claim set means a restart re-opens
  already-paid orders for double-credit; this is the single most expensive bug in
  this flow and it is invisible until you restart.

## Polling belongs server-side

If the browser polls for payment status, closing the tab loses the order. Move the
poll into a `setInterval` worker that reconciles, marks paid, and fans out — then
close the tab, the order still settles.

## Audit checklist for any third-party gateway repo

Clone before recommending. `grep -rniE 'webhook|callback_url' --include='*.go'`
returning zero means the fan-out is not in it, whatever the README claims.

- `grep -c webhook server.js` — no webhook means "webhook otomatis" is unimplemented.
- In-memory `Map` for orders/claims instead of a DB — restart loses everything.
- Called-but-undefined helper (`autoLoginGojek()` present, no declaration) — the
  branch dies with `ReferenceError` at request time, not at boot.
- No `.dockerignore` while the Dockerfile does `COPY . .` — `.env` and session files
  bake into image layers and survive every `docker rmi`.
- `User-Agent` used as a session cache key — same UA shares one merchant session.
- Payment QR rendered by a third-party image API — the payload, including the
  merchant NMID, is sent to that third party. Render locally.
- Browser-side polling; API key accepted as a query param (leaks into access logs).
- An obfuscated multi-hundred-KB auth module you cannot read: you cannot prove it
  does not exfiltrate the merchant credential, and you are shipping that merchant's
  token through unauditable code. Say so plainly rather than shipping it silently.