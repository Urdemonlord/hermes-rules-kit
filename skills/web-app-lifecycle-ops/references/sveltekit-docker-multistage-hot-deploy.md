# SvelteKit Multi-Stage Docker Hot Deploy

## Problem

SvelteKit app using `@sveltejs/adapter-node` with multi-stage Docker build.
Production image has only compiled output in `/app/build/` — no source, no dev deps.

When frontend-only changes are needed (routes, components, styles), rebuilding the full Docker image is slow (~2-3 min) and unnecessary.

## Fastest path

```bash
# 1. Build locally (same project root as Docker build)
npm run build

# 2. Copy fresh build to running container
docker cp build/ <container>:/app/build

# 3. Restart container
docker restart <container>
```

Total: ~15-30 seconds vs 2-3 min for `docker compose build`.

### Config files that also need copying

When changes touch SvelteKit config, hooks, or app types, copy those too:

```bash
# Source-level files baked into the build
docker cp src/hooks.server.ts <container>:/app/src/hooks.server.ts
docker cp src/app.d.ts <container>:/app/src/app.d.ts
docker cp svelte.config.js <container>:/app/svelte.config.js
```

Note: `hooks.server.ts` and `app.d.ts` are NOT in `build/` — they're referenced at build time but the built output uses the compiled versions. If you change them, you MUST rebuild AND copy `build/` to the container.

## Verification

Check all modified routes return 200:

```bash
curl -s -o /dev/null -w "%{http_code} " http://127.0.0.1:3301/
curl -s -o /dev/null -w "%{http_code} " http://127.0.0.1:3301/about
curl -s -o /dev/null -w "%{http_code} " http://127.0.0.1:3301/products
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3301/products/some-product
```

Spot-check HTML contains expected strings:

```bash
curl -s http://127.0.0.1:3301/ | grep -o 'some-expected-text' | head -1
```

## Root cause: `docker cp` with missing parent dirs

`docker cp` copies FILES, not entire mount trees. If the target directory doesn't exist inside the container (e.g. `/app/src/` was never created in a multi-stage image that only has `/app/build/`), `docker cp` fails with `Could not find the file`. Always create needed directories first:

```bash
docker exec <container> mkdir -p /app/src /app/prisma
docker cp src/hooks.server.ts <container>:/app/src/hooks.server.ts
```

For the build directory itself, prefer:
```bash
docker exec <container> rm -rf /app/build
docker cp local/build/ <container>:/app/build
```

## Note: ORIGIN env var changes

The `ORIGIN` env var affects CSRF origin comparison at runtime. If `ORIGIN` is baked into the Docker image via `ENV` in Dockerfile, `docker restart` won't change it. To override at runtime: `docker run -e ORIGIN=http://new-origin ...` or set in docker-compose `environment:`. Removing ORIGIN by setting to empty string (`-e ORIGIN=""`) crashes the server — `parse_origin("")` throws `Invalid URL`. If CSRF is blocking legitimate requests, prefer `csrf: { checkOrigin: false }` in `svelte.config.js` and rebuild.

## When this works

- **Only for SvelteKit/adapter-node** (the output is self-contained JS in `build/`)
- **Only for frontend / route changes** — no schema migrations, no npm deps
- **Container MUST have the same build output structure** as your local build (same SvelteKit version, same adapter config)
- **Not for SSR-only changes** that involve data loading logic in `+page.server.ts` — those are also in `build/` so it actually works fine for server routes too

## When NOT to use this

- Schema changes (`prisma db push` / migrations)
- New npm packages added
- Adapter config changed
- SvelteKit version mismatch between local and container
- ORIGIN env var changes (requires container recreation with `-e` flag, not just build copy)
