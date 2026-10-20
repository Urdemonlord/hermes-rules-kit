# SQLite volume schema drift in Docker-backed apps

## Symptom
- A container is healthy, but a page returns 500 with `SQLITE_ERROR` / `no such column`.
- The live DB file is mounted in a Docker volume, so the authoritative schema is the volume file, not the checked-in local copy.

## What to verify
1. Find the exact DB path/volume used by the running container.
2. Inspect the live schema from that file (`PRAGMA table_info(...)` or equivalent).
3. Compare against raw SQL in route/loaders, not just ORM models.
4. Check for camelCase vs snake_case drift in raw queries.
5. Verify the app is not reading a stale local `dev.db` copy.

## Example pattern
- Model field: `isActive`
- Raw SQL bug: `WHERE p.is_active = 1`
- Result: runtime 500 even though the app and DB are both otherwise healthy.

## Probe
```bash
python3 - <<'PY'
import sqlite3, json
conn = sqlite3.connect('/path/to/dev.db')
cur = conn.cursor()
cur.execute('PRAGMA table_info("Product")')
print(json.dumps(cur.fetchall(), indent=2))
PY
```
