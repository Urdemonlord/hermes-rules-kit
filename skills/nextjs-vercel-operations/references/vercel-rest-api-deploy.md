# Vercel REST API — Deploy & Env Management (no CLI)

Vercel CLI in hermes venv is broken (python3 module error). Use REST API directly.
Token lives at `~/.vercel/config.json` → `token` field.

## Get token
```bash
VERCEL_TOKEN=$(cat ~/.vercel/config.json | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
```

## List projects
```bash
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects?limit=50" | python3 -c "
import sys,json
for p in json.load(sys.stdin).get('projects',[]):
    print(p['id'], p.get('name'), p.get('framework'))
"
```

## List env vars
```bash
PROJECT_ID="prj_XXXXX"
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects/$PROJECT_ID/env?decrypt=true" | python3 -c "
import sys,json
for e in json.load(sys.stdin).get('envs',[]):
    print(e['key'], '=', (e.get('value') or '')[:30], '| target:', e.get('target'), '| id:', e.get('id'))
"
```

## Add / patch env var
```bash
# Add (fails with ENV_CONFLICT if key already exists for same target)
curl -s -X POST "https://api.vercel.com/v10/projects/$PROJECT_ID/env" \
  -H "Authorization: Bearer $VERCEL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key":"NEXT_PUBLIC_MAINTENANCE_MODE","value":"true","target":["production"],"type":"encrypted"}'

# Patch (use env ID from list call)
ENV_VAR_ID="XXXXXXXXX"
curl -s -X PATCH "https://api.vercel.com/v10/projects/$PROJECT_ID/env/$ENV_VAR_ID" \
  -H "Authorization: Bearer $VERCEL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value":"false","target":["production"]}'
```

## Trigger production deploy (from any branch)
```bash
REPO_ID="1075539263"  # GitHub repo ID (from projects API link.repoId)
curl -s -X POST "https://api.vercel.com/v13/deployments" \
  -H "Authorization: Bearer $VERCEL_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"roblox-top-up-system\",
    \"project\": \"$PROJECT_ID\",
    \"gitSource\": {
      \"type\": \"github\",
      \"ref\": \"chore/codebase-cleanup-and-refactor\",
      \"repoId\": \"$REPO_ID\"
    },
    \"target\": \"production\"
  }"
# Response has "id" (deployment id), "readyState", "gitSource.sha", "url"
```

## Poll deploy status
```bash
DEPLOY_ID="dpl_XXXXX"
for i in $(seq 1 15); do
  STATE=$(curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
    "https://api.vercel.com/v13/deployments/$DEPLOY_ID" | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('readyState','?'))")
  echo "build: $STATE"
  [ "$STATE" = "READY" ] || [ "$STATE" = "ERROR" ] && break
  sleep 10
done
```

## Delete env var
```bash
ENV_VAR_ID="XXXXXXXXX"  # from list call
curl -s -X DELETE "https://api.vercel.com/v9/projects/$PROJECT_ID/env/$ENV_VAR_ID" \
  -H "Authorization: Bearer $VERCEL_TOKEN"
```

## Static site deploy from a `files:` manifest (no git)

For a plain-HTML project that is not connected to git, push the tree per deploy and let the sha manifest skip re-uploading what Vercel already stores (`~/flow-board/bin/deploy.py` is the working example).

```python
TOKEN=<redacted> / ".vercel" / "config.json").read_text())["token"]
TEAM  = "<team_id>"   # team-owned projects: append ?teamId=<TEAM> to every call
files = [p for p in WEB.rglob("*") if p.is_file() and not (set(p.relative_to(WEB).parts) & {"bin", ".git"})]
body  = {"name": P, "project": P, "target": "production",
         "files": [{"file": str(p.relative_to(WEB)), "sha": sha1hex(p), "size": p.stat().st_size} for p in files]}
try:    dep = api("POST", "/v13/deployments", body)
except ApiError as e:
    missing = set((json.loads(e.body).get("error") or {}).get("missing") or [])
    for entry in body["files"]:                       # retry ONCE, inlining the gaps
        if entry.pop("sha", None) in missing:
            entry.pop("size", None)                   # sha/size are rejected beside data
            entry["data"] = content[WEB / entry["file"]].decode()   # raw text, NOT base64
        elif "sha" not in entry:
            entry["sha"], entry["size"] = blobs[WEB / entry["file"]], len(content[WEB / entry["file"]])
    dep = api("POST", "/v13/deployments", body)
```

- `400 missing_files` + `error.missing` is the normal first-POST answer, not a failure to debug; the sha list is exactly what to inline.
- Inlined entry = `file` + `data` only. `sha` → `should NOT have additional property 'sha'`; `size` → same for `size`.
- `data` must be **raw text**. Base64 is accepted and stored verbatim, so the page serves as base64 (200 OK, plausible size, every grep empty).
- `POST /v2/files` (the documented upload endpoint) rejects every body shape with `invalid_digest: File digest missing` — skip it, use the inline retry.
- Keep internal dirs out of the manifest (`bin/`, `.git`), or the scripts get published.
- No promote API: create with `target: "production"`, else it lands as a preview nothing can promote (`references/vercel-build-status-check.md`).
- Verify on `st["url"]` from the POST response, or `?cb=$RANDOM` on the alias — the alias is CDN-cached and will happily serve the previous build.

## Key gotchas
- `NEXT_PUBLIC_*` env is **build-time inlined** — env PATCH/DELETE alone has no effect; must trigger a new deploy. For deletions: `NEXT_PUBLIC_*` values disappear from the NEXT build, defaulting to `undefined` in the bundle. A quick empty-commit push is the fastest way to trigger the rebuild.
- **Env DELETE ≠ immediate effect:** current production deployment still uses the old baked-in value. Only a new build (triggered by git push or API deploy) picks up the deletion.
- **Preview deploys are SSO-locked on team projects.** Can't `curl` preview URLs from terminal — they redirect to Vercel SSO (`vercel.com/sso-api`). Custom domains bypass SSO. To test without SSO: test on the production custom domain (after env changes) or use local `next start` from a build.
- **No promote API exists.** There is no REST endpoint to promote a preview deploy to production. Use the Vercel dashboard, or trigger a deploy with `target: production` + correct `gitSource`.
- Production deploy `target: "production"` goes to the production domain regardless of source branch.
- If env key exists with wrong target, PATCH the existing record (id from env list), don't POST a second one.
- Repo ID and project ID come from the projects list API response (`link.repoId`, `id`).
- Hobby plan: no concurrent builds — deploy sits QUEUED until current one finishes; poll with timeout.
- User shown as "azazel", team "Azazel's projects" — token is person-scoped.