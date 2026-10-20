# SQLite Docker Backup Pattern

## Problem

Backing up SQLite database from a running Docker container without corruption (WAL mode).

## The Safe Pattern

SQLite in WAL mode has 3 files: `dev.db`, `dev.db-wal`, `dev.db-shm`. A plain `docker cp` only copies `dev.db` — the copy is stale and may be corrupt.

### Steps

1. Force WAL checkpoint to flush pending writes to the main DB file
2. Copy the DB to a temp location inside the container
3. Pull the copy out via `docker cp`
4. Verify with integrity check
5. Gzip for storage

### Script

```bash
#!/bin/bash
set -e

BACKUP_DIR="/path/to/backups"
CONTAINER="my-app-1"
RETENTION=7

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/mydb_${TIMESTAMP}.db"

# 1. Force WAL checkpoint via better-sqlite3 (Node)
docker exec "$CONTAINER" node -e "
  const Database = require('better-sqlite3');
  const db = new Database('/data/dev.db');
  db.pragma('wal_checkpoint(TRUNCATE)');
  db.close();
" 2>/dev/null

# 2. Copy inside container
docker exec "$CONTAINER" cp /data/dev.db /tmp/backup.db 2>/dev/null

# 3. Pull out
docker cp "$CONTAINER:/tmp/backup.db" "$BACKUP_FILE" 2>/dev/null

# 4. Cleanup temp file
docker exec "$CONTAINER" rm /tmp/backup.db 2>/dev/null

# 5. Verify + gzip
if [ -f "$BACKUP_FILE" ]; then
    if sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
        gzip "$BACKUP_FILE"
        echo "[$(date)] Backup created: ${BACKUP_FILE}.gz"
        find "$BACKUP_DIR" -name "mydb_*.db.gz" -mtime +$RETENTION -delete
    else
        rm "$BACKUP_FILE"
        echo "[$(date)] ERROR: Integrity check failed"
        exit 1
    fi
fi
```

### Cron

```bash
# Daily at 3 AM
0 3 * * * /path/to/backup.sh >> /path/to/backups/backup.log 2>&1
```

## Pitfalls

- **Container has no sqlite3 binary**: Use Node with `better-sqlite3` for WAL checkpoint instead.
- **`docker cp` without WAL checkpoint**: Results in stale/corrupt copy. Always checkpoint first.
- **`sqlite3 .backup` not available**: The `.backup` command requires sqlite3 CLI. `better-sqlite3`'s `db.backup()` method may throw `TypeError: The database connection is not open` — use the checkpoint + cp pattern instead.
- **Volume name mismatch**: Docker Compose prefixes volume names with project directory name. Check `docker inspect <container> --format '{{json .Mounts}}'` to find the actual volume name.
- **Permission denied on host DB path**: Docker volumes are root-owned. Use `docker cp` instead of direct filesystem access.
