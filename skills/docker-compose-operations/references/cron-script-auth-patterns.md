# Cron Script Authentication Patterns

## Problem: Silent 403 Failures in `no_agent` Cron Scripts

**Session**: 2026-07-27. Project: iki-tenun auto-cancel orders cron job.

### Symptom

Cron job runs every 15 minutes with `last_status: error` but **no visible logs or alerts**. The job calls a protected endpoint (e.g., `/api/cron/cancel-expired`), receives HTTP 403 Unauthorized, and exits silently because the script uses `curl -sf` (silent fail).

Running `cronjob(action='run')` shows no change in `last_status` — it stays `error` indefinitely.

### Root Cause

The protected endpoint requires a cron secret in query params or headers:

```typescript
// +server.ts
export const GET: RequestHandler = async ({ url, request }) => {
  const CRON_SECRET = process.env.CRON_SECRET
  const secret=<redacted>'secret')
  const headerSecret = request.headers.get('x-cron-secret')
  if (secret !== CRON_SECRET && headerSecret !== CRON_SECRET) {
    return json({ error: 'Unauthorized' }, { status: 403 })
  }
  // ... actual work (auto-cancel orders, restore stock, etc.) ...
}
```

But the calling script in `~/.hermes/scripts/` does **not** pass the secret:

```bash
# BROKEN — no secret parameter
curl -sf "https://client-site.meowlabs.id/api/cron/cancel-expired" 2>&1
```

Result: **403 every run, script exits with code 22 (HTTP error), but output is empty** because of `-sf`. The cron scheduler records `error` status, but the actual 403 response is never logged or visible to the user.

### Fix

Pass the secret as a query parameter. The secret is defined in `compose.yaml`:

```bash
#!/bin/bash
# FIXED — pass CRON_SECRET from env or hardcoded default
CRON_SECRET="${CRON_SECRET:-yCm6rAoTpl9fc6DdYO8bSSgo9EP8NfvunXQ6rjrktPA}"
curl -sf "https://client-site.meowlabs.id/api/cron/cancel-expired?secret=<redacted>" 2>&1
```

Or use a header (alternate pattern):

```bash
curl -sf -H "x-cron-secret: ${CRON_SECRET}" "https://client-site.meowlabs.id/api/cron/cancel-expired" 2>&1
```

### Detection Workflow

```bash
# 1. Check if cron job has been failing silently
cronjob(action='list')
# → look for `last_status: error` on a recurring job (every 15m, daily, etc.)

# 2. Check the output file for clues
cat ~/.hermes/cron/output/<job_id>/$(date +%Y%m%d).log
# → if empty or just "exit 22", likely auth issue

# 3. Test the endpoint manually without secret
curl -v "https://client-site.meowlabs.id/api/cron/cancel-expired"
# → HTTP/2 403 Unauthorized

# 4. Verify the fix works
CRON_SECRET=$(grep CRON_SECRET ~/.hermes/config.yaml | awk '{print $2}')
curl -s "https://client-site.meowlabs.id/api/cron/cancel-expired?secret=<redacted>"
# → HTTP/2 200 OK + JSON response with {cancelled: N, restored: M}
```

### Prevention Checklist

- [ ] For any protected cron endpoint, the calling script MUST pass auth (query param, header, or API key)
- [ ] The secret is typically a build ARG or env var defined in `compose.yaml` — extract and use in the script
- [ ] Test the endpoint with curl before deploying to cron
- [ ] Audit all `no_agent` cron scripts to verify they include auth
- [ ] Add a comment in the script referencing the protected endpoint spec and where to find the secret

### Pitfall: `-sf` Flag Hides Errors

`curl -sf` = silent + fail (exit code 22 on HTTP 400+ but **no output**). When used in `no_agent` cron scripts, auth errors vanish completely — the job fails repeatedly with no visible reason.

**Better patterns:**

**Option A — Remove `-f`, keep `-s`:**
```bash
# If 403, curl still returns exit code 22, but JSON error is printed
curl -s "https://client-site.meowlabs.id/api/cron/cancel-expired?secret=<redacted>"
```

**Option B — Include error handling:**
```bash
response=$(curl -s -w "\n%{http_code}" "https://client-site.meowlabs.id/api/cron/cancel-expired?secret=<redacted>")
body="${response%$'\n'*}"
code="${response##*$'\n'}"

if [ "$code" != "200" ]; then
  echo "ERROR: HTTP $code — $body" >&2
  exit 1
fi

echo "$body"  # parsed JSON response
```

**Option C — Use `-i` to include headers (debugging):**
```bash
curl -si "https://..." | head -20  # shows HTTP status line
```

### Real-World Timeline (Session 2026-07-27)

1. **Initial report**: User says "pesanan yg ga dibayar bayar ga hilang padahal sebelumnya cancel sendiri"
2. **Root cause**: Cron job `/api/cron/cancel-expired` was returning 403 silently for **days**
3. **Why silent**: Script used `curl -sf`, endpoint requires `?secret=<redacted>`, cron output was empty
4. **Fix**: Added secret parameter to script, tested with curl, redeployed
5. **Verification**: Script now returns 200 OK, next run will auto-cancel expired orders

### Related Patterns

- **Hermes cron auth guard**: SvelteKit `+server.ts` with CRON_SECRET env var
- **Multi-layer delivery failures**: Email/WA cron jobs can fail due to provider auth OR delivery endpoint auth — debug both
- **Docker env var override**: When updating `.env` or `compose.yaml` with new secrets, remember `docker restart` does NOT pick up new values if they're `${VAR}` interpolation — use `docker compose up -d --force-recreate` instead

