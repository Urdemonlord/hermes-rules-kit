# Diagnosing QRIS Static vs Dynamic From an Actual Payload

Load this when the user shows a QR image and asks "is this static or dynamic?", "can this become dynamic?", or "why do I have to type the amount". The answer must come from decoding THEIR payload, not from the printed label.

## 1. Decode the payload — do not infer from the card art

A printable QRIS card never states static or dynamic in words. Decode the image:

```
pip install zxing-cpp pillow
python3 -c "
import zxingcpp
from PIL import Image
r = zxingcpp.read_barcodes(Image.open('<qr.png>').convert('RGB'))
print(repr(r[0].text) if r else 'NO QR FOUND')
"
```

`zxing-cpp` is a single wheel with no system deps; prefer it over `pyzbar` (needs libzbar shared library) or `opencv` (heavy). In a venv, `pip install --user` fails — install into the active venv.

## 2. Read three tags, in this order

| Tag | Meaning | Static | Dynamic |
|---|---|---|---|
| `01` + `11` | Point of Initiation Method | `11` = static | `12` = dynamic |
| `54` | Transaction amount | ABSENT | present, e.g. `540550000` |
| `62` | Bill number / additional data | ABSENT | present, carries order ref |
| `63` + 4 hex | CRC16-CCITT | present | present |

**Verdict rule:** `01 11` with no `54` and no `62` is static and cannot carry an order reference, no matter what the checkout page displays. The amount a customer "types in" is entered by the customer in their wallet — the QR never held it.

Also record `26` (merchant account info, reveals acquirer), `52` (MCC), `58` (`ID`), `59` (merchant name), `60` (city), and the `29`/`30` /nested `62`-style acquirer-specific block so you can tell a DANA-provisioned QR from a bank-provisioned one.

## 3. The three answers, and when each is the honest one

- **"Can static become dynamic?"** No, not in code. A static QR's defining property is that one payload serves every transaction forever; that is why it can be printed. Amount and reference fields exist only in a dynamic payload. Dynamic issuance is a licensed-PSP capability (Midtrans/Xendit/DOKU charge API, or the EMVCo rewrite in `gobiz-gopay-merchant-api.md`), never a self-minted payload.
- **"Why does it feel like dynamic?"** Static QR plus an amount the customer types is functionally the same experience as dynamic at the moment of scanning. Conflating the two is the single most common misunderstanding; separate "does the QR contain the amount" from "does the customer have to type it".
- **"Will a webhook match my order?"** Only if the notification carries an order reference. With static QR the provider sends amount plus merchant/NMID and nothing else, so reconciliation collapses to amount matching.

## 4. Reconciliation on static QR — state the ceiling honestly

Match-by-amount is a real design, not a workaround, but two customers paying the same amount inside one window are indistinguishable. What actually helps:

- per-order min/max amount window (accept `24.500`-`25.500` for an order of `25.000`)
- a short expiry (15 min) so the ambiguity window closes
- unique suffix in the low digits where the acquirer supports it (that is what dynamic does for you)

Acknowledge the residual collision case as a property of the payment rail, not a bug to fix in code.

## 5. Pitfalls

- **A pipe-delimited string is not EMVCo.** `00|01|NMID|amount|ref` parses in no wallet. Before recommending a "generator", check its output actually starts with `000201` and has a valid `6304` CRC; anything using `|` as a separator is a stub that will be rejected on scan.
- **Check whether the QR component is even wired.** Grep for imports of the generator route/component and for the QR-rendering library. A generator endpoint nothing calls, with the NMID hardcoded inline, is dead code from a previous attempt - the live path is probably a static image served from `public/`.
- **Multiple NMIDs in one repo** (config file, component constant, generator route) usually means copy-paste drift. Diff them and name which one the live path uses before advising anything.
- **Static QRIS has no built-in webhook.** A static NMID on its own emits nothing to your server; notification requires the PSP side configured for it. Do not promise automatic webhook on a static QR without checking that setup.
- **MCC 5993 (gambling)** appears on gaming merchant QRIS and may be queried during PSP KYC; anticipate it rather than being surprised.

## 6. Report shape the user expects

Answer in this order: the decoded payload (truncated, exact), the verdict with the deciding tag, the one sentence on why the lived experience still felt automatic, and the concrete next step (which PSP credential unlocks dynamic). Do not open with theory; open with the bytes you read.

## 7. Auditing a self-hosted QRIS/GoPay gateway the user is considering

Self-hosted gateways do the EMVCo rewrite locally (see `gobiz-gopay-merchant-api.md`) and detect payment by polling the merchant portal, because GoBiz has no push webhook. Auditing one before the user deploys it, check in this order:

1. **Is the EMVCo rewrite real?** Look for TLV parse → tag `01` `11`→`12` → insert `54` → recompute CRC16. A pipe-delimited string or a static image served from `public/` is a stub; see section 5.
2. **Where does payment detection come from?** Browser-driven polling (`setInterval` in inline HTML hitting a status endpoint) means the order is never confirmed if the customer closes the tab. That is a correctness defect, not a UX preference - it is the thing that must become a server-side worker.
3. **Is there any webhook at all?** `grep -i webhook` over the server file. Zero hits means the user's "webhook otomatis" requirement is entirely unimplemented, and "multi webhook" needs the fan-out written from scratch.
4. **Unique suffix?** If tag `54` is written verbatim with no low-digit suffix, two customers paying the same amount in one window collide - report the collision, do not let the in-memory claimed-transaction map disguise it.
5. **State durability.** Order store and claim map as bare `Map` = in-memory only. Restart loses pending orders AND releases claims, so an already-paid transaction can be claimed twice.
6. **Secret handling:** missing `.dockerignore` next to `COPY . .` bakes `.env` and session files into image layers irrecoverably; `javascript-obfuscator` on the session module means the refresh-token path cannot be audited - say that plainly rather than implying it was checked.
7. **Auth shape:** API key accepted via `?api_key=` query leaks into access logs and referrers; `cors()` wildcard, no helmet, no rate limit, and a public unauthenticated status endpoint that proxies to the upstream merchant API are each a finding.
8. **Undefined-call check:** grep each locally-named function for a definition (`function <name>` / `const <name> =`). A helper called on an error-recovery branch but never defined is a latent `ReferenceError` on that branch - report it as a concrete bug with the line number.
9. **State, not REST endpoints:** `getValidHeaders(req.headers['user-agent'])` keys a cached session on User-Agent, so concurrent callers sharing a UA share a session and can each trigger a refresh.

Report which of the user's stated requirements the repo actually satisfies (count them), then the patch order: cheapest secret-containment fix first, then the durability bug, then the amount-collision fix, then the worker + fan-out. Offer the licensed-PSP route as the alternative that removes matching entirely, with the cost (onboarding, MDR) attached.