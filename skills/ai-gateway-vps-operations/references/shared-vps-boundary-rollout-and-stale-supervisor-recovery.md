# Shared VPS boundary rollout + stale supervisor recovery

Use on multi-project VPS hosts where several unrelated apps coexist and the main risk is cross-project inference by humans or agents.

## What to create

At the VPS level:
- `~/ops/vps-project-registry.md`
- `~/ops/ports.md`

Per project and per meaningful subproject/runtime root:
- `.ops-boundary.md`

Do not stop at top-level repos only. Add boundary files to subprojects that may be operated independently, for example:
- backend/
- frontend/
- deploy/
- runtime roots under hidden tool dirs such as `.hermes/`, `.the gateway/`, `.config/`

## Discovery rule

When rolling out boundaries across a VPS, treat a directory as project-like when it has one or more markers such as:
- `.git`
- `package.json`
- `go.mod`
- `Cargo.toml`
- `pyproject.toml`
- `docker-compose.yml`
- `requirements.txt`

Exclude build artifacts and caches from coverage math, especially:
- `.next/`
- `node_modules/`
- `__pycache__/`
- cache dirs under home

Success condition: every project-like dir except build artifacts has a `.ops-boundary.md`.

## Boundary content minimum

Each `.ops-boundary.md` should state:
- exact project path
- that the project is isolated unless an explicit relationship is documented in env/compose/systemd/nginx/deploy/docs
- do-not-cross rules: no blind reuse of DB/Redis/network/volume/port
- mandatory preflight: `ss -tulpen`, `docker ps -a`, `docker network ls`, `docker volume ls`, `pm2 ls`, `systemctl list-units --type=service`
- explicit warning not to treat missing listeners or broken ports as free resources

## PM2 false-green recovery pattern

A PM2 app can report `online` while being operationally dead.

Treat a PM2 entry as stale/broken when the combination below appears:
- `pm2 ls` shows `online`
- `pid` is `N/A`
- CPU and memory are `0`
- expected listener is missing in `ss -ltnp`
- `pm2 describe` points to a missing `exec cwd` or missing package/runtime path
- logs are empty or uninformative

Safe cleanup pattern:
1. Backup `~/.pm2/dump.pm2`
2. `pm2 delete <name>`
3. `pm2 save`
4. Verify the app is gone from both `pm2 ls` and `~/.pm2/dump.pm2`
5. Re-check the expected port listener

This is supervisor cleanup, not project deletion. Keep project files and boundary docs intact unless obsolete status is separately confirmed.

## Port-hardening interpretation rule

A bind on `0.0.0.0` is not automatically public if host firewall default is deny, but it is still attack surface and should be moved to loopback when direct internet access is unnecessary.

Preferred order:
1. verify whether the port truly needs public reachability
2. if not, rebind to `127.0.0.1`
3. keep public access through nginx on `80/443`
4. do not stop a service when rebinding or firewalling is enough
