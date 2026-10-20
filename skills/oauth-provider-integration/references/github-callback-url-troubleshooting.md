# GitHub callback URL troubleshooting

GitHub is the provider where "the app is correct but sign-in still fails" is
most often a **settings-page** problem, and where external probing is useless.
This file is the depth behind the GitHub subsection in SKILL.md.

## 1. Which app type is the code using?

Decide from the code, never by asking the user which one they made.

| Evidence in code | App type |
|---|---|
| authorize URL carries `scope=...` | OAuth App |
| token exchange at `github.com/login/oauth/access_token` | OAuth App |
| calls `api.github.com/user`, `/user/repos` | OAuth App |
| fine-grained permissions, no `scope` | GitHub App |
| `/app`, `/app/installations`, `/installation/repositories` | GitHub App |

client_id prefixes (a hint, not proof):

- `Ov23li…` — modern OAuth App
- `Iv1.…` — can be either; older format
- `Iv23li…` — GitHub App

## 2. Where the callback URL lives

Both pages are reached from `https://github.com/settings/developers`:

- **OAuth Apps** → app → field **"Authorization callback URL"**
  - up to 10 entries, added with "Add callback URL"
- **GitHub Apps** → app → field **"Callback URL"**
  - **distinct from "Setup URL"** — Setup URL fires after *installation*,
    Callback URL fires after *authorization*. Putting the value in Setup URL
    is a silent no-op for the OAuth web flow.

There is **no API** to register or read callback URLs. Manual, always.

## 3. Matching rules

- **Exact match** (scheme, host, port, path; no trailing slash unless
  registered) for apps created on/after 2026-08-03 with wildcard matching off.
- **Wildcard matching** is on by default for apps created before 2026-08-03
  with a single callback URL. Then: host (excluding subdomain) and port must
  match exactly, and the redirect path must be a **subdirectory** of the
  callback path.

```
CALLBACK https://example.com/path
MATCH    https://example.com/path
MATCH    https://example.com/path/sub
MATCH    https://oauth.example.com/path        (subdomain OK)
FAIL     https://example.com/bar               (not a subdir)
FAIL     https://example.com/                   (not a subdir)
FAIL     https://example.com:8080/path          (port differs)
FAIL     https://other.org/path                 (host differs)
```

A **different host is fatal in every mode** — this is the most common real
cause of `redirect_uri_mismatch` after a domain change.

## 4. Probing is impossible — do not try to be clever

```bash
# ALL of these return the same 302 → /login?client_id=…&return_to=…
curl -sI 'https://github.com/login/oauth/authorize?client_id=Ov23liREAL&redirect_uri=<registered>'
curl -sI 'https://github.com/login/oauth/authorize?client_id=Ov23liREAL&redirect_uri=<garbage>'
curl -sI 'https://github.com/login/oauth/authorize?client_id=Ov23liNOTREAL123'
```

GitHub redirects to its login page **before** validating the client or the
redirect_uri. The negative control cannot fail, so no verdict is possible.
Stop probing; ask the user for the browser evidence instead.

## 5. What to ask the user for

Two artifacts resolve this in one round trip:

1. **The error page screenshot** — distinguishes
   "redirect_uri is not associated" (settings) from an app-side error page.
2. **The authorize URL from the address bar** — it contains the exact
   `client_id` and `redirect_uri` the app emitted. Compare it byte-for-byte
   against what your app produces:

```bash
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/203.0.113.10 Safari/537.36'
curl -s -o /dev/null -D - -A "$UA" "https://<app>/api/auth/github" \
  | grep -i '^location:' \
  | python3 -c 'import sys,urllib.parse as u; q=u.parse_qs(u.urlparse(sys.stdin.read().split(" ",1)[1].strip()).query); print(q["client_id"][0]); print(q["redirect_uri"][0])'
```

If the two match, the app is emitting correctly and the fix is **entirely** in
GitHub settings — say so plainly rather than continuing to debug app code.

## 6. User-facing checklist to hand over

1. Open `https://github.com/settings/developers`
2. Go to the tab matching the app type determined in step 1
3. Find the app whose **Client ID** equals the one in `.env`
4. Set the callback field to exactly what the app emits
5. Save, then retry

Also check, in order of likelihood: the other app type's page was edited; the
"Homepage URL" field was edited instead; an old host (`localhost:5173`, a
previous domain) is still there; trailing slash; wrong account/org.

## 7. Once the callback URL is right, watch for the session-binding bug

A working callback can still produce a wrong-account sign-in: if the handler
looks the user up **by provider id** and issues a session for the found user,
clicking "Connect GitHub" while signed in as someone else can swap identities.
See the SKILL.md rule — bind to the authenticated session, reject if the
identity is already taken.
