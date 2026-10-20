# Vercel build-status check (read-only, via REST API)

Use when the user asks "cek di Vercel build bener atau error" — verifying whether a pushed commit actually built successfully. No CLI needed.

## Prereqs
- Token: `~/.vercel/config.json` → `token` field.
- Project ID + org/team ID come from the linked project:
  - `.vercel/repo.json` in the repo → `projects[0].id`, `projects[0].orgId`
  - or `curl "https://api.vercel.com/v9/projects?limit=50"` and read `id` / `link.repoId`
- **Team-owned projects REQUIRE `&teamId=...` on every request.** Without it you get `{"error":{"code":"could_not_route",...}}`. This is the #1 gotcha — the local `~/.vercel/config.json` token is person-scoped to the team, and the API won't route without the teamId.

## 1. List recent deployments (find the latest)
```bash
TOKEN=<redacted> ~/.vercel/config.json | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
PROJECT_ID="prj_XXXXX"
TEAM_ID="team_XXXXX"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.vercel.com/v6/deployments?projectId=$PROJECT_ID&limit=5&teamId=$TEAM_ID" | python3 -c "
import json,sys
for d in json.load(sys.stdin).get('deployments',[]):
    print(d.get('created'), d.get('uid'), d.get('state'), d.get('meta',{}).get('githubCommitRef',''), d.get('url'))
"
```

## 2. GET one deployment — state + commit meta
```bash
DEP_ID="dpl_XXXXX"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.vercel.com/v13/deployments/$DEP_ID?teamId=$TEAM_ID" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('state:', d.get('status'))           # READY / ERROR / QUEUED / BUILDING
print('url:', d.get('url'))
meta=d.get('meta',{})
print('branch:', meta.get('githubCommitRef'))
print('sha:', meta.get('githubCommitSha'))
print('msg:', meta.get('githubCommitMessage'))
"
```

## 3. Prove it's OUR commit
```bash
cd <repo> && git rev-parse HEAD
# must equal meta.githubCommitSha above
```
Check the commit message too — a READY state for a stale SHA (e.g. an old push that finally finished building) is not proof your latest push built. Match SHA + message + branch, then report.

## 4. Verify the SHIPPED bytes, not just the build (resolving the prod chunk hash)

SHA + `state: READY` proves *your commit built*, not that the browser receives your new client
code. To confirm the latter you must grep the served chunk — and you cannot guess its name: the
local build's hash **differs** from prod's, because build-time `NEXT_PUBLIC_*` inlining changes
the chunk contents and therefore its filename. Fetching the landing HTML does not help either,
since the app chunk is lazy-loaded and absent from it.

Resolve the real name from the **webpack runtime** chunk, whose hash is itself in the HTML:

```bash
# 1. find the webpack runtime chunk from the served HTML
curl -s https://<prod-host>/ | grep -o '/_next/static/chunks/webpack-[a-f0-9]*\.js'

# 2. read its chunk-id → hash map, and pull out the one you want
curl -s https://<prod-host>/_next/static/chunks/webpack-<hash>.js \
  | grep -o '{[^{}]*"<chunkId>":"[a-f0-9]*"[^{}]*}'
# → ...<chunkId>:"<realhash>"...

# 3. fetch that chunk and assert on its contents
curl -s https://<prod-host>/_next/static/chunks/<chunkId>.<realhash>.js | grep -c '<new string>'
```

Which chunk id holds your code: grep the **local** build for a string you added
(`grep -rl '<new string>' .next/static/chunks/`) — the *id* is stable across builds even though
the hash is not.

Assert **both directions** or the check is vacuous: new markers present **and** every removed
marker absent. A `grep` that only finds nothing proves nothing if you fetched the wrong chunk —
confirm the fetch returned 200 with a plausible size first.

## Notes
- `state: READY` means build succeeded; `ERROR` means it failed. `QUEUED` on Hobby plan means it's waiting for the previous build.
- A branch push auto-creates a preview deployment; `main` goes to production. The latest deployment for the pushed branch is the one to inspect.
- This is read-only verification — no env writes, no deploy triggers. For those see `references/vercel-rest-api-deploy.md`.
