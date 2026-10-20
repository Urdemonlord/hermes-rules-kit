# Matching a bank / QRIS payment notification to an order

Use when the server must decide "this incoming payment belongs to that order" — the
core of any QRIS auto-detection feature. This is the single most expensive place to
be wrong: a wrong match marks an unpaid order as paid and the shop loses money.

## The constraint that shapes everything

A bank notification says only:

```
QRIS Rp50.000 diterima
```

No order number. No reference to your database. If two orders are waiting at exactly
Rp50.000, the notification cannot be attributed — and guessing means marking the
wrong one paid.

## Rule 1 — keep the matcher pure

`matchSignal(signal, candidates, limits)` takes every input as an argument: no
database, no `Date.now()`, no network. Return a discriminated union so each outcome
is explicit and auditable:

```ts
export type MatchResult =
  | { outcome: "matched"; saleId: string }
  | { outcome: "no_candidate" }
  | { outcome: "ambiguous"; candidateIds: readonly string[] }
  | { outcome: "too_old"; ageMs: number }
  | { outcome: "too_early"; skewMs: number }
  | { outcome: "amount_mismatch" };
```

A matcher tangled with Prisma queries cannot be tested, and it is the code that most
needs testing.

## Rule 2 — allocate a UNIQUE amount, and only ever round up

Give each pending order a distinct amount so a notification can only mean one order.
When the base amount is taken, add a few rupiah:

```ts
export function allocateUniqueAmount(baseAmount: number, isTaken: (n: number) => boolean) {
  for (let offset = 0; offset <= MAX_OFFSET_STEPS; offset += 1) {
    const candidate = baseAmount + offset;
    if (!isTaken(candidate)) return { amount: candidate, offset, unique: true };
  }
  return { amount: baseAmount, offset: 0, unique: false };
}
```

- **Round UP, never down.** Down can make the bill smaller than the goods.
- The buyer pays Rp50.003 instead of Rp50.000 — the notification then names exactly
  one order.
- **Enforce it in the database, not only in code.** A nullable column holding the
  amount while `status = 'pending'` and `NULL` once settled, unique **per merchant**:

  ```prisma
  /// Non-null while pending, NULL after paid/cancelled/expired.
  amountLock BigInt? @map("amount_lock")

  @@unique([merchantId, amountLock])
  ```

  **Scope the uniqueness to the merchant — never make `amountLock` unique on its
  own.** A global unique means one shop's pending Rp 50.000 rejects a *different*
  shop's Rp 50.000 order with a conflict error: shops block each other for no
  legitimate reason, and it gets worse as more shops sign up. The guarantee actually
  needed is narrower — within ONE merchant, at most one pending order per amount —
  and the DB still holds it even if two requests race past the application check.
  This defect is invisible to code review and to unit tests; it surfaces only when an
  integration test lets two merchants order the same amount.
- **Release the lock when the order expires.** A unique index cannot carry a
  `WHERE status = 'pending'` predicate, so a pending row whose key is still set keeps
  blocking that amount forever once the buyer walks away. Clear `amountLock` during
  the expiry sweep and filter the taken-amount query by `expiresAt > now`, or a busy
  shop slowly runs out of usable amounts.

## Rule 3 — refuse ambiguity, do not resolve it

When more than one candidate matches, return `ambiguous` and **reject the signal**.
The cashier falls back to manual confirmation.

This looks wasteful and is deliberate: refusing a legitimate signal costs a manual
confirmation; matching the wrong order costs the shop the order's value. State that
trade-off in the code comment so nobody "optimises" the ambiguity check away.

## Rule 4 — bound the time window in both directions

```ts
const ageMs = signal.deviceTimestampMs - candidate.createdAtMs;
if (ageMs > limits.maxAgeMs) return "too_old";        // stale notification, or replay
if (ageMs < -limits.clockSkewMs) return "too_early"; // clock skew on the device
```

- A **stale** notification must never settle a newer order.
- A small negative age is normal — the phone's clock drifts from the server's. Allow
  a skew allowance (a couple of minutes), do not require `ageMs >= 0`.

## Rule 5 — a replay key, scoped to the merchant

If the notification carries a bank reference (RRN/STAN), lock on it with a UNIQUE
column so one notification can never settle two orders:

```ts
export function buildReplayKey(merchantId: string, bankRef: string | null | undefined) {
  const ref = (bankRef ?? "").trim();
  if (ref === "") return null;   // NULL when absent — UNIQUE ignores NULLs
  return `${merchantId}:${ref}`;
}
```

**Always include the merchant id.** Banks reuse reference numbers across customers;
without the scope, one shop's signal blocks an unrelated shop's legitimate one.

## Rule 6 — the client reports, the server decides

The device sends **numbers and references only**:

```
{ sale_id, amount, package_name, bank_ref, device_timestamp }
```

- Never the raw notification text. Raw text can carry the sender's name, account
  number, and balance — a real finding in a competitor audit.
- The device never decides "paid". It reports "money arrived"; the server matches,
  and only the server flips the status.
- Return `matched` and `status` as **separate** fields: a signal can be accepted
  (HTTP 200) yet not matched. The UI moves to paid only when `matched === true`.

## Rule 7 — keep one indistinguishable rejection

Do not distinguish "no order with that amount" from "order exists but already
settled". Return one outcome and one message, with the real reason only in the audit
log. Otherwise the endpoint becomes an oracle for probing order state.

## What this does NOT prove

A green matcher test suite proves the pure logic. It does not prove the bank's
notification format is parsed correctly on a real device, nor that the amounts your
server allocates are the amounts actually billed. Those need a device run against a
real QRIS — say so rather than implying the feature is verified.
