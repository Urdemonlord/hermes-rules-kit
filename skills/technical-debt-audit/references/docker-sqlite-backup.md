# Docker SQLite Backup Pattern

Battle-tested pattern for backing up a SQLite database running inside a Docker container using WAL checkpoint + `docker cp` + integrity verification.

## The Problem

SQLite with WAL journal mode writes to three files: `dev.db`, `dev.db-wal`, `dev.db-shm`. Simply `docker cp`-ing the `.db` file can produce an inconsistent state because pending WAL frames aren't checkpointed into the main file. Running `sqlite3` inside the container may not be available (node:22-slim images don't include it). And `better-sqlite3`'s `.backup()` method can fail with connection-not-open errors in certain Node.js versions.

## The Pattern

```bash
#!/bin/bash
set -e

BACKUP_DIR="/path/to/backups"
CONTAINER="container-name"
RETENTION=7  # days
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/db_${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"

# Step 1: Force WAL checkpoint — flush pending changes to main DB file
docker exec "$CONTAINER" node -e "
  const Database = require('better-sqlite3');
  const db = new Database(process.env.DATABASE_FILE || '/data/dev.db');
  db.pragma('wal_checkpoint(TRUNCATE)');
  db.close();
" 2>/dev/null

# Step 2: Copy the checkpointed main DB file to a temp path inside the container
docker exec "$CONTAINER" cp /data/dev.db /tmp/backup_tmp.db 2>/dev/null

# Step 3: Pull the copy out of the container
docker cp "$CONTAINER:/tmp/backup_tmp.db" "$BACKUP_FILE" 2>/dev/null

# Step 4: Cleanup temp file inside container
docker exec "$CONTAINER" rm /tmp/backup_tmp.db 2>/dev/null

# Step 5: Integrity check on the host
if [ -f "$BACKUP_FILE" ]; then
  if sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
    gzip "$BACKUP_FILE"
    echo "[$(date)] Backup created: ${BACKUP_FILE}.gz ($(du -h ${BACKUP_FILE}.gz | cut -f1))"
    find "$BACKUP_DIR" -name "*.db.gz" -mtime +$RETENTION -delete
  else
    rm "$BACKUP_FILE"
    echo "[$(date)] ERROR: Integrity check failed" >&2
    exit 1
  fi
else
  echo "[$(date)] ERROR: docker cp failed" >&2
  exit 1
fi
```

## Cron Setup

```bash
# Add to crontab (runs daily at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 * * * /path/to/backup.sh >> /path/to/backups/backup.log 2>&1") | crontab -

# Verify
crontab -l | grep backup
```

## Pitfalls

1. **Docker volume name ≠ Compose volume name**: In `compose.yaml`, the volume is `client-site_data`, but Docker creates it as `COMPOSE_PROJECT_NAME_client-site_data`. Use `docker inspect` to get the exact `Source` path rather than guessing.

2. **`sqlite3` binary not available in container**: `node:22-slim` images don't include `sqlite3`. Use Node.js with `better-sqlite3` and `PRAGMA wal_checkpoint` instead.

3. **`better-sqlite3` `.backup()` can fail**: In some Node.js/better-sqlite3 version combinations, `.backup()` throws "The database connection is not open" even when the connection is valid. The `cp`-within-container approach is more reliable.

4. **`docker cp` without checkpoint = inconsistent backup**: WAL mode means the `.db` file alone may not have all committed transactions. Always run `PRAGMA wal_checkpoint(TRUNCATE)` first.

5. **Verify, don't trust**: Always run `PRAGMA integrity_check` on the copied file. A gzip'd corrupt backup is worse than no backup — it creates false confidence.

6. **Cron may not be running on VPS**: Some minimal VPS setups don't have cron installed or the daemon isn't running. Verify with `systemctl status cron` or `pgrep cron`. Also verify the backup directory actually has files — a valid crontab entry with a stopped cron daemon produces zero backups.

## Verification

```bash
# Test backup manually first
bash backup.sh

# Check backup was created
ls -la backups/

# Verify cron is scheduled
crontab -l | grep backup

# Verify cron daemon is running
systemctl status cron 2>/dev/null || service cron status 2>/dev/null
```
