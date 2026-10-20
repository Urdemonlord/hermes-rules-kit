# Verifying a payment SDK's runtime contract before building on it

Docs describe intent. Source describes behaviour. For a money path the gap between
them is where the expensive bugs live.

## Order of operations

1. **Get the package.** JSR-hosted packages are often absent from npm and blocked by
   CDN WAF on a datacenter IP; if the registry 403/404s, `git clone` the GitHub repo
   and install from the local path. `file:` installs run the package's `prepare`
   script, so build it (`npx tsup`) in the source dir *before* depending on it.
2. **Read the adapter's constructor and the feed method.** Not the README.
3. **List real exports** and confirm every symbol the wrapper imports:
   ```bash
   node -e "import('<pkg>').then(m=>console.log(Object.keys(m).length, Object.keys(m)))"
   ```
4. **Diff your wrapper against source, line by line.** Each mismatch is a bug with a
   silent symptom.
5. **Probe the pure function** against a real payload you have on hand.

## What to check for in each method

- **normalisation** — does it scale amounts, and by which factor? (GoBiz:
  `rawGross >= 100000 ? round(rawGross/100) : rawGross`, so it returns rupiah.)
- **casing** — `status: 'SETTLEMENT'` uppercased from the wire, or lowercase? A
  case-sensitive set membership check silently rejects every transaction.
- **method names** — `getTransactions` vs `fetchTransactions` vs `listTransactions`.
- **lazy auth** — does the client log in on first call, or does it need an explicit
  login before the feed works?
- **forced options** — what does `force` defeat, and is defeating it a rate-limit risk?
- **built-in background timers** — `startPoller` / `watch` / `subscribe` helpers.
  Running one while also running your own loop = two pollers, one credential.

## Convenience functions hide unreachability

A high-level helper may hardcode a behaviour with no opt-out. The generic name
(`createDynamicPayment`) reads like it accepts your exact requirements; the source
shows an unconditional branch. Always scan for a lower-level primitive exported by
the same package — the same library frequently ships both, and the low-level one is
what makes the requirement reachable.

## An empty array from a feed method is not "no payments"

`[]` from `getTransactions()` means one of four completely different things, and
nothing in the return value distinguishes them. Treat it as unverified and go
looking, in this order:

1. **The request window is narrower than you think.** Many clients default to the
   last 24 hours with no way to widen it from the options object you passed. A
   settlement from four days ago is simply absent, and the API answers
   `total: 0, transactions: []` — a success shape, not an error. Pass an explicit
   `from`/`to` covering days, not hours.
2. **A required scoping parameter silently omitted.** A client that resolves the
   merchant id from a profile endpoint can fail that lookup (see the 404 note in
   `payment-portal-auth.md`) and then query without the id, getting every
   merchant's-zero rows back. Pass the id explicitly if the constructor accepts
   it — do not rely on the profile lookup succeeding.
3. **Envelope shape mismatch.** The wire returns `{from, size, total,
   transactions: []}`. A client reading `res.data || res.transactions` finds the
   empty array and returns it. When you suspect this, intercept `fetch` and print
   the raw body plus the exact URL — that single instrument ends the guessing:
   ```js
   const orig = globalThis.fetch
   globalThis.fetch = async (u, o) => {
     const r = await orig(u, o)
     console.log('>>', String(u).slice(0, 160))
     console.log('<<', r.status, (await r.clone().text()).slice(0, 300))
     return r
   }
   ```
4. **Auth is genuinely dead.** Establish this only with the mangled-token control
   (401 vs 404), never from `[]`.

Fix the first, then re-run before believing the fourth. Reporting "the merchant has
no transactions" when the answer was a 24-hour window buries the real bug, and
the panel then sits quietly showing every order pending forever.

## Proof, not assertion: emit an amount-bearing payload and read it back

Emit a payload with the primitive, render it to a PNG, and **decode the PNG back**
with a barcode reader. Assert the amount tag round-trips at its declared length,
the CRC self-validates, and the static marker flipped. Handing the buyer a QR to
scan in a real wallet is the only test that proves the app accepts it; everything
before that proves your own code is self-consistent. A non-greedy tag parse:

```js
const seg = out.slice(out.indexOf('54'), out.indexOf('5802ID')); // 540525000
const len = Number(seg.slice(2, 4));                              // 5
const value = seg.slice(4, 4 + len);                              // 25000
```

`/54\d{2}\d+/` is greedy and swallows the following tag — it will report a wrong
amount and a wrong length while looking like a pass.