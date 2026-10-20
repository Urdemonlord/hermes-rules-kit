# Production deploy review checklist (Vercel + Next.js)

Use when deploying a refactor/fix branch to production and verifying it's live + secure. Combines deploy status, SHA match, and header/endpoint audit into one pass.

## Step 1: Vercel API — prod deploy status + SHA match

```bash
TOKEN=<redacted> ~/.vercel/config.json | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
PROJECT_ID="prj_W6o3dxyUtXBKLNVKeoWtM5vDVVJb"
TEAM_ID="team_z63pBlfbjzXS6e1iI9bKjs7O"
# Production deployments only (target=production)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.vercel.com/v6/deployments?projectId=$PROJECT_ID&target=production&limit=1&teamId=$TEAM_ID" \
  | python3 -c "
import json,sys
dep=json.load(sys.stdin)['deployments'][0]
m=dep.get('meta',{})
print('sha:', m.get('githubCommitSha'))
print('branch:', m.get('githubCommitRef'))
print('msg:', m.get('githubCommitMessage','')[:80])
print('url:', dep.get('url'))
"
# Must match: cd <repo> && git rev-parse HEAD
```

Wait 45–90s after push for build to complete. Poll until `state: READY` or `ERROR`.

## Step 2: Security header audit

```bash
# Headers show up even on 307 redirect responses (middleware applies to all return paths)
curl -s -I --max-time 10 https://www.storefront.example/robux-5-hari 2>/dev/null \
  | grep -iE 'HTTP|x-frame|x-content|x-xss|referrer|permissions|cross-origin|strict'
```

Expected (if middleware has security headers):
```
HTTP/2 307
x-frame-options: DENY
x-content-type-options: nosniff
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin
permissions-policy: camera=(), microphone=(), geolocation=()
cross-origin-opener-policy: same-origin
```

If only `strict-transport-security` shows: headers not yet set in middleware.

## Step 3: API auth probe

Verify sensitive endpoints reject unauthenticated calls:

```bash
# Admin endpoints must return 401 without token
curl -s -w '\nHTTP:%{http_code}' https://www.storefront.example/api/admin/stats 2>/dev/null | tail -2
# Expected: {"error":"Missing token","code":"UNAUTHORIZED"} + 401

# Health endpoint must be reachable (it's allowlisted through maintenance)
curl -s https://www.storefront.example/api/health 2>/dev/null | head -1
# Expected: {"status":"ok",...}

# Public data endpoint must work
curl -s https://www.storefront.example/api/games 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('games',[])),'games')"
```

## Step 4: Maintenance mode check (if applicable)

```bash
curl -s -I --max-time 10 https://www.storefront.example/robux-5-hari 2>/dev/null | grep -i location
# Expected during maintenance: location: /maintenance
# Expected when live: no location header (page renders directly)
```

## Pitfall: Vercel production deploy ≠ latest push
- Production deploy list uses `target=production`, NOT `branch=main`. A push to `main` starts a production deploy, but the list may still show the previous one until the new one completes.
- When checking, verify `githubCommitSha` matches `git rev-parse HEAD`. A `READY` state for an old SHA means the latest hasn't finished yet.

## Pitfall: `NEXT_PUBLIC_*` env — maintenance mode
- `NEXT_PUBLIC_MAINTENANCE_MODE` is build-time only. Changing it in Vercel dashboard takes effect only on next deploy. Toggle the env, then trigger a redeploy (or wait for the next push).
