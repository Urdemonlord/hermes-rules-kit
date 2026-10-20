# SQLite SQL Migration Pattern for Docker Volumes

When applying schema changes + data to a running Docker container with SQLite, the safest pattern is:
1. Write `.sql` file on host
2. Copy container DB to local
3. Apply SQL locally
4. Copy back, fix ownership, restart

This avoids repeated overwrites, session invalidation, and password hash loss.

## Full workflow

```bash
# Setup
PROJECT=iki-tenun
CONTAINER=iki-tenun-app-1
APP_UID=999
APP_GID=999
ADMIN_EMAIL=user@example.com
ADMIN_PASSWORD=client-site2026!

# 1. Write migration file
cat > ~/project/scripts/migrate-schema.sql <<'SQL'
-- Create new tables
CREATE TABLE IF NOT EXISTS ProductOption (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  displayName TEXT NOT NULL,
  createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS OptionValue (
  id TEXT PRIMARY KEY,
  optionId TEXT NOT NULL,
  value TEXT NOT NULL,
  displayValue TEXT NOT NULL,
  sortOrder INTEGER DEFAULT 0,
  FOREIGN KEY (optionId) REFERENCES ProductOption(id) ON DELETE CASCADE
);

-- Insert Varian types (Set, Kemeja, Atasan, Skirt)
INSERT OR IGNORE INTO ProductOption (id, name, displayName)
  VALUES ('opt_set', 'set', 'Set'),
         ('opt_kemeja', 'kemeja', 'Kemeja'),
         ('opt_atasan', 'atasan', 'Atasan'),
         ('opt_skirt', 'skirt', 'Skirt'),
         ('opt_size', 'size', 'Ukuran');

-- Insert size values (XS, S, M, L, XL, XXL, CUSTOM)
INSERT OR IGNORE INTO OptionValue (id, optionId, value, displayValue, sortOrder)
  VALUES ('sz_xs', 'opt_size', 'xs', 'XS', 0),
         ('sz_s', 'opt_size', 's', 'S', 1),
         ('sz_m', 'opt_size', 'm', 'M', 2),
         ('sz_l', 'opt_size', 'l', 'L', 3),
         ('sz_xl', 'opt_size', 'xl', 'XL', 4),
         ('sz_xxl', 'opt_size', 'xxl', 'XXL', 5),
         ('sz_custom', 'opt_size', 'custom', 'CUSTOM', 6);
SQL

# 2. Get fresh DB from container (preserves current state + admin)
docker cp $CONTAINER:/data/dev.db /tmp/prod.db
echo "✓ Copied container DB"

# 3. Apply migration locally
sqlite3 /tmp/prod.db < ~/project/scripts/migrate-schema.sql
echo "✓ Applied migration"

# 4. Verify migration (count tables, options)
sqlite3 /tmp/prod.db "SELECT COUNT(*) FROM ProductOption; SELECT COUNT(*) FROM OptionValue;"

# 5. Sync admin password hash (container seed uses env var)
NEW_HASH=$(docker exec $CONTAINER node -e "console.log(require('bcryptjs').hashSync('$ADMIN_PASSWORD', 10))")
sqlite3 /tmp/prod.db "UPDATE User SET passwordHash='$NEW_HASH' WHERE email='$ADMIN_EMAIL';"
echo "✓ Updated admin password hash"

# 6. Copy back to container (ONCE)
docker cp /tmp/prod.db $CONTAINER:/data/dev.db
echo "✓ Copied DB back to container"

# 7. Fix file ownership (docker cp uses host user UID)
docker exec -u root $CONTAINER chown $APP_UID:$APP_GID /data/dev.db
echo "✓ Fixed ownership"

# 8. Restart container (clears in-memory caches, WAL checkpoint)
docker restart $CONTAINER
echo "✓ Container restarted"

# 9. Verify at user surface
sleep 3
curl -s -o /dev/null -w "Status: %{http_code}\n" "http://localhost:3301/"
echo "✓ Homepage responds"
```

## Idempotent SQL file guidelines

- **Use `IF NOT EXISTS`** on CREATE TABLE, CREATE INDEX
- **Use `INSERT OR IGNORE`** on data (won't crash if row exists)
- **Transactions not needed** for SQLite in Docker (writes are implicit)
- **Add comments** for future debugging — migrations are read over time
- **Test locally first** before copying to container

```sql
-- ✓ Safe — won't fail if run twice
CREATE TABLE IF NOT EXISTS MyTable (id TEXT PRIMARY KEY);
INSERT OR IGNORE INTO MyTable VALUES ('id1');

-- ✗ Unsafe — crashes on second run
CREATE TABLE MyTable (id TEXT PRIMARY KEY);
INSERT INTO MyTable VALUES ('id1');
```

## When to use this pattern vs alternatives

| Task | Use pattern | Why |
|------|-------------|-----|
| Add 1-2 columns to existing table | SQL file | Repeatable, debuggable |
| Insert 50+ products from Shopee | SQL file | All-or-nothing, version-controlled |
| Fix a few incorrect prices | `docker exec node -e` (section 13c) | Faster, no copy-back |
| Full schema migration (>5 table changes) | SQL file + Prisma | SQL file for schema, then `prisma generate` |
| Runtime user upload handling | Separate volume + dynamic route (section 23) | Not a DB change |

## Pitfalls

- **Container DB is source of truth** — always copy FROM container, not FROM local dev.db (unless intentionally reverting)
- **Password hash MUST be synced** — container seed generates hash from `ADMIN_PASSWORD` env var. After copy, regenerate the hash to match what was used at container startup. Otherwise: "Email atau password salah"
- **Don't forget `chown`** — `docker cp` copies with host UID/GID. Container user can't write → "readonly database" on next login
- **WAL checkpoint before large copy** — see `references/sqlite-docker-backup.md` for details
- **One copy per migration** — copy once after all local edits complete. Multiple copy cycles = multiple password resets, session loss, confusion

## Verification after copy

```bash
# Verify migration applied
sqlite3 /tmp/prod.db "SELECT COUNT(*) FROM ProductOption;"
# → 5 (Set, Kemeja, Atasan, Skirt, Size)

# Verify password works
curl -s -X POST http://localhost:3301/login \
  -d "email=user@example.com&password=<redacted>" \
  -o /dev/null -w "Status: %{http_code}\n"
# → 200 or 302 (redirect to homepage after login) = success

# Verify no readonly errors in logs
docker logs iki-tenun-app-1 2>&1 | grep -i "readonly\|permission denied"
# → (empty = success)
```

## the client site specifics

**Admin user:**
- Email: `user@example.com` (seeded at `docker compose up -d`)
- Password: `client-site2026!` (from compose.yaml `ADMIN_PASSWORD` env)

**App user in container:**
- UID/GID: `999:999` (node user)
- Must own `/data/dev.db` and `/app/static/images/products/` for writes

**Database location:**
- `/data/dev.db` (Docker volume mount `client-site_data:/data`)
- Prisma migration status: `npx prisma migrate status`
- Size column exists (added in section 13 of devops skill): `PRAGMA table_info(Product) | grep size`

**Common migrations for the client site:**
1. Add product categories (Set, Kemeja, Atasan, Skirt) — see section 11 of main skill
2. Add size variants (XS-CUSTOM) + ProductOption + OptionValue — this file
3. Fix image URLs (.png → .webp) — see `references/sveltekit-image-optimization.md`
4. Reset admin password after lost session — `docker exec ... UPDATE User SET passwordHash='...'`
