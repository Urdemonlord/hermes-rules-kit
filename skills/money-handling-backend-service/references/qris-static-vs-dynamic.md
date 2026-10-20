# QRIS static vs dynamic: what the code can and cannot do

Read this before touching any QRIS code in an existing project, or answering
"can we make this dynamic?" — the honest answer is usually that the repo is not where
the change happens.

## The payload is EMVCo TLV, not a template string

A QRIS payload is a binary tag/length/value structure. The tags that matter:

| Tag | Meaning | Static | Dynamic |
|-----|---------|--------|---------|
| `00` | Payload Format Indicator | `01` | `01` |
| `01` | Point of Initiation Method | `11` | `12` |
| `26` | Merchant Account Template (contains NMID) | yes | yes |
| `52`–`54` | MCC / merchant name / city | yes | yes |
| `58` | Country ID | `ID` | `ID` |
| `62` | Additional data — **this is where `order_id` lives** | absent | present |
| `53`/`54` | Transaction amount | absent | present |
| `58`/`59` | Tip / merchant name | — | — |
| CRC | checksum over the whole payload | required | required |

**Static sets `01` = `11` and omits `62` and the amount. Dynamic sets `01` = `12` and
carries both.** The amount in a dynamic payload is what makes `order_id` matching
possible; that is the whole reason for the switch, not convenience.

### The trap: a plausible-looking fake payload

Hand-built strings are the classic failure:

```ts
// WRONG — pipes are not TLV delimiters, no CRC, no `01`=12
const qrisString = `00|01|ID1024335007646|${amount}|${invoiceCode}`
```

Every wallet rejects this. It looks reasonable in review because it contains a real
NMID and the right field order. Two tells: pipe or comma delimiters, and the absence
of a `01`=dynamic marker or `62` tag.

**How to confirm you have the problem:** `grep -rn "qris" --include='*.ts'` and look
for a template literal built from an NMID and an amount. If a QR library import
(`qrcode.react`, `qrcode`) is absent from `package.json`, nobody is rendering a real
payload either — the page is showing a static image.

### Static QR still has no webhook of its own

A printed/generated static QR is only a payment instrument. Nothing about it emits a
notification. If no PJP console has a webhook URL configured against the MID/NMID,
payments succeed and no server ever hears about them. The "automatic verification" a
customer UI promises cannot exist in that state — which is why a manual confirmation
chat is the correct interim design, not a shortcut.

## Audit checklist for an existing project

Run these in order; each one is a `grep` away and each has burned an audit:

1. **Every NMID in the repo, in one list.** `grep -rnE 'ID10[0-9]{11}'` across
   source. Three different NMIDs in one repo means the merchant cannot say which
   account money is arriving in, and one of them is receiving payments while another
   is displayed to customers. Fix before shipping anything else.
2. **Which QR component is actually mounted?** Find the rendered component's callers,
   not its file. Dead code containing a fake payload reads as live logic in review.
3. **The real payment method string.** `payment_method: "qris_whatsapp"` or similar in
   the order-creation path is the ground truth for what the system supports.
4. **Is there a real payment webhook route?** Look under the webhook/API route dir.
   A `test-*` route guarded by an admin key is a manual trigger, not an inbound
   payment notification — do not report it as one.
5. **Does a unique amount get allocated per order?** See
   `references/payment-signal-matching.md`. If nothing allocates one and the flow is
   manual, that is consistent; if the UI claims automatic verification, it is a
   false promise.

## The honest answer to "bisa jadi dinamis?"

Not in your code. It requires a PJP account that issues dynamic QR (merchant
signup, server key, charge API per order), after which webhooks become possible and
deterministic. Static QR can coexist on the same merchant for walk-in / donation
traffic — so the practical plan is two modes, not a migration.

Say that, and name what is missing (the server key, or the webhook URL on the
console). Do not produce a charge-API sketch against guessed request and signature
shapes: those differ per provider and a wrong guess is a silent failure on the one
path that moves money.