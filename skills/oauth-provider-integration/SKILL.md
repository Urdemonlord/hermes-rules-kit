---
name: oauth-provider-integration
description: Backend OAuth integration with third-party provider APIs — scope troubleshooting, token management, and provider-specific implementation patterns
tags: [oauth, api-integration, backend, providers]
---

# OAuth Provider Integration

Backend OAuth integration patterns for third-party provider APIs (Google Drive, Dropbox, OneDrive, etc.). Covers scope troubleshooting, token lifecycle, and provider-specific API quirks.

**Use when**: Integrating OAuth-based third-party APIs, debugging provider 403/401 errors, implementing provider connect/disconnect flows.

---

## Core OAuth Flow

1. **Begin connection**: Generate OAuth state, redirect user to provider consent screen
2. **Callback handler**: Receive authorization code, exchange for access/refresh tokens
3. **Token storage**: Encrypt tokens, store with expiry, associate with user connection
4. **API calls**: Use access token, refresh when expired
5. **Disconnect**: Revoke tokens, cascade delete user data

---

## Common Pitfalls

### 403/401 Errors AFTER Successful Token Exchange

**Symptom**: OAuth callback succeeds, token is obtained, but subsequent API calls return 403 Forbidden or 401 Unauthorized.

**Root cause**: OAuth scopes granted don't match API endpoints being called.

**Example**:
- Token has `drive.metadata.readonly` scope
- Backend calls `GET /drive/v3/about?fields=user` (requires `drive.readonly` or `profile` scope)
- Google returns 403

**Fix**:
1. Identify which API endpoint is failing (check backend logs)
2. Look up required scopes in provider API docs
3. Update OAuth scope list in backend config
4. **Important**: Users with old tokens must revoke and reconnect (old tokens keep old scopes)

