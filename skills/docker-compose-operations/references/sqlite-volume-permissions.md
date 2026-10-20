# SQLite Volume Permissions: UID Mismatch in Docker

## Symptom

```
Invalid `prisma.setting.upsert()` invocation:
attempt to write a readonly database
```

But `ls -la /data/dev.db` inside the container shows `rw-r--r--`. Or `prisma db push` fails with the same error even though the schema is valid.

## Root Cause

The Docker container runs as a non-root user (`app`, UID 999). The Docker volume directory on the host is owned by a different user (e.g., `ubuntu`, UID 1000). Docker mounts the volume with the host's ownership, so the container user (UID 999) can't write to files owned by UID 1000.

### Why it's subtle

- `ls -la` inside the container shows `rw` for "other" if world-writable — misleading
- `prisma db push` from the HOST works fine (host user owns the files)
- `prisma db push` inside the CONTAINER fails (app user ≠ file owner)

## Detection

```bash
# 1. Check container user
docker exec <container> id app
# uid=999(app) gid=999(app)

# 2. Check host file ownership
sudo ls -la /var/lib/docker/volumes/<project>_data/_data/
# -rwxr-xr-x 1 ubuntu netdev 278528 ... dev.db
#   ^^^^^ host user (UID 1000) owns it, container user (UID 999) can't write

# 3. Verify the mismatch
docker exec <container> sh -c "touch /data/test && rm /data/test" 2>&1
# touch: cannot touch '/data/test': Permission denied
```

## Fix

```bash
# From the host, fix ownership to match container user
sudo chown -R 999:999 /var/lib/docker/volumes/<project>_data/_data/
sudo chmod -R 755 /var/lib/docker/volumes/<project>_data/_data/

# Then retry inside container
docker exec <container> npx prisma db push
```

### After fix
```
drwxr-xr-x 2 dnsmasq systemd-journal   4096 ... .
-rwxr-xr-x 1 dnsmasq systemd-journal 278528 ... dev.db
```
`dnsmasq` = UID 999 on host, `systemd-journal` = GID 999. Container user `app` (999:999) now has write access.

## Prevention

### Option A: Entrypoint fix (recommended)
```sh
#!/bin/sh
# Fix permissions before starting (container runs as root briefly? No — app user can't chown)
# Better: use the Dockerfile RUN chown, but volume mounts override it
# SOLUTION: Make the Dockerfile do chown AND keep the volume writable from host
```

### Option B: Dockerfile `USER` + `chown` at build
```dockerfile
RUN mkdir -p /data && chown -R app:app /data
```
This works for the image layer, but Docker volume mounts override the ownership at runtime. The entrypoint must re-apply chown at container start.

### Option C: Start container as root, chown, then drop to app (complex)
Not recommended — security best practice is non-root user.

### Option D: Match host UID to container UID at provision time (simplest)
```bash
# When setting up the VPS:
sudo useradd -u 999 app  # match container UID
# Or: sudo chown 999:999 /data/volumes after each docker compose up
```

## Common Scenario

This hits when:
1. First container start creates the volume with root ownership
2. Dockerfile RUN chown fixes it for the image layer
3. Subsequent restarts override with host ownership
4. Schema changes need `prisma db push` → fails with "readonly"

## Quick Recovery

```bash
# Always works — fix from host side
sudo chown -R 999:999 /var/lib/docker/volumes/*/_data/ 2>/dev/null
sudo chmod -R 755 /var/lib/docker/volumes/*/_data/ 2>/dev/null
docker restart <container>
```
