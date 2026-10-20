# Docker-Proxy Ghost: Port Blocked After Container Disappears

## Symptom

- A container (e.g., `platform-suite-postgres`) is **completely gone** — `docker ps -a` shows nothing with that name.
- But `docker compose up -d` fails with:
  ```
  Error response from daemon: Bind for 0.0.0.0:5432 failed: port is already allocated
  ```
- `ss -tlnp | grep <port>` shows `docker-pr` (docker-proxy) processes still listening, even though the container they belonged to no longer exists.

## Root Cause

When a Docker container is removed (via `docker rm`, `docker compose down`, or by Docker daemon recovering from a crash), the **docker-proxy** process that was forwarding the host port into the container can **survive** as a zombie/ghost. This happens most often when:

- The container was removed while the docker-proxy was mid-operation.
- Docker daemon was restarted while containers were running on a bridge network.
- A `docker system prune` or container removal raced with the proxy teardown.

The port remains held by a detached `docker-pr` PID with no parent container.

## Diagnosis

### 1. Confirm the container is truly gone
```bash
docker ps -a --filter name=<container_name> --format 'table {{.Names}}\t{{.Status}}'
# Empty output means the container does not exist
```

### 2. Find the port listener
```bash
ss -tlnp | grep <PORT>
# Example output:
# LISTEN 0 4096 0.0.0.0:5432 0.0.0.0:*
# LISTEN 0 4096   [::]:5432     [::]:*
```

### 3. Identify the owning process
```bash
sudo lsof -i :<PORT>
# Example output:
# COMMAND      PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
# docker-pr 3534654   root    7u  IPv4 ...     0t0  TCP *:postgresql (LISTEN)
# docker-pr 3534659   root    7u  IPv6 ...     0t0  TCP *:postgresql (LISTEN)
```
Two PIDs: one for IPv4, one for IPv6 — always kill both.

### 4. Confirm orphan status
```bash
# Check if any running container references the same port mapping
docker inspect $(docker ps -aq) --format '{{.Names}} {{range $p, $c := .NetworkSettings.Ports}}{{$p}} {{end}}' | grep <PORT>
# Empty output = ghost
```

## Fix

```bash
# Kill the docker-proxy ghosts
sudo kill <PID_IPv4> <PID_IPv6>

# Verify port is free
ss -tlnp | grep <PORT>
# Should return nothing

# Now restart the stack
docker compose up -d
```

## Prevention

### In compose configs
No direct prevention — this is a Docker daemon-level race condition. Mitigation:

1. **Graceful shutdown:** Use `docker compose down` (not `docker rm`) for compose-managed containers.
2. **Health-check before up:** If a watchdog script restarts compose services, add a port-clear step before `docker compose up -d`:
   ```bash
   PORT=<PORT>
   PIDS=$(lsof -ti :$PORT 2>/dev/null || true)
   if [ -n "$PIDS" ]; then
     echo "Killing ghost process(es) on port $PORT: $PIDS"
     kill $PIDS
     sleep 1
   fi
   ```

### In watchdog scripts
If a `no_agent` watchdog script restarts Docker services, add a port pre-clearing loop for known compose ports:

```bash
for PORT in 5432 3100 3101; do
  PIDS=$(lsof -ti :$PORT 2>/dev/null || true)
  [ -n "$PIDS" ] && kill $PIDS
done
sleep 1
docker compose up -d
```

This is safe because:
- If there's no ghost, `lsof -ti` returns empty → no-op.
- If there's a real process (the intended container), that process will be killed — but you're about to recreate it anyway via `docker compose up -d`.

Be careful not to kill non-Docker processes on that port. The pattern above assumes the port is exclusively managed by Docker compose.

## Pitfall: docker-proxy reappears mid-connection

After killing the ghost, the port may briefly appear free, but a subsequent `docker compose up -d` can fail again if another stale docker-proxy process was still mid-teardown. In that case:

1. Check `ss -tlnp` again — a new ghost PID may have appeared.
2. Kill the new PID.
3. Try `docker compose up -d` a second time.
4. If it happens repeatedly, restart Docker daemon via nsenter:
   ```bash
   docker run --rm --pid=host --privileged alpine \
     sh -c 'nsenter -t 1 -m -u -i -n -p -- sh -c "systemctl restart docker"'
   ```
   (This restarts ALL Docker containers — use only as last resort.)

## Relation to other references

- **`vps-runtime-recovery-matrix.md`** covers compose revival with surviving DB containers (name conflict). This reference covers port conflict from orphaned proxy processes (a different mechanism that produces the same `port already allocated` error).
- **`vps-stability-hardening.md`** covers the watchdog pattern. The port pre-clearing mitigation above should be integrated into watchdog scripts that manage Docker compose services on shared VPS ports.
