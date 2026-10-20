## Regular Snap vs BI-SNAP (important distinction)

This project uses **regular Snap** (redirect-based). It does NOT use BI-SNAP.

| Aspect | Regular Snap | BI-SNAP (Core API) |
|--------|-------------|-------------------|
| Integration | Simple API call → Snap token | Requires credential exchange with Midtrans |
| Domain whitelist | None needed — works on any domain | Must whitelist outgoing IP on Midtrans side |
| Client Key | Public frontend key for Snap.js init | Not used — uses Client ID/Secret instead |
| Server Key | Server-side auth for creating transactions | Uses X-CLIENT-KEY + X-PARTNER-ID headers |
| Public-private keys | Not needed | Must generate PKCS8 keypair |
| IP whitelist | Not needed | Merchant's outgoing IP must be whitelisted |
| Notification config | Set Payment Notification URL in dashboard | Must provide notification URL + Midtrans IP whitelist |
| Redirect URL | Pass `finishCallbackUrl` per-transaction | Required only for GoPay Tokenization flow |

**What this means**: For regular Snap (what client-site uses), you do NOT need to register any domain or whitelist any IP. The Client Key (`Mid-client-...`) and Server Key (`Mid-server-...`) work as-is once set. The only Midtrans dashboard setting needed is the **Payment Notification URL** (webhook).

**If you see docs talking about**: "credential exchange", "public/private key PKCS8", "outgoing IP whitelist", "notification URL as onboarding item" — those are for BI-SNAP, NOT regular Snap.

**Docs URL**: `docs.midtrans.com/reference/getting-started-1` is BI-SNAP documentation. For regular Snap, use `docs.midtrans.com/docs/snap`.

### Production cutover checklist

When moving from sandbox (`SB-`) to production (`Mid-server` / `Mid-client`):

1. **Update `.env`**:
   - `MIDTRANS_SERVER_KEY=Mid-server-...` (not `SB-Mid-server-...`)
   - `PUBLIC_MIDTRANS_CLIENT_KEY=Mid-client-...` (not `SB-Mid-client-...`)
   - `MIDTRANS_MERCHANT_ID=M283228709` (the production MID)
   - `MIDTRANS_IS_PRODUCTION=true`

2. **Recreate container** (not just restart — compose `${VAR}` interpolation bakes values at creation time):
   ```bash
   docker compose up -d --force-recreate
   ```

3. **Masked verification** (never echo raw secrets):
   ```bash
   docker inspect <container> --format '{{json .Config.Env}}' | python3 -c "
   import sys, json
   envs = json.load(sys.stdin)
   for e in envs:
       if any(k in e.upper() for k in ['MIDTRANS']):
           parts = e.split('=', 1)
           val = parts[1] if len(parts) > 1 else ''
           masked = val[:8] + '...' + val[-4:] if len(val) > 12 else val
           print(f'{parts[0]}={masked}')
   "
   ```

4. **Verify "no domain whitelist needed"** — don't go looking for a domain setting in Midtrans dashboard. There is none for regular Snap. Just make sure your webhook URL is set at **Settings > Payment Notification URL**.
