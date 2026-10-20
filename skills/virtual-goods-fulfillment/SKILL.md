---
name: virtual-goods-fulfillment
description: Automate in-game currency and virtual-goods delivery.
---

# Virtual Goods Fulfillment

Automating delivery of in-platform currency and items (Robux, gamepasses, gift
items, boosts, in-game services) for a top-up storefront. The engineering is
easy; the constraints are contractual and physical, and they decide the
architecture before any code does.

## Rule 0 — find the existing implementation before designing anything

The user asking "what is <delivery method X>" is frequently already running it.
Grep their own repos for the platform's API hostnames before answering:

```bash
grep -rn 'roblox.com/v\|robloxapis\|/v1/trades/send\|gifts/give' --include=*.ts --include=*.js .
find . -path ./node_modules -prune -o -name '*noblox*' -print -o -name '*fulfillment*' -print
```

A term from the market (reseller slang) usually maps onto a function they already
wrote. Answering with a generic explanation of the platform feature, while their
repo holds a working implementation, wastes the session and understates their own
state. Read their delivery path first, then explain what it does and where its
ceiling is.

## The route decision comes first — only one route automates fully

"Auto delivery" is not one feature; it is N incompatible processes that buyers
perceive as the same product. Decide the route before building:

| Route | Automates? | Limiting factor | Who controls fulfillment |
|---|---|---|---|
| Prepaid code pool (gift cards) | **Fully** | Code stock | You |
| Group / community payout | Partially | Platform waiting periods | You, queued |
| Direct transfer (peer-to-peer send) | Only up to the recipient's approval | **Recipient must accept** | The buyer |
| Account-login delivery | Fully, but rule 4 applies | Credential handling + ToS | You, at your risk |

Consequences to state up front rather than after building:

- **The code pool is the only route that delivers instantly with a predictable
  SLA.** If the requirement is "instant", that is where it is built. Claim codes
  atomically: reserve and mark sold in the same transaction, or two concurrent
  orders at peak hand out the same code.
- **Approval-required routes can never be instant by design.** The platform
  requires a human on the buyer's side. Do not let a product page promise
  otherwise.
- Do not stack routes into one "try everything" function and call it resilient.
  Each route has its own failure meaning and its own operator action.

## Rule 1 — a delivery that needs the recipient's approval is not done when the API returns 200

Sending a transfer offer is not delivering currency. The call returns success the
instant the offer exists, while the order completes only when the buyer accepts —
so a naive `success === true → fulfillment_status = 'completed'` marks every order
complete the moment it is *offered*. Symptoms: buyers who never accepted show as
fulfilled, and the reconciliation ledger disagrees with the balance.

Model it as its own state, and make the fallback explicit:

```
paid → transfer_offered → (recipient accepts) → completed
                       ↘ (fails / expires) → fallback route → pending_review
```

- Record the offered state before attempting, and never collapse `offered` into
  `completed`.
- A fallback route (a second delivery mechanism) may only run when the order is
  provably still undelivered, and it must re-check the amount against the balance
  it can actually spend.
- Both routes failing is a **`pending_review` terminal-for-now state with the real
  error preserved** — not a delete, and not a retry that nothing re-invokes.

## Rule 2 — the platform's limits are the architecture, not a footnote

Every platform caps transfer volume per account, per day and per month, and gates
eligibility on account age, verification, and — for minors — **a linked parent
account plus approval on every single transfer**. Some regions require parental
approval up to 18.

Read the current published limits before sizing anything, and quote them in the
summary: Roblox's figures as a worked example are in
`references/roblox-robux-delivery-routes.md`. The design consequences are general:

- **Scaling means more sender accounts, not a faster script.** Cost and failure
  points scale linearly with account count (each has its own session, its own
  eligibility, its own limit window).
- **Minors cannot be automated at all** where approval-per-transfer applies. That
  is a product constraint to state, not a bug to engineer around.
- **Transferred currency is usually not convertible** (not eligible for the
  platform's developer-payout program). It is spend-only, which changes what the
  product can promise.
- **A sent transfer is irreversible.** On this route an automation bug costs real
  money rather than pausing an order — which is the reason the state machine in
  Rule 1 has to be right before the loop runs unattended.

## Rule 3 — multi-account sender pools: the pattern and its ceilings

When one account's per-period limit is the cap, the industry answer is a pool of
sender accounts, each holding its own authenticated session, selected per order.

What that means in code: a `selectSender()` / `authenticate(session)` pair with a
re-auth interval and a cached current sender, plus a CSRF-token fetch immediately
before each mutating call (platforms issue it on a deliberate 403/401 response and
expect it replayed in a header).

Ceilings to name in the handover rather than discover in production:

- **Session staleness is the dominant failure.** A logged-out or invalidated
  session fails silently at fulfillment time. Give each sender a health state and
  surface it in the operator panel — a pool with no visibility into which senders
  are dead is a pool you debug by reading buyer complaints.
- **Selector bugs are balance bugs.** Choosing a sender whose limit window is
  exhausted converts into a failed order, so selection must consult usage per
  window, not just "is it logged in".
- **Every additional sender is another credential to secure** — see rule 5.

## Rule 4 — the automation line is drawn by the platform's terms, not by what the API allows

Platform terms commonly forbid **automating trade processes without the user's
consent**, and separately forbid holding a user's password. Two things follow:

- **Sending an offer automatically sits in a grey zone; auto-accepting on the
  user's behalf is on the prohibited side of the line.** If a delivery path exists
  in the codebase that accepts on the recipient's behalf, that is the finding to
  raise — not a feature to extend. Keep the buyer's approval in the loop; the
  route that requires it is also the one that keeps the account alive.
- **Say plainly that the limit is contractual, not technical.** When a user asks
  why "auto" is capped, the answer is the platform's ToS and rate limits, not a
  missing skill. Anyone selling unlimited automation in this domain is carrying
  ban risk they are not disclosing, and the account that gets banned is the one
  holding the balance.
- Do not remove a credential-based route's guard rails to make it smoother. See
  rule 5 — that route is the one that can lose the buyer's account.

## Rule 5 — a credential-holding delivery route is a liability to contain, not a feature to grow

When the product accepts a buyer's account password (and possibly a backup/recovery
code) to deliver by logging in:

- **Never store it reversibly.** Hash with a per-deployment pepper and a memory-hard
  KDF. **Refuse to start when the pepper is missing** — a missing secret must be a
  boot error, never a silent fallback to an unhashed or default-keyed path.
- **A hash is not encryption, and it is not a mitigation for having received the
  credential.** It removes the storage liability; it does not remove the fact that
  the buyer handed over their account, and it means the route cannot log in again
  later without asking them anew. Say that, because it is the reason a hash does
  not make the route safe.
- **That route is the one that can destroy a customer's account.** It is the
  correct candidate to deprecate — recommend narrowing or removing it, and never
  present it as equivalent to a route that does not need the password.
- Anyone handling credentials is in a trust-boundary role: validate length bounds,
  rate-limit the endpoint hard, require CSRF, and never log the field.

## Rule 6 — verify a legacy platform endpoint before trusting it, and never present it as a fix you have not tested

Storefront integrations accumulate calls to platform endpoints that may have been
retired or moved to a legacy docs subtree. A fallback path that silently 404s looks
like coverage and is worse than no fallback: it converts a clear failure into an
ambiguous one.

- Find every platform hostname in the delivery path and check each against current
  published documentation before describing the path as working.
- For endpoints reachable only via an unofficial client library, distinguish
  "documented" from "observed working" and label the difference in your summary.
  Offer the live check as the next step instead of asserting it works.
- Prefer the officially documented API route over a scraped/undocumented one, and
  say when the official route cannot serve a headless server (an in-experience-only
  API with a recipient prompt cannot replace a server-side delivery path, no matter
  how official it is).

## References

- `references/roblox-robux-delivery-routes.md` — the worked example: Roblox's three
  delivery routes, current transfer limits and eligibility, the trades/gifts
  endpoint shapes, reseller vocabulary decoded ("via login / via plus / via send"),
  and the official Transfers API's in-experience boundary.
