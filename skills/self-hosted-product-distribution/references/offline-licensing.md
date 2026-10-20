# Offline license signing for a sold self-hosted product

Recipe behind SKILL.md rule 25. Applies whenever a product is sold per-install
and the buyer must prove entitlement **without phoning home**.

## Decide what the license is FOR before writing any code

There are only two honest options, and they need opposite code.

| Goal | Requires | Reality |
|---|---|---|
| **Enforcement** — panel stops working unpaid | Server-side check the buyer cannot edit | Only possible with a phone-home or a hardware dongle |
| **Compliance** — buyer proves it is licensed | Offline signature check | JavaScript the buyer has the source to, deletable in one line |

Offline verification is **compliance**. Anyone can delete one line in
`server.js`. Say so in the module header rather than implying protection, and
price the product on the sale, not on the check.

**The corollary that decides the wiring:** a verifier must never block a service
that holds irreplaceable state. A payments panel that refuses to boot because a
license file went missing costs more than the sale it protects. Report the state
through the health endpoint and **exclude it from the status code**. Same
precedent as rule 12 — an installer reports validation findings as warnings
rather than refusing to install.

## Key custody

- **Private key: outside the repo, mode 600.** A sibling directory the build
  script reads, never a subdirectory of the project and never a `.env` var.
- **Public key: in the shipped source tree**, next to the module that reads it,
  so it travels with the tarball automatically via the existing `src` allowlist
  entry.
- Issuer tool is **vendor-side only** and never enters the allowlist.
- On first run the issuer generates the pair if absent. Regenerating the *public*
  key invalidates every outstanding license, so treat the private key as
  unrecoverable-in-practice: back it up somewhere the buyer cannot reach.

## Canonical bytes: store the signed string verbatim

The single highest-value rule in this file.

**Sign a canonical string and store that exact string in the license file.
Verify the stored string. Never re-serialize the parsed object and never rebuild
the string at verification time.**

```
{ "data": "meowpay-license-v1\nbuyer=Toko Sederhana\nissued=2026-01-01\n...",
  "sig": "<base64>" }
```

Why it matters, concretely: a buyer who pretty-prints their `license.json`, or
runs it through any JSON formatter, or whose editor reorders keys, changes the
bytes. A verifier that does `JSON.stringify(parsed, null, 2)` or that rebuilds
`buyer=…\nissued=…` from fields now sees different bytes and rejects a genuine
license. There is no error — it just reads "unlicensed" to a paying customer.

This is the same mechanism as SKILL.md rule 10 (derive values in the fixture
rather than pasting literals) applied to the signing boundary.

## Field encoding: split on the FIRST delimiter, build without escaping

Payload lines are `key=value`. Values are free text a human types.

- Parse with `indexOf('=')` and slice both sides — splitting on every `=` silently
  corrupts a buyer name like `Warung = Sederhana`.
- Prefer **no escaping scheme at all** over half-implemented escaping. Disallow
  newlines in values; that is one validation line and it removes an entire class
  of parser-injection bugs.

## Verifier shape

`licenseState()` returns a state object and **never throws**. Missing file,
malformed JSON, non-base64 signature, unparseable key, wrong field types — every
one returns `{ valid: false, reason }` with a distinct reason string. A monitor
watching the health endpoint has to tell "not licensed yet" apart from "file
corrupted" apart from "expired, renew here".

- **Put the version check first**, before parsing fields. An old license against
  a new panel is then refused as `wrong-version` instead of being misparsed
  against a schema it predates.
- Distinguish **expired** from **tampered** — they lead to different operator
  actions, and an expired license still needs to name its buyer so the renewal
  path can find the account.
- `expires=never` needs an explicit branch in both the parse and the compare.

## Verification API

`crypto.verify(null, Buffer.from(data, 'utf8'), crypto.createPublicKey(pub),
Buffer.from(sig, 'base64'))` — Ed25519 takes a null algorithm. No dependency;
`node:crypto` covers the whole thing.

## Packaging

| File | Ships? | Why |
|---|---|---|
| `src/*.pub` | **yes** | needed to verify anything |
| `license.json` | **never** | it is *someone's* license |
| issuer tool + private key | **never** | obviously |

Add `license.json` to the build script's leak-guard list in the same change that
introduces the feature, not after a leak. A leak-guard that knows about
`.env` and `session.json` and not about the license file is a guard whose
list was written for a different product.

## Test the asymmetry, not the happy path

Spend the assertions on **never falsely rejecting a genuine license** — that is
the failure that reaches a paying customer. A forged license that slips through
costs one sale.

Must-have cases:

1. A genuine license verifies.
2. **Reformatting and reordering the JSON does not invalidate it.**
3. A field value containing the delimiter round-trips intact.
4. Edited payload → rejected. Forged signature → rejected. Both same reason.
5. Past expiry → `expired` flag set, buyer still reported, distinguishable from
   tampering.
6. Missing file, garbage file, truncated file, non-base64 signature → no throw.
7. Old format version → `wrong-version`, not a misparse.
8. The canonical-payload builder and the verifier build **byte-identical**
   strings — assert them against each other so the two cannot drift.

Red-to-green two of these: sign-and-then-re-serialize must go red on case 2, and
deleting the version gate must go red on case 7. See SKILL.md rule 25 in
`test-proof-discipline` for why an unred injection proves nothing.