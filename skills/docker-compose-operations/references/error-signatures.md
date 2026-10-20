# Docker Compose Error Signatures

Quick pattern-matching reference. Grep your terminal output against these.

## Build context blocked by root-owned volume

```
checking context: can't stat '/home/user/onedock/postgres-data'
→ exit code 1, no build output
```

Fix: `.dockerignore` + `chmod 755 <dir>` or `sudo rm -rf <dir>`.

## Init script permission denied

```
/usr/local/bin/docker-entrypoint.sh: running /docker-entrypoint-initdb.d/001-schema.sql
psql: error: /docker-entrypoint-initdb.d/001-schema.sql: Permission denied
```

Fix: `chmod 644 db/schema.sql` or remove init-script mount from compose.yml.

## Migration collision (duplicate type)

```
apply base schema: ERROR: type "user_plan" already exists (SQLSTATE 42710)
```

Fix: remove init-script mount from compose.yml; let Go migration handle schema.

## DNS resolution failure in custom container on compose network

```
ping database: failed to connect to `user=onedock database=onedock`:
hostname resolving error: lookup postgres on 203.0.113.10:53: server misbehaving
```

Fix: ensure postgres container is running and on the same Docker network.
Check with: `docker inspect <container> --format '{{range $net,$v := .NetworkSettings.Networks}}{{$net}} {{end}}'`