**Scope expansion does NOT automatically update existing tokens.** Users must:
- Go to provider permissions page (e.g., https://myaccount.google.com/permissions)
- Remove app access
- Reconnect via your app to get new token with new scopes

### OAuth State Not Persisting

**Symptom**: OAuth callback returns "state not found" or similar error.

**Root cause**: Using in-memory state store; state is lost on server restart or load-balanced requests.

**Fix**: Use persistent state store (PostgreSQL, Redis) with TTL (10-15 minutes).

```go
// Bad: InMemoryStateStore — lost on restart
store := NewInMemoryStateStore()

// Good: Database-backed state store
store := NewPostgreSQLStateStore(db)
```

### State cookie never reaches the callback (host-only cookie vs multi-host serving)

**Symptom**: the provider returns to your callback and the handler rejects it with a state error. The two sub-causes look identical to the user but need different fixes — split them *in the callback log* before theorizing.

Log the **presence** of each input, not just the outcome:

```ts
console.warn('oauth callback', {
  hasStoredState: Boolean(storedState),       // was a state ever stored for this session?
  cookieHeader:  Boolean(req.headers.cookie), // did the browser send ANY cookie?
  hasStateParam: Boolean(stateParam),
});
```

- `cookieHeader: false` → the browser sent **zero** cookies. The state was never going to match; this is a cookie-delivery problem, not a state-logic problem. Do not go debug state comparison.
- `cookieHeader: true, hasStoredState: false` → cookies arrive but the state key is missing/expired → TTL, process restart (see the in-memory pitfall above), or a cookie-name mismatch.

**Before blaming the cookie, confirm the callback was ever reached.** A `cookieHeader: false` line proves only that *that one request* carried no cookie — it does not prove the user's sign-in failed here. If the request was your own probe, or the provider refused the flow at its authorize step, the user never got this far and you are debugging a symptom you invented. Check the access log for a callback from a **browser** (real UA / `Referer`), not your own agent, before theorising:

```bash
sudo grep '<callback-path>' /var/log/nginx/access.log
# only your curl probes? the failure is upstream of your app — go to the provider's app settings
```

A log read that returns nothing may mean the file was unreadable, not empty: `access.log` is commonly root-only (`-rw-r----- www-data adm`), and `grep` as a normal user exits non-zero with no output — indistinguishable from "no traffic". Confirm the file is actually readable (`sudo wc -l <log>`) before treating "no hits" as "no traffic".

**Then, for a genuine `cookieHeader: false` from a real browser: the app may be served under more than one hostname with a host-only state cookie.** A cookie set while the user was on `a.example.com` is not sent to `b.example.com`. If the authorize step ran on one host while `redirect_uri` is pinned to another, the callback lands on a host that never received the cookie. Confirm the second host is actually in use (grep the access log for the callback path per host) before acting — an unused `server_name` alias does not cause this.

Audit the hosts serving the app **before** touching app code:

```bash
grep -rn 'server_name' /etc/nginx/sites-enabled/ | grep -i '<app-domain>'
# two hostnames on the same upstream = two cookie jars for one app
```

Fixes, in order of preference:
1. **One canonical host.** Stop serving the app on the second hostname (or 301 it to the canonical one). Cleanest — no cross-host cookies at all.
2. **Scope the cookie to the parent domain** (`Domain=.example.com`) so all subdomains share it. Works, but the cookie is then sent to *every* subdomain — acceptable only when the whole parent domain is trusted.
3. **Register a per-host `redirect_uri`** and build it from the request host so each host round-trips to itself. Requires adding every host to the provider's registered list (GitHub: manual only).

**Do not trust an empty result from a cookie-capturing probe.** `curl` and its cookie jar will not store/resend a `Secure` cookie and drop cookies across cross-host redirects, so a probe that "proves the cookie is missing" may be a probe artifact. Read the `Set-Cookie` attributes (`Secure`, `SameSite`, `Domain`, `Path`) from the response headers directly, and test the flow over the real HTTPS origin — never plain `http://127.0.0.1`.

### `redirect_uri` built from a silent default — the provider blames its own console

**Symptom**: the provider refuses sign-in with a message pointing at *its* configuration, e.g. Google's "The redirect_uri is not associated with this application." Nothing in the message mentions your app, so the instinct is to go re-check the provider console.

**Root cause**: the app built its redirect_uri from a fallback:

```js
`${process.env.PUBLIC_SITE_URL || 'http://localhost:5173'}/api/auth/google/callback`
```

When the origin env var is missing — or the process started without its environment — the app emits `http://localhost:5173/...`, which is not among the redirect URIs registered for that client. A production client rarely has localhost registered. The provider rejects it and the error blames the console, hiding the real cause: a missing env var.

**Fix — resolve the origin once, and fail hard in production:**

```ts
const siteUrl = (): string => {
  const configured = process.env.PUBLIC_SITE_URL?.trim();
  if (configured) return configured.replace(/\/+$/, '');   // normalize trailing slash
  if (process.env.NODE_ENV === 'production') {
    throw new Error('PUBLIC_SITE_URL is not set; the OAuth redirect_uri cannot be built.');
  }
  return 'http://localhost:5173';                          // dev only
};
```

- Define it **once, above every provider helper**, and use it in both the authorization URL *and* the token exchange — those two must send a byte-identical redirect_uri.
- **Fix every provider, not just the one the user reported.** The fallback is usually copy-pasted into each helper; grep for it (`grep -rn 'PUBLIC_SITE_URL ||' src/ backend/src/`) and check every hit. Leaving one behind reproduces the identical bug on the other provider later.
- A localhost default for a **non-redirect** use (e.g. an `HTTP-Referer` header) is harmless — do not "fix" those, only redirect_uri construction.
- Registration is per-client and matches **exactly** (scheme, host, path; no trailing slash unless registered). A URI registered for a different client or host does not count.

**Diagnosing which URIs are actually registered** — probe the provider's authorize endpoint and read the **redirect target**, never the response body:

```bash
loc="https://accounts.google.com/o/oauth2/v2/auth?client_id=$CID&redirect_uri=$ENC&response_type=code&scope=openid%20email%20profile&state=diag"
dest=$(curl -s -o /dev/null -w '%{redirect_url}' -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/203.0.113.10 Safari/537.36' "$loc")
# registered     -> .../signin/identifier    (proceeds to login)
# not registered -> .../signin/oauth/error?authError=...redirect_uri_mismatch
```

Google answers **302 with an empty body**, so matching on body text reports *every* URI as registered. Always include a **negative control** — a URI that is certainly not registered (e.g. `https://example.com/nope`). If the control comes back "registered", the detector is broken, not the data. Validate the detector before trusting any verdict it gives.

Send a **browser User-Agent** on every such probe. A WAF in front of the app (Cloudflare et al.) answers a default `curl`/`python-urllib` agent with `403` (Cloudflare: "error 1010") — that reads as an app failure and sends you chasing a bug that does not exist. `-A 'Mozilla/5.0 … Chrome/120'` is enough to get through.

**At deploy time**, assert the redirect_uri the app actually emits matches the configured origin — the cheapest way to catch a lost env var before users do:

```bash
expected="$(grep -E '^PUBLIC_SITE_URL=' backend/.env | cut -d= -f2- | sed 's#/*$##')"
redirect="$(curl -s -o /dev/null -w '%{redirect_url}' http://127.0.0.1:3100/api/auth/google | sed -n 's/.*redirect_uri=\([^&]*\).*/\1/p')"
case "$redirect" in "$expected"/*) ;; *) echo "redirect_uri mismatch: $redirect" >&2; exit 1 ;; esac
```

**Do not conclude the app is wrong before checking the provider's registered list.** A perfectly correct redirect_uri is still refused if the callback URL was never added to the provider's app settings — GitHub requires this manually, there is no API for it.

### GitHub: OAuth App vs GitHub App — editing the wrong settings page

**Symptom**: GitHub shows "The `redirect_uri` is not associated with this application" (or `redirect_uri_mismatch`) and never calls your callback. You change the callback URL and the error is unchanged.

**Root cause**: GitHub has **two separate app types with separate settings pages**, and the code is registered against one while the user is editing the other.

| | OAuth App | GitHub App |
|---|---|---|
| client_id prefix | `Ov23li…` (modern) / `Iv1.…` (older) | `Iv23li…` / `Iv1.…` |
| settings page | `github.com/settings/developers` → **OAuth Apps** | `github.com/settings/developers` → **GitHub Apps** |
| field that matters | **Authorization callback URL** | **Callback URL** (distinct from Setup URL) |
| `scope=` param | used (classic scopes) | **not used** (fine-grained permissions) |

Tell them apart **from the code**, not by asking: an authorize URL carrying `scope=…`, a token exchange at `github.com/login/oauth/access_token`, and calls to `api.github.com/user` is the **OAuth App** flow. A GitHub App uses fine-grained permissions and sends no `scope`.

Common user errors, in order: editing the GitHub App when the code uses an OAuth App; editing "Homepage URL" instead of "Authorization callback URL"; a different host than the app emits (`localhost:5173`, an older domain); a trailing slash; the app living under a different account/org.

Callback matching: apps created before 2026-08-03 have **wildcard matching** on their single callback URL — host (minus subdomain) and port must match and the path must be a subdirectory. Newer apps require an **exact** match. Either way a different host is fatal.

**You cannot verify a GitHub `redirect_uri` from outside.** `GET github.com/login/oauth/authorize` answers `302 → /login?client_id=…&return_to=…` for a valid client_id, a bogus one (`Ov23liNOTREAL123`), a registered URI and an unregistered URI **alike** — validation runs only after login. The negative control fails, so the detector is unusable; per the probe rule above, stop and get the user's browser evidence (the error page / the authorize URL from the address bar) instead of guessing. GitHub also has **no API** to register a callback URL — it is manual only.

### One authorize endpoint serving two intents: sign-in vs connect

**Symptom**: a logged-in user clicks "Connect <provider>" and either nothing happens, or they silently end up signed in as a *different* account.

**Root cause**: a single `/api/auth/<provider>` endpoint is used for two different intentions — **sign in** (create a session) and **connect** (attach the provider to the account already signed in) — with one code path. The callback does `SELECT … WHERE provider_id = <incoming id>` and, on a hit, issues a session **for that found user**. If the incoming provider identity is already bound to another account, the connect flow silently switches the user to it.

**Rule**: the intent must be explicit and unforgeable, and the two paths must not share the account-resolution code.

1. Carry the intent **inside the state nonce** (e.g. suffix `.c` for connect), and keep the nonce in the httpOnly state cookie. The browser cannot forge it, so the callback can trust it without a second channel:

   ```ts
   const intent = req.query('intent') === 'connect' ? 'connect' : 'login';
   if (intent === 'connect' && !c.var.user) return c.redirect('/login?error=login_required');
   const nonce = crypto.randomBytes(16).toString('hex');
   const state = intent === 'connect' ? `${nonce}.c` : nonce;   // set this exact value in the cookie
   // callback: const intent = storedState?.endsWith('.c') ? 'connect' : 'login';
   ```

2. In the callback, branch **before** any session creation:
   - **connect**: require an authenticated session; update *that* user's row; **never** create or switch a session. If the provider identity is already bound to a different user, **refuse** — silently re-pointing the link would hand the caller the other account's data.
   - **login**: only here do you resolve the identity to a user and create a session.

3. **Every redirect out of the callback must honour the intent — including the `catch` block.** A failed connect that lands on `/login` looks to the user like they were logged out; send connect failures back to the settings page (`/settings?error=…`) and surface the reason there. This is easy to miss because the happy path is branched but the error path is not.

4. Apply the split to **every** provider, not just the reported one. The flaw is copy-pasted between providers; the second one reproduces it later.

**Verify** (this is the check that actually catches the bug):

- Seed a second user with the provider id already bound, then run "Connect" from the first user's session. The flow must link or refuse — and the **original session id must still be valid afterwards** (assert `/api/auth/me` returns the same user id, not merely that the response is non-error).
- Connect without a session → `/login?error=login_required`.
- Pure sign-in → still lands on the login path.

**Test artifacts that fake a failure here** (each produced a false "session was swapped" verdict before being ruled out):

- **Your own app's rate limiter.** A 30-req/60s limiter answers `429` to every probe; curl then prints empty status/redirect fields, and the follow-up `/me` check reads as unauthenticated — indistinguishable from "the session changed". Print the raw status code, and if it is `429`, wait for the window to clear and re-run **one** clean pass instead of concluding a bug.
- **`-b jar -c jar` on the same file.** Writing and reading the same cookie jar in one call makes the jar round-trip drop the session cookie. Capture the state param **and** the `Set-Cookie` header from the **same single response**, then send both explicitly.
- **A `Secure` cookie over plain HTTP.** See the probe note above — test over the real HTTPS origin.

### Callback failures must redirect with a reason, never return a bare error body

A callback that answers a failure with raw HTML (a `<h3>…</h3>` string) is undiagnosable: the user sees a dead-end page, and you cannot tell a missing cookie from a stale tab from a replayed callback. Make every exit path a **redirect carrying a machine-readable code**, and log the specific condition that tripped:

- Redirect to the login page (or, for a connect flow, the settings page) as `/login?error=<code>`, and map codes to human messages on that page. The reason then survives the redirect and is visible without reading server logs.
- Log *which* input was missing, not just that the check failed (`hasCode`, `hasState`, `hasStoredState`, `match`, `cookieHeader`) — the combination is what identifies the cause.
- Treat the provider's `?error=access_denied` (user pressed Cancel) as a **normal choice**, not a failure: redirect with a plain "you cancelled" message.
- Never echo upstream error text to the user. Provider error bodies routinely leak the model slug, provider name, or account identifier; keep the raw detail in the server log and show the user a generic message.

### Provider-Specific Gotchas

**Dropbox**:
- Download API uses `https://content.dropboxapi.com` (not `api.dropboxapi.com`)
- File path goes in `Dropbox-API-Arg` header, not query params
- Response metadata in `Dropbox-API-Result` header

```go
req.Header.Set("Dropbox-API-Arg", `{"path": "/file.pdf"}`)
// Body is the file content stream
// Metadata in resp.Header.Get("Dropbox-API-Result")
```

**Google Drive**:
- `/drive/v3/about?fields=user` requires user profile scopes (`openid`, `email`, `profile`)
- `/drive/v3/files` metadata requires `drive.metadata.readonly` minimum
- File download needs `drive.readonly` or `drive`

---

## Provider Disconnect Pattern

### Backend

1. Verify connection belongs to requesting user
2. Delete connection record (cascade deletes files/metadata via DB foreign keys)
3. Optional: Call provider revoke endpoint (if available)
4. Return success

```go
func (r *Router) handleProviderDisconnect(w http.ResponseWriter, req *http.Request) {
    user := requireUser(req)
    connectionID := extractConnectionID(req)

    // Verify ownership
    conn, err := r.connections.GetByIDForUser(ctx, user.ID, connectionID)
    if err != nil { /* 404 */ }

    // Delete (cascade)
    if err := r.connections.Delete(ctx, connectionID); err != nil {
        /* 500 */
    }

    // Optional: revoke at provider
    // revokeAtProvider(conn.Provider, conn.AccessToken)

    writeJSON(w, 200, {"message": "disconnected"})
}
```

### Frontend

1. Confirm dialog (warn about data loss)
2. Call disconnect endpoint
3. Refresh provider list
4. Show success/error message

```typescript
async function disconnect(connectionID: string) {
  if (!confirm('Remove this provider? Synced files will be deleted.')) return
  try {
    await disconnectProvider(connectionID)
    await refreshProviders()
  } catch (e) {
    showError(e.message)
  }
}
```

---

## Token Refresh Pattern

1. Check `token_expires_at` before API call
2. If expired and refresh token exists, call provider token refresh endpoint
3. Update stored tokens with new values
4. Retry original API call

```go
func (s *Service) callAPI(ctx context.Context, conn Connection) error {
    if time.Now().After(conn.TokenExpiresAt) {
        newTokens, err := s.refreshToken(ctx, conn.RefreshToken)
        if err != nil { return ErrRefreshFailed }
        conn = s.updateTokens(ctx, conn.ID, newTokens)
    }
    return s.makeAPICall(ctx, conn.AccessToken)
}
```

---

## Verification Steps

After implementing OAuth integration:

1. **Scope coverage**: List all API endpoints your backend calls, verify scopes cover them all
2. **Token refresh**: Test with expired token (manually set `token_expires_at` in past)
3. **Disconnect**: Verify cascade delete works (check DB, confirm files removed)
4. **State persistence**: Restart backend mid-OAuth flow, verify callback still works
5. **Error messages**: Trigger 403/401, verify user sees helpful error (not just "failed")

---

## Firebase / Google sign-in notes

For Firebase-based Google login flows in this repo, see `references/firebase-google-signin-triage.md`.

---

## References

- `references/dropbox-api-patterns.md` — Dropbox-specific API quirks
- `references/google-drive-scopes.md` — Google Drive scope requirements by endpoint
- `references/firebase-google-signin-triage.md` — Firebase Google sign-in triage notes for popup + profile sync failures
- `references/github-callback-url-troubleshooting.md` — GitHub OAuth App vs GitHub App: telling them apart, where the callback URL lives, and the user-facing checklist

---

## Absorbed sibling workflows

### Interactive browser-auth handoff
narrow sibling absorbed: `interactive-oauth-browser-auth`

When OAuth automation reaches a provider-side human verification wall, keep working inside this umbrella instead of loading a one-off auth skill:
- inspect the actual challenge screen after password submission
- classify the challenge type (number match, recovery email, SMS, device security code, QR)
- tell the user the exact visible action required, including the current number/device/destination
- re-check that the browser session actually advanced after the user acts
- persist session/browser state when the downstream provider integration depends on it

## Related Skills

- `idp-session-bridge` — Migrating app auth to third-party identity providers
