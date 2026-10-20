# Systemd-managed Next.js apps: single-supervisor rule and node_modules dependency

Use this when a Node/Next.js app on a VPS appears to be "already running" but a second supervisor (often PM2) fails with `EADDRINUSE`, or when a cleanup removed `node_modules` and the service later fails only on restart.

## Durable lessons

1. **Pick one supervisor as source of truth**
   - If `systemd --user` already runs the app, do not also run it under PM2.
   - Duplicate supervisors for the same app and port create false outage signals: the app may be healthy under systemd while PM2 loops with `EADDRINUSE`.

2. **Verify the real owner of the port before "fixing" the app**
   - Check the bound port and process owner first.
   - Then inspect the service unit to confirm the working directory and `ExecStart` path.
   - For systemd-managed user services, `systemctl --user status <service>` is the source of truth, not PM2 status.

3. **Deleting `node_modules` can be a delayed failure, not an immediate one**
   - A running Next.js process can stay alive after `node_modules` is deleted.
   - But the next restart will fail if `ExecStart` points into `node_modules`, e.g. `.../node_modules/next/dist/bin/next start`.
   - Therefore blanket `node_modules` cleanup is unsafe on live VPS apps unless you first identify which services still depend on local package trees.

4. **Recovery pattern**
   - Restore dependencies with `npm ci` in the app directory.
   - Restart the systemd service.
   - Verify both service readiness and HTTP response on the bound localhost port.

## Suggested operator flow

1. `systemctl --user status <service> --no-pager -l`
2. inspect the service file and `ExecStart`
3. confirm whether a second supervisor exists (PM2, Docker, another systemd unit)
4. if dependencies were deleted, run `npm ci`
5. restart only the chosen supervisor
6. verify localhost health with HTTP 200

## Why this matters

Without this check, an agent may incorrectly conclude the app is down, restart the wrong process manager, or keep a duplicate PM2 process around that only reintroduces the conflict later.