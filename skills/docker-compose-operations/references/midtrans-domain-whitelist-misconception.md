# Addendum: Domain Whitelist Misconception (from 2026-07-25 session)

**Never tell the user to "register domain" in Midtrans dashboard for regular Snap.** There is no domain whitelist for regular Snap integration.

When user asks "dimana daftar domain Midtrans?" → answer is: there is none needed. See `references/sveltekit-midtrans-snap-vs-bisnap.md` for the full Regular Snap vs BI-SNAP distinction.

## Midtrans Dashboard Settings Needed (regular Snap)

1. **Settings > Payment Notification URL** → webhook endpoint (e.g., `https://client-site.meowlabs.id/api/midtrans/webhook`)
2. **Settings > Finish Redirect URL** (optional — we pass `finishCallbackUrl` per-transaction)
3. **Settings > Unfinish Redirect URL** (optional)
4. **Settings > Error Redirect URL** (optional)

That's it. No domain tab. No IP whitelist. No credential exchange process.

## Where the confusion came from

- `docs.midtrans.com/reference/getting-started-1` → this is **BI-SNAP Core API** getting started, NOT regular Snap
- BI-SNAP requires: PKCS8 keypair, IP whitelist, notification URL during onboarding, credential exchange with Midtrans
- Regular Snap only needs: Server Key + Client Key + optional webhook URL

Always check which product (Snap vs BI-SNAP) before quoting docs.
