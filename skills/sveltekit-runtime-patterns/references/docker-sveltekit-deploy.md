# Docker SvelteKit Deploy Recipes

Session-derived patterns for deploying SvelteKit apps in Docker (Concrete example: the client site, multi-stage `node:22-slim` Dockerfile, SvelteKit SSR adapter).

## Multi-stage Dockerfile Shape (the client site)

```
FROM node:22-slim AS build      # build stage: npm ci → prisma generate → npm run build → npm prune --omit=dev
FROM node:22-slim               # runtime stage: copy build/, node_modules/, prisma/, static/
```

Key facts learned:
- Source is compiled INSIDE the build stage. The runtime container holds only compiled output.
- `docker cp` of a compiled chunk into a running container = no-op for source fixes. Old compiled output persists until image rebuild.
- SvelteKit inlines `$env/static/public` at build time (e.g. `PUBLIC_TURNSTILE_SITE_KEY`), so even the client build is baked from build-time ARG/ENV.

## Live Rebuild Cycle (correct)

```bash
docker compose build app
docker compose stop app && docker compose rm app
docker compose up -d app      # fresh container from the new image
```

Compose treats a running container as "already up" — plain `docker compose up -d` does NOT pull the newly built image. Stop+rm (or `--force-recreate`) is required.

## Verify the Build Actually Landed

Build artifacts live under `/app/build/`. Confirm the new identifier / action / string:

```bash
docker exec <container> grep "updatePaymentStatus" /app/build/server/chunks/entries/pages/admin/orders/_id_/_page.server.ts.js
```

Hashed chunk filenames change per build — `grep` across `/app/build/server` instead of relying on a fixed filename.

## Gotchas

- `docker compose build` can exceed a 180s foreground timeout; run it backgrounded (`background=true`, `notify_on_complete=true`), then wait.
- Terminal may flag docker compose commands as "long-lived server" — split stop/rm from up into separate commands, or run via background.
- SQLite DB lives in a named volume (e.g. `client-site_data`, mount `/data/dev.db`), NOT in the container `node_modules` tree — survives container recreate; don't `docker cp` dev.db into it (see project memory warning).
- A graceful Turnstile/CAPTCHA disable: make the server `verifyTurnstile()` return `true` early. esbuild tree-shakes the now-dead code, so the compiled function becomes a bare `return true`. Re-enable = remove the early return and rebuild.

## Always read the entrypoint log before declaring a deploy done

`docker compose ps` showing `(healthy)` proves only that the process answers HTTP. An
entrypoint that runs `npx prisma db push 2>/dev/null || true` will happily come up
healthy while the schema sync never applied — and, worse, while Prisma printed a
data-loss plan for tables that are NOT empty. The stderr redirect hides both.

```bash
docker compose up -d --force-recreate app
docker logs <container> 2>&1 | tail -30
```

Read for the real error, not just `Listening on ...`. Specifically:
- `⚠️ There might be data loss when applying the changes: • drop ... not empty (N rows)`
  means the push ABORTED and the rows survived. Check the committed schema
  (`git diff <old>..<new> -- prisma/ migrations/`; empty = the warning is drift from an
  OLDER schema) before considering `--accept-data-loss`. Never silence it reflexively.
- Prisma writing only to stderr means any entrypoint redirect hides the whole story.

Then confirm with row counts read straight from the volume, since neither a healthy
container nor a clean HTTP 200 says anything about the schema.

## Env changes in compose need a forced recreate

A new or changed `environment:` entry (a raised `BODY_SIZE_LIMIT`, a new secret) does
not reach the container via `docker restart` or a plain `up -d` — both reuse the existing
container's original env. Use `--force-recreate` and then prove the value landed:

```bash
docker inspect <container> --format '{{range .Config.Env}}{{println .}}{{end}}' | grep <VAR>
```
