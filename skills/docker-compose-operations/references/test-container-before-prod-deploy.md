# Verifying a new image without upgrading prod

Companion to SKILL.md sections 12 (CSRF/ORIGIN) and 28 (entrypoint `|| true`).
Covers the `:latest` overwrite trap and why a fresh volume is the real test.

## The `:latest` trap

`docker compose build` overwrites the `:latest` tag. The running prod container keeps
serving its **old image ID** (safe), but the next `up -d` on that host silently upgrades
to the new build — even if you never intended to deploy.

```bash
docker inspect <container>-1 --format '{{.Image}}'          # image ID currently running
docker images --format '{{.Repository}}:{{.Tag}} {{.CreatedSince}}' | grep <project>
# tag :latest says "2 minutes ago" while the running ID is 5 days old
```

Record the running image ID **before** any rebuild on a shared host, so you can later prove
prod didn't move.

## Run the new image beside prod

Separate port + separate volume. Never reuse the prod volume, and never `docker cp` a local
dev.db in (SKILL.md section 13bb).

```bash
docker run -d --name <project>-test -p 127.0.0.1:3302:3000 \
  -v <project>test:/data -e DATABASE_URL=file:/data/dev.db \
  -e DATABASE_FILE=/data/dev.db -e NODE_ENV=production \
  -e ORIGIN=http://localhost:3302 -e ADMIN_PASSWORD=<pass> \
  <project>-app:latest
```

`ORIGIN` must match the **test port**, or every form POST 403s (section 12). Curl form
actions as `POST /path?/actionName` with an `Origin` header — a bare `POST /path` returns
404 for a named action.

## A fresh volume is the point, not a side effect

An empty volume runs migrations + seed from scratch, the **only** way to surface
seed/migration drift. Prod with existing data never re-runs seed, so a broken seed can sit
in the repo for months without touching anyone.

Real bug this caught: `prisma/seed.cjs` still inserted a `Product.size` column that had
been deleted from the schema. The entrypoint's `|| true` swallowed the crash, the container
still reported `Listening on`, and the log still printed `Seed complete` — with **0
products** actually inserted.

## Verify by row count, not by the success message

```bash
docker logs <container>-test 2>&1 | grep -iE "seed|error|listening" | head -5   # read from the TOP
docker exec <container>-test node -e "
const D=require('better-sqlite3'); const db=new D('/data/dev.db',{readonly:true});
console.log('Product', db.prepare('SELECT COUNT(*) c FROM Product').get().c)"
```

`tail` hides the crash sitting above `Listening on`. Cross-check counts against what the
seed claimed to write. `sqlite3` is usually absent from these images — go through
`better-sqlite3` via `node -e`.

## Cleanup

```bash
docker rm -f <project>-test && docker volume rm <project>test
```

## Prevention

- Tag builds explicitly (`docker build -t <project>-app:$(git rev-parse --short HEAD)`) so a
  test build can't become an implicit prod upgrade.
- Treat "fresh volume produces expected row counts" as a deploy gate, not a nice-to-have.
- When a change spans both UI and server, drive the full user path over HTTP (login → cart →
  checkout → order detail → admin action) — LSP-clean code can still 500 at runtime.
