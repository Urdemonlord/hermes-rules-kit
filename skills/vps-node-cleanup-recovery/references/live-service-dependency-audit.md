# Live Service Dependency Audit Pattern

Use this before deleting `node_modules`, global npm packages, or virtualenv/runtime directories on a VPS.

## Why
A cleanup can look successful because already-running processes stay alive, but the next restart fails because startup paths still depend on local runtime files that were deleted.

## Preflight audit

### 1. Enumerate active supervisors
```bash
systemctl --user list-units --type=service --all --no-pager
pm2 list
ss -tlnp
```

### 2. Map each service to its startup artifact
Inspect:
- systemd user units in `~/.config/systemd/user/*.service`
- PM2 config from `pm2 jlist`

Extract these fields:
- `ExecStart`
- `WorkingDirectory`
- `pm_exec_path`
- `pm_cwd`
- `exec_interpreter`

### 3. Classify dependency risk

**High risk to delete:**
- per-project `node_modules` when startup path resolves into package-managed binaries or runtime deps
- global npm packages under `~/.hermes/node/lib/node_modules/*`
- active virtualenvs used by systemd services
- built artifacts (`dist/`) when PM2/systemd starts from the built file

**Lower risk:**
- caches (`~/.npm`, `~/.cache/pip`, `~/.cache/typescript`, uv cache)
- `node_modules` of inactive projects with no active systemd/PM2 owner

## Concrete recovery lessons from this VPS

### Duplicate supervisor pitfall
A Next.js app can be healthy under systemd while a duplicate PM2 app crashes with `EADDRINUSE` on the same port.

Pattern:
- `systemd --user` already owns the app and port
- PM2 restart loop is a duplicate, not the source of truth

Action:
- verify the real owner with `ss -tlnp` + `systemctl --user status`
- stop/remove the duplicate PM2 app instead of changing the healthy systemd service

### Services that looked alive but were restart-brittle
These runtime paths had to exist for restart safety:
- `agentwa-web.service` → `/home/user/agentwa/web/node_modules/next/dist/bin/next`
- `the gateway.service` → `/home/user/.hermes/node/lib/node_modules/the gateway/cli.js`
- `video-downloader.service` → `/home/user/video-downloader/node_modules`
- `whatsapp-api` (PM2) → `/home/user/whatsapp-api/node_modules`
- `kosatlas` (PM2) → `/home/user/atlasproject/server/node_modules`
- `hermes-gateway.service` → `/home/user/.hermes/hermes-agent/venv`

## Restore order after aggressive cleanup
1. restore npm if global npm vanished
2. restore pm2 if global pm2 vanished
3. restore global service packages (example: `npm install -g the gateway@0.4.80`)
4. restore per-project dependencies with `npm ci`
5. restart each affected systemd/PM2 service
6. verify with real HTTP/port checks

## Verification pattern
```bash
systemctl --user status agentwa-web.service the gateway.service video-downloader.service --no-pager -l
pm2 status whatsapp-api kosatlas
curl -I http://127.0.0.1:20128
curl -I http://127.0.0.1:20129
curl -I http://127.0.0.1:8890
```

The lesson is not just "reinstall npm". The durable lesson is: audit live service dependency ownership before deleting rebuildable directories.