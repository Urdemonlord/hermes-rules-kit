# SQLite Data Modification in Docker Volumes

## Problem

You need to edit product data, prices, or other records directly in the SQLite database of a running Docker container. The container uses a **Docker-managed named volume** (not a host bind-mount), so the local `dev.db` or `prisma/dev.db` in your repo is stale — changes there don't affect production.

Can't install `sqlite3` inside the container (Debian slim, no `apk`/`apt`). But the host has `sqlite3`.

## The Pattern

```bash
# 1. Find the actual DB — check volume mounts
docker inspect <container> --format '{{json .Mounts}}' | python3 -m json.tool
# Look for "Destination": "/data" or similar

# 2. Copy the live DB to host
docker cp <container>:/data/dev.db /tmp/prod.db

# 3. Verify it's the real one (not the local stale copy)
sqlite3 /tmp/prod.db "SELECT id, name, price FROM Product;"
# Should show production products, not just dev set

# 4. Edit data — INSERT, UPDATE, DELETE
sqlite3 /tmp/prod.db <<'SQL'
INSERT INTO Product (id, name, slug, price, stock, categoryId, isActive, createdAt, updatedAt)
VALUES ('prod_new_item', 'New Item', 'new-item', 299000, 1,
  (SELECT id FROM Category LIMIT 1), 1, datetime('now'), datetime('now'));
SQL

# 5. Copy modified DB back into container
docker cp /tmp/prod.db <container>:/data/dev.db

# 6. Restart container so in-memory caches refresh
docker restart <container>

# 7. Verify at the user surface
curl -s http://localhost:<PORT>/ | grep -o 'new-item'
```

## CRITICAL: WAL checkpoint before copy

If the container was writing to the DB when you copy, the `-wal` and `-shm` files may have unflushed data. Safe approach:

1. Stop the container first (clean shutdown checkpoints WAL automatically):
```bash
docker stop <container>
docker cp <container>:/data/dev.db /tmp/prod.db
# ... modify ...
docker cp /tmp/prod.db <container>:/data/dev.db
docker start <container>
```

2. Or if the app uses better-sqlite3 (Node):
```bash
docker exec <container> node -e "
  const Database = require('better-sqlite3');
  const db = new Database('/data/dev.db');
  db.pragma('wal_checkpoint(TRUNCATE)');
  db.close();
" 2>/dev/null
docker cp <container>:/data/dev.db /tmp/prod.db
```

3. Or (least reliable) copy all three files:
```bash
docker cp <container>:/data/dev.db /tmp/prod.db
docker cp <container>:/data/dev.db-wal /tmp/prod.db-wal 2>/dev/null || true
docker cp <container>:/data/dev.db-shm /tmp/prod.db-shm 2>/dev/null || true
# Modify /tmp/prod.db with sqlite3
docker cp /tmp/prod.db <container>:/data/dev.db
```

## Diagnostic: local vs production DB mismatch

When you edit the local `dev.db` but the container uses a volume:

```bash
# Local has the new products
sqlite3 ~/iki-tenun/dev.db "SELECT count(*) FROM Product;"
# → 20

# Production doesn't have them
docker cp <container>:/data/dev.db /tmp/prod.db
sqlite3 /tmp/prod.db "SELECT count(*) FROM Product;"
# → 13 (or different number)
```

## When NOT to use this pattern

- Schema changes (add column, rename table) → use `docker cp schema.prisma + docker exec npx prisma db push` (see `references/prisma-schema-change-running-container.md`)
- Large batch updates → write a migration or admin UI operation instead
- Production critical data → prefer app-level admin panel to ensure validation and triggers fire. Direct SQL bypasses app hooks.

## One-shot inject script template

```bash
#!/bin/bash
set -e
CONTAINER="$1"
[ -z "$CONTAINER" ] && { echo "Usage: $0 <container-name>"; exit 1; }

TMP=$(mktemp /tmp/db-XXXXXX.db)
docker cp "$CONTAINER:/data/dev.db" "$TMP"

# Modify via heredoc
sqlite3 "$TMP" <<'SQL'
INSERT OR IGNORE INTO Product (id, name, slug, price, stock, categoryId, isActive, createdAt, updatedAt)
VALUES ('prod_pusaka_blazer', 'Pusaka Blazer', 'pusaka-blazer', 437000, 1,
  (SELECT id FROM Category LIMIT 1), 1, datetime('now'), datetime('now'));
SQL

docker cp "$TMP" "$CONTAINER:/data/dev.db"
rm -f "$TMP"
docker restart "$CONTAINER"
echo "Done. Verify with: curl -s http://localhost:3301/ | grep pusaka"
```
