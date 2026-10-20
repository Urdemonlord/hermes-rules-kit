# SvelteKit POST Body Size Limit (413 Payload Too Large)

## Problem
SvelteKit adapter-node has a default `BODY_SIZE_LIMIT` of **512KB**. File uploads, bulk form submissions, or multi-image product edits fail with HTTP 413.

## Root Cause
- The `@sveltejs/adapter-node` handler reads the env var `BODY_SIZE_LIMIT` (default `512K`)
- This limit is passed to `bodySizeLimit` in `getRequest()` from `@sveltejs/kit/node`
- Prisma `$queryRawUnsafe()` and form actions both respect this limit

## Solution: Set BODY_SIZE_LIMIT in Docker Compose

**compose.yaml:**
```yaml
services:
  app:
    environment:
      - BODY_SIZE_LIMIT=${BODY_SIZE_LIMIT:-10M}  # Default 10MB for uploads
```

**Dockerfile (build stage):**
```dockerfile
ARG PUBLIC_TURNSTILE_SITE_KEY
ENV PUBLIC_TURNSTILE_SITE_KEY=${PUBLIC_TURNSTILE_SITE_KEY}
# No need to pass BODY_SIZE_LIMIT here — it's runtime-only
```

## Verification
```bash
# Container should accept payloads up to 10MB
curl -X POST http://localhost:3301/api/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@large-image.jpg"  # Works if < 10MB
```

## The limit is a THREE-tier budget, not one number

Any of the tiers can emit 413, so raising one and still getting 413 just means the
untouched tier is now the ceiling. Keep them ordered:

```
client-side budget  <=  BODY_SIZE_LIMIT (adapter-node)  <=  nginx client_max_body_size
```

- **Client-side** (a `MAX_UPLOAD_BYTES` constant in a shared util): total budget for one
  request. Keep it below the others so oversized submissions are rejected in the
  browser with a readable message instead of an opaque 413.
- **adapter-node** (`BODY_SIZE_LIMIT`): the Node-side ceiling.
- **nginx**: defaults to `1m`, so a SvelteKit limit raised past 1M stays unreachable
  through nginx until `client_max_body_size` is raised too. Put it inside the `server`
  block alongside the SSL directives.

## compose env changes need a RECREATE, not a restart

`BODY_SIZE_LIMIT` is read from the container's env at process start. `docker restart`
reuses the container's ORIGINAL env, so a value just added to `compose.yaml` is silently
absent — and plain `docker compose up -d` misses it too, since compose compares the image
tag rather than the changed config. Use `up -d --force-recreate`, then prove the value
landed:

```bash
docker inspect <container> --format '{{range .Config.Env}}{{println .}}{{end}}' | grep BODY_SIZE_LIMIT
```

Verify upload deploys at BOTH tiers: POST to `http://127.0.0.1:<port>/path` (adapter-node)
and the same POST through the public domain (nginx). A passing loopback test alone hides
a still-1m nginx.

## References
- Handler: `node_modules/@sveltejs/adapter-node/files/handler.js` line 25: `const body_size_limit = parse_as_bytes(env('BODY_SIZE_LIMIT', '512K'))`
- Type: `node_modules/@sveltejs/kit/types/index.d.ts` line 3146: `bodySizeLimit?: number`
