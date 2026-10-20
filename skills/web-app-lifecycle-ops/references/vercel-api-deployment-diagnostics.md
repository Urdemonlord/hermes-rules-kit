# Vercel API — Deployment Diagnostics

Quick-reference for diagnosing Vercel deployment failures via API using `$VERCEL_TOKEN`.

## Prerequisites

```bash
source ~/.hermes/.env 2>/dev/null  # exports VERCEL_TOKEN
```

## 1. List projects → find project ID

```bash
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects?limit=20" | \
  python3 -c "import sys,json; [print(f'{p[\"name\"]}: {p[\"id\"]}') for p in json.load(sys.stdin).get('projects',[])]"
```

## 2. List recent deployments for a project

```bash
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v6/deployments?limit=5&projectId=prj_xxx" | \
  python3 -c "
import sys,json
for dep in json.load(sys.stdin)['deployments']:
    commit = dep['meta'].get('githubCommitMessage','?')[:60]
    state = dep.get('readyState','?')
    error = dep.get('errorCode','')
    print(f\"{dep['uid'][:12]} | {state:8s} | {error:15s} | {commit}\")"
```

## 3. Check deployment state and error details

```bash
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v13/deployments/dpl_xxx" | \
  python3 -c "
import sys,json,datetime
d=json.load(sys.stdin)
print('State:', d.get('readyState'))
print('Error Code:', d.get('errorCode'))
print('Error Msg:', d.get('errorMessage'))
if d.get('buildingAt'): print('Build:', datetime.datetime.fromtimestamp(d['buildingAt']/1000))
if d.get('ready'): print('Ready:', datetime.datetime.fromtimestamp(d['ready']/1000))"
```

## 4. Get full build log with error lines

```bash
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v1/deployments/dpl_xxx/events?limit=500" | \
  python3 -c "
import sys,json
for e in json.load(sys.stdin):
    t = e.get('text','') or e.get('payload','') or ''
    if 'Type error' in t or 'Error:' in t:
        print(str(t)[:500])"
```

## 5. Poll until READY or ERROR

```bash
id="dpl_xxx"
for i in 1 2 3 4 5; do
  STATUS=$(curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
    "https://api.vercel.com/v13/deployments/$id" | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('readyState','?'))")
  echo "[$i] $STATUS"
  echo "$STATUS" | grep -q "READY\|ERROR" && break
  sleep 15
done
```

## 6. Build alias/domain info

The `inspectorUrl` field from the deployment response links to the Vercel web dashboard:
```
https://vercel.com/<team>/<project>/<deployment-id>
```

The `url` field is the preview URL (often returns 401 with Vercel Authentication):
```
<project>-<random>.vercel.app
```

The production domain is the custom domain (e.g. `meowlabs.id`). Use `curl -sL` (follow redirects) for production verification.

## Typical error patterns

| errorCode | Meaning | Likely fix |
|-----------|---------|------------|
| `lint_or_type_error` | TypeScript type error | Run `npx tsc --noEmit` locally (Turbopack build skips type checks). Add missing required fields to interfaces. |
| `BUILD_UTILS_SPAWN_MODULE_NOT_FOUND` | Missing dependency | Check `package.json` — add missing package. |
| Exit code 1 (npm run build) | General build failure | Get the full event log (step 4) to see the actual compile error. |

## Vercel deploy (CLI, when not connected to GitHub auto-deploy)

```bash
source ~/.hermes/.env 2>/dev/null
npx vercel deploy --prebuilt --token "$VERCEL_TOKEN" --prod --yes
```

## Verification on production

```bash
for route in "" "/bansos-ai" "/api-ai-gratis" "/open-source"; do
  code=$(curl -sL -o /dev/null -w "%{http_code}" --max-time 30 "https://yourdomain.com/resources$route")
  echo "GET /resources$route → $code"
done
```
