# Roblox Robux Delivery — Routes, Limits, Vocabulary

Worked example backing `virtual-goods-fulfillment`. Everything here is platform
behaviour that constrains the architecture; re-check the limits against the live
source before quoting them, because they change.

## The three delivery routes

| Route | Automates | Limiting factor | Notes |
|---|---|---|---|
| Gift card code pool | Fully | Stock of codes | The only route with instant, predictable delivery. Redeemable by anyone until claimed, so codes are not tied to a buyer. Must be claimed atomically. |
| Group payout | Partially | Roblox waiting periods | Currency comes out of a group balance; tied to account + membership state. Instant delivery is physically impossible. |
| Direct transfer / trade | Only to the recipient's approval | Recipient must accept | Server can send an offer; the buyer completes it. |

A fourth route exists commercially but is not a Roblox mechanism: **account-login
delivery** — the seller signs into the buyer's account and delivers from there.
See "Credential route" below.

## Reseller vocabulary (Indonesian market)

The terms come from the delivery method, so decoding them is how you map a
market listing onto a delivery path:

| Term | Origin | Meaning |
|---|---|---|
| `vilog` / `v2l` | *via login* | Seller logs into the buyer's account. Requires the buyer's password. |
| `viplus` | *via plus* | Roblox Plus transfer feature. |
| `visend` | *via send* | Send to username, or via gamepass/gift item. |
| `autovisend` | auto + visend | **Not a platform term.** Slang for "send Robux, automated by a bot/script". No standard definition — do not treat it as a documented capability. |

`gp` / gamepass method: the buyer creates/sells a gamepass and the seller buys it,
which credits the buyer through the normal creator-payout path. Different from
both transfer and login, with its own waiting period.

## Roblox Plus transfer limits (verify against source before quoting)

- **5,000 Robux/day and 10,000 Robux/month** with 2-Step Verification enabled and
the account in good standing.
- Without 2SV: 500/day and 1,000/month.
- Recipients do **not** need Plus; only senders do.
- Age: 16+ requires an age check; under 16 requires a linked parent account with
**approval on every transfer**. Some regions require parental approval up to 18.
- **A sent transfer cannot be reversed or cancelled.**
- **Transferred Robux is not eligible for DevEx** — spend-only inside the platform.

Sources: Roblox support article "Sending and Receiving Robux"; the Roblox Plus
transfers announcement on the Developer Forum.

## Endpoint shapes

**Trades API** — `POST https://trades.roblox.com/v1/trades/send`, authenticated with
the `Cookie: .ROBLOSECURITY=<cookie>` header plus an `X-CSRF-TOKEN`. The CSRF token
is obtained by sending any mutating request and reading `x-csrf-token` from the
(rejection) response, then replaying it. A payload roughly:

```json
{
  "SendingItem": null,
  "RequestingItem": null,
  "UserIdToTrade": 123,
  "Note": "...",
  "Requester": { "UserId": <sender>, "Robux": 500 }
}
```

This **sends an offer**. It requires the recipient to have trading enabled, and the
sender account needs inventory space so the returned item can be held.

**Gifts endpoint** — `POST https://economy.roblox.com/v1/gifts/give` with
`{recipientUserId, assetId, robux, message}`. Same cookie + CSRF requirements. This
is a **legacy** endpoint documented under `create.roblox.com/docs/cloud/legacy`;
verify it responds before depending on it as a delivery fallback.

The `noblox` npm package wraps both and exposes `setCookie()` plus user/gamepass
lookups, which is why storefront code often mixes direct `fetch` calls with the
library.

**Official Transfers API** — `PromptRobuxTransferAsync` + `BindReceiptHandler`,
documented at `create.roblox.com/docs/production/monetization/robux-transfers`. It
is **in-experience only**: it opens a prompt and requires the recipient's approval
in the client. It cannot serve as a headless server-side delivery path, no matter
how official it is.

## Credential route

`vilog` means the store accepts the buyer's Roblox password (frequently a
backup/recovery code as well). Roblox explicitly forbids sharing account
credentials, and this is the route that can get the *buyer's* account compromised
or banned. If a storefront keeps this path, it should hash with a peppered KDF,
rate-limit hard, require CSRF, and be presented to the owner as a deprecation
candidate.

## Inventory / stock APIs used for validation

Storefronts usually call public Roblox endpoints for validation rather than for
delivery: user resolution by username, owned-gamepass checks
(`inventory.roblox.com/v1/users/<id>/items/GamePass/<passId>`), gamepass listings
(`games.roblox.com/v1/games/<universeId>/game-passes`), and the newer
`apis.roblox.com/game-passes/v1/universes/<universeId>/game-passes?passView=full`.
These are read-only and unauthenticated, which makes them a separate security
surface from the delivery path.
