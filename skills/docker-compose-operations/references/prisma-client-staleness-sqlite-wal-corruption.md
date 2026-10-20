# Prisma Client Staleness & SQLite WAL Corruption

## Prisma Client Staleness in Docker Builds

### Symptom
```
Invalid `prisma.order.create()` invocation:
The column `shippingCourier` does not exist in the current database.
```
`prisma/schema.prisma` has the column. `sqlite3 .schema "Order"` shows it. `npx prisma db push` says "already in sync". But the app still crashes.

### Root cause
`prisma generate` runs at npm install time (`postinstall`). The Docker image's `node_modules/@prisma/client` was built against an older schema. Prisma client validates columns against its own static type map — not the live DB schema.

### Fix
```bash
docker exec -e DATABASE_URL=file:/data/dev.db <container> npx prisma generate
docker restart <container>
# ~400ms, no rebuild needed
```

### Prevention
Add `prisma generate` to the start script:
```json
"start": "prisma generate && node build/index.js"
```
Or `docker compose build --no-cache` after any schema change.

---

## SQLite WAL Corruption from `docker cp`

### Symptom
After `docker cp <container>:/data/dev.db /tmp/dev.db` + restore:
```
database disk image is malformed
```
But `sqlite3 /tmp/dev.db "PRAGMA integrity_check"` says `ok`.

### Root cause
SQLite WAL mode uses three files: `dev.db`, `dev.db-wal`, `dev.db-shm`. `docker cp` copies only `dev.db`. Without the WAL, the copied file is stale.

### Detection
```bash
sqlite3 <db> "PRAGMA journal_mode;"    # → wal
sqlite3 <db> "PRAGMA wal_checkpoint;"  # → malformed if WAL missing
```

### Fix
```bash
# Checkpoint WAL into main DB before copy
docker exec <container> sqlite3 /data/dev.db "PRAGMA wal_checkpoint(TRUNCATE);"
docker cp <container>:/data/dev.db /tmp/dev.db

# Alternative: sqlite3 backup
docker exec <container> sh -c 'sqlite3 /data/dev.db ".backup /tmp/backup.db"'
docker cp <container>:/tmp/backup.db /tmp/dev.db

# Alternative: stop container first (clean shutdown checkpoints)
docker stop <container>
docker cp <container>:/data/dev.db /tmp/dev.db
docker start <container>
```

### Prevention
- Always checkpoint or `.backup` before copying SQLite from containers.
- Never copy individual files from a WAL-mode volume — copy the entire directory.
- For backup scripts: use `sqlite3 <db> ".backup <dest>"`, never bare `docker cp`.
