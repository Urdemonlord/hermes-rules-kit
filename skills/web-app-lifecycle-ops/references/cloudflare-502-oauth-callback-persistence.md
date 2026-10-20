# Cloudflare 502 Interception + OAuth Callback Persistence

## Problem: Cloudflare replaces backend 502 with branded error page

When the backend returns a 502 Bad Gateway response (for example from a failed OAuth token exchange), Cloudflare **replaces the response body** with its own branded "Error 502 | Bad Gateway" page. The user sees a Cloudflare-branded error with no reference to the actual problem. This makes OAuth debugging impossible.

**Symptom:** User sees "Error code 502" with a Cloudflare-branded page after an OAuth provider callback. The 502 is not from nginx — it's the backend's own response being intercepted.

**Root cause:** Standard Go error handler:
```go
if err != nil {
    writeError(w, stdhttp.StatusBadGateway, provider+"_sync_failed", err.Error())
    return
}
```
Returns a 502 JSON response. Cloudflare reads the 502 status code and renders its branded 502 page instead of forwarding the JSON body to the browser.

## Fix: Redirect to frontend with query-param error message

Instead of returning raw 502 JSON, redirect the browser to the frontend's callback handler with error details in query params:

```go
if err != nil {
    stdhttp.Redirect(w, req, result.RedirectURL+
        "&status=error&message="+url.QueryEscape(err.Error()),
        stdhttp.StatusFound)
    return
}
```

This way:
- The browser receives a 302 redirect (Cloudflare passes this through)
- The frontend's callback view receives the error message
- The user sees a clean page explaining what happened
- Cloudflare never intercepts

The redirect URL format:
```
https://app.com/oauth/callback?provider=google_drive&status=error&message=...encoded+error...
```

Requires `"net/url"` import in Go.

### What does NOT work

- Adding `Cloudflare-Origin-Body: 1` header — undocumented, unreliable
- Using `X-Cloudflare-Debug` headers — not configurable from origin
- Changing status to 500 instead of 502 — same interception
- Empty body responses — Cloudflare may still show its own error page

### What works: use 3xx (redirect) or 2xx (OK with error body)

- **3xx redirect** (recommended for OAuth callbacks): Pass error info as query params
- **2xx response** (alternative for API endpoints): Return 200 OK with error JSON body. Cloudflare does NOT intercept 2xx status codes. Only use this for non-callback API endpoints where the client reads the body.

## Problem: OAuth state persistence

OAuth state values must survive across server restarts and multi-instance deployments. InMemoryStateStore is unsuitable for production because:

1. **Server restart** — Any restart loses all pending OAuth states
2. **Multiple instances** — A state saved by instance A cannot be consumed by instance B
3. **Long-lived flows** — OAuth flows may take minutes (user reads consent screen). Any deployment during that window invalidates all pending states

**Symptom:** OAuth callback returns `{"error":{"code":"provider_callback_failed","message":"oauth state not found"}}`. User sees error after provider consent screen even though the flow looked correct.

### Fix: Use PostgreSQL (or Redis) for OAuth state storage

```sql
CREATE TABLE IF NOT EXISTS oauth_states (
    value TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    user_id TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_oauth_states_expires_at ON oauth_states (expires_at);
```

The `Consume` operation must atomically DELETE and RETURN:
```go
DELETE FROM oauth_states WHERE value = $1
RETURNING value, provider, user_id, expires_at
```

This prevents double-use of the same state (race condition on callback + user retry).

**Table design notes:**
- `value` as TEXT PRIMARY KEY for fast single-row delete
- `user_id` stored so the callback handler knows which user to associate the connection with (the callback request itself is anonymous — the user's browser redirected away from your app before the OAuth provider sends them back)
- `expires_at` for cleanup jobs (`DELETE FROM oauth_states WHERE expires_at < NOW()`)
- Index on `expires_at` for cleanup query performance
- **Do NOT use `WHERE expires_at < NOW()` in a partial index** — `now()` is STABLE, not IMMUTABLE. PostgreSQL rejects it. Use a simple index on `expires_at` without a predicate.

## Clerk frontend/backend key matching

Frontend (`pk_test_...`/`pk_live_...`) and backend (`sk_test_...`/`sk_live_...`) must use matching Clerk instances.

| Instance | Frontend publishes | Backend verifies |
|----------|-------------------|-----------------|
| **Test** | `pk_test_xxxxx` | `sk_test_xxxxx` |
| **Live** | `pk_live_xxxxx` | `sk_live_xxxxx` |

A mismatch (pk_test on frontend + sk_live on backend) silently breaks session exchange:
1. Frontend gets session from Clerk test instance
2. Backend verifies against Clerk live instance → fails because session belongs to a different Clerk project
3. Exchange returns error → no local JWT
4. Route guard redirects to /auth
5. Clerk sees already-signed-in user → redirects to /dashboard
6. Loop repeats

**Symptom:** Login loop — user logs in, gets redirected, then immediately redirected back to /auth with no error message.

**Detection:** Check the production frontend JS for the publishable key:
```bash
grep -oP 'pk_live_[a-zA-Z0-9_$]+|pk_test_[a-zA-Z0-9_$]+' dist/assets/index-*.js | sort -u
```

**Fix:** Build frontend with the correct key for the target environment:
```bash
VITE_CLERK_PUBLISHABLE_KEY=pk_live_xxxxx npm run build
```

Then verify only the live key is present in the output:
```bash
grep -c 'pk_test_' dist/assets/index-*.js  # should be 0 or only inside Clerk SDK internals
grep -c 'pk_live_' dist/assets/index-*.js  # should be >= 1 (the actual key)
```

Note: The Clerk JS SDK contains `pk_test_` in its error-handling code even when using a live key. The presence of `pk_test_` in the bundled JS is not a bug — check that `pk_live_XXXXX` (your actual key, not just the prefix `re="pk_live_"`) appears in the bundle, and that no `pk_test_XXXXX` (your test key as a value) appears.
