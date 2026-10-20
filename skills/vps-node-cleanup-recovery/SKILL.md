---
name: vps-node-cleanup-recovery
title: VPS Node.js Cleanup & Recovery
description: Safe cleanup of node_modules without breaking npm/pm2, plus recovery procedures for broken symlinks
trigger: |
  - Disk usage high (>85%) from node_modules
  - npm/pm2 CLI broken after cleanup (symlink targets missing)
  - Need to free space without losing running services
---

# VPS Node.js Cleanup & Recovery

## Overview

On a VPS with multiple Node.js projects and long-running services (pm2, Hermes, next-server), cleaning up `node_modules` is safe BUT requires awareness:

- `node_modules` are fully rebuild-able via `npm ci` or `npm install`
- npm/pm2 CLIs live in `~/.hermes/node/` and use symlinks
- Symlink targets (e.g., `lib/node_modules/npm/bin/npm-cli.js`) can disappear if cleanup is too aggressive
- Running processes don't immediately fail when targets vanish — they fail on restart

## Safe Cleanup Sequence

### 1. Audit active supervisors BEFORE deleting anything

```bash
systemctl --user list-units --type=service --all --no-pager
pm2 list
ss -tlnp
```

Then map each service to its startup artifact:
- systemd user units in `~/.config/systemd/user/*.service`
- PM2 startup info from `pm2 jlist`

Read these fields before cleanup:
- `ExecStart`
- `WorkingDirectory`
- `pm_exec_path`
- `pm_cwd`
- `exec_interpreter`

This catches the critical failure mode where a process stays alive after cleanup, but the next restart fails because its runtime dependency path was deleted.

See also: `references/live-service-dependency-audit.md`.

### 2. Deployment-Aware Categorization (preferred over blanket delete)

Before deleting any `node_modules`, map each project to its deployment type:

```bash
# Projects with node_modules
find /home/user -maxdepth 3 -name "node_modules" -type d 2>/dev/null | while read d; do du -sh "$d"; done | sort -rh

# Map each to deployment type:
pm2 list 2>/dev/null          # which projects are pm2 apps?
docker ps --format "{{.Names}}"  # which run in Docker?
for d in /home/user/*/; do echo -n "$(basename $d): "; git -C "$d" log -1 --format="%ai" 2>/dev/null || echo "no git"; done  # last activity
```

**Categorize:**

| Deployment Type | Can delete host `node_modules`? | Why |
|----------------|-------------------------------|-----|
| **Docker** | ✅ Yes | Code runs inside container image |
| **pm2** (runtime needs local deps) | ❌ No | PM2 starts app from host node_modules |
| **Vercel/remote** deployed | ✅ Yes | Deployed elsewhere |
| **Idle** (no container, no pm2, stale git) | ✅ Yes | Not running anywhere |

### 3. Identify space hogs

```bash
du -sh /home/user/*/node_modules | sort -rh | head -10
```

Typical per-project: 500M–1.5G.

### 3. Stop non-critical services (optional)

If rebuilding will take time, stop services that don't depend on npm:

```bash
pm2 stop agentwa-web  # if it conflicts with nginx on :20128
```

Running services stay alive during cleanup.

### 3. Remove all node_modules safely

```bash
find /home/user -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
```

**Expected result:** ~9G freed (from 97% → 80% disk usage).

### 4. Verify global npm/pm2 still work

```bash
which npm && npm --version
which pm2 && pm2 --version
```

If npm/pm2 return "command not found" or broken symlink:
- **Symlink targets are missing** — follow Recovery below
- Do NOT assume npm is gone, check symlink carefully first

### 5. Rebuild projects on next run

When services restart, they'll rebuild `node_modules` from `package-lock.json`:

```bash
cd /home/user/agentwa/web && npm ci
cd /home/user/umkm-os && npm ci
```

Or let pm2/systemd auto-restart handle it.

---

## Recovery: Broken npm/pm2 After Cleanup

### Symptom

```bash
$ npm --version
/usr/bin/bash: npm: command not found

$ ls -la /home/user/.local/bin/npm
lrwxrwxrwx ... /home/user/.local/bin/npm -> /home/user/.hermes/node/bin/npm
# Symlink exists but target does not

$ ls -la /home/user/.hermes/node/lib/node_modules/npm/
ls: cannot access ...: No such file or directory
```

### Root Cause

`lib/node_modules/` was removed during cleanup. The `node` binary still works, but all global packages are gone.

### Fix: Rebuild npm from tarball

Node v22 ships with npm built-in capability. Restore it:

```bash
# 1. Fetch latest npm tarball
mkdir -p /home/user/.hermes/node/lib/node_modules
cd /tmp && curl -sL https://registry.npmjs.org/npm/-/npm-11.17.0.tgz | tar xzf -

# 2. Install to node_modules
mv /tmp/package /home/user/.hermes/node/lib/node_modules/npm

# 3. Test
/home/user/.hermes/node/bin/node /home/user/.hermes/node/lib/node_modules/npm/bin/npm-cli.js --version
# Expected: 11.17.0

# 4. Verify symlinks work
/home/user/.local/bin/npm --version
```

### Fix: Rebuild pm2 after npm

```bash
/home/user/.local/bin/npm install -g pm2
# Expected: added 90 packages in ~16s

pm2 --version
pm2 list  # Check running processes
```

### Recovery Checklist

- [ ] Node binary exists: `/home/user/.hermes/node/bin/node` (ELF executable, 124MB)
- [ ] npm tarball downloaded and extracted to `lib/node_modules/npm/`
- [ ] Symlinks in `~/.local/bin/` point to correct targets
- [ ] `npm --version` works
- [ ] `pm2 --version` works
- [ ] `pm2 list` shows running processes (may have "stopped" status if they failed)
- [ ] Restart stopped services via `pm2 restart <id>`

---

## Pitfalls

### Pitfall 1: Assuming npm is "uninstalled"

After cleanup, `which npm` fails. Don't reinstall Node — check the symlink chain first:

```bash
ls -la /home/user/.local/bin/npm              # Is symlink broken?
ls -la /home/user/.hermes/node/bin/npm         # Where does it point?
ls -la /home/user/.hermes/node/lib/node_modules/npm/bin/npm-cli.js  # Final target?
```

If only the final target is missing (lib/node_modules/npm/), rebuild npm. Don't reinstall Node.

### Pitfall 2: Cleanup hitting ~/.hermes/node/bin/ itself

**DO NOT** delete `~/.hermes/node/bin/node` — it's the 124MB binary, irreplaceable without a fresh Node install.

**Safe cleanup pattern:**
```bash
find /home/user -type d -name node_modules -exec rm -rf {} +
```

This skips `bin/` directories and only removes `node_modules/`.

### Pitfall 3: Duplicate supervisors causing fake service failures

A web app may already be healthy under `systemd --user`, while a duplicate PM2 entry for the same app and port fails with `EADDRINUSE`.

Pattern:
- systemd owns the real app and port
- PM2 crash loop is only a duplicate supervisor

Verify ownership first:

```bash
ss -tlnp | grep 20128
systemctl --user status agentwa-web.service --no-pager -l
pm2 list
```

If systemd is already the source of truth, stop/remove the duplicate PM2 app instead of modifying the healthy service.

### Pitfall 4: Global service packages hidden under ~/.hermes/node/lib/node_modules

Some systemd services do not depend on per-project `node_modules`, but on global packages under Hermes' Node tree.

Example:
- `the gateway.service` → `/home/user/.hermes/node/lib/node_modules/the gateway/cli.js`

If cleanup wipes that directory, the currently running process may survive, but restart will fail. Restore with the pinned global package version, then restart the service.

### Pitfall 5: pm2 logs hang indefinitely

```bash
pm2 logs agentwa-web
# [Command timed out after 180s]
```

Use `pm2 describe <app>` or check log file directly instead:

```bash
pm2 describe agentwa-web
tail -50 /home/user/agentwa/web/logs/err.log
```

### Pitfall 6: PM2 can report `online` while nothing is actually listening

Do not trust `pm2 ls` alone.

Observed failure pattern on this VPS:
- `pm2 describe <app>` shows `status: online`
- `pm2 ls` may even show `PID N/A`
- target port is not listening at all
- earlier app logs show real startup failures (`MODULE_NOT_FOUND`, `EADDRINUSE`, stale Next.js build artifacts), but after `pm2 flush` the evidence can disappear from the live log files

Required verification for suspicious PM2 apps:

```bash
pm2 describe <app>
ss -tulpen | grep -E ':<expected_port>\b' || true
lsof -i :<expected_port> -P -n || true
```

Interpretation rule:
- `pm2` says online but no listener exists -> treat the process entry as stale/broken, not healthy
- if the expected port is already owned by a different supervisor (systemd, docker, another pm2 app), fix the ownership conflict before rebuilding the app

### Pitfall 7: node_modules isn't always the hog — audit per-subdir first

After `rm -rf <proj>/node_modules`, if `du -sh <proj>` barely moved, the weight is elsewhere. Run `du -sh <proj>/* | sort -rh` before deciding what's safe to delete.

Observed on this VPS:
- `security-gateway-src/ml-service/models/indobert-agentwa/model.onnx` = 475M — re-trainable artifact of a STOPPED service, safe to delete (or keep if service may resume)
- `agentwa/web/node_modules` = 789M — the actual rebuild-able dep tree

Also: Docker images of stopped services (e.g., `security-gateway-src-ml-service:latest`, 1.58G, no running container) are NOT freed by `docker image prune --filter until=720h` (only 505M reclaimed). Use plain `docker image prune -a -f` instead (1.87G reclaimed here). Cross-check `docker ps -a --format '{{.Image}}'` against `docker images` before pruning so you never remove an image a running container needs.

### Cleanup yield reference points (shared VPS)

On this host, the safest no-downtime first pass produced meaningful savings without touching active project `node_modules`, Docker images, or Hermes runtime:
- `journalctl --vacuum-size=200M` cut journald from ~651M to ~163M
- `npm cache clean --force` reduced `~/.npm` from ~698M to ~227M
- `pm2 flush` reduced `~/.pm2` from ~107M to ~7.6M

Important nuance:
- deleting `~/.gradle/caches` may free little or nothing from the top-line `~/.gradle` size when most of that directory is actually `wrapper/` content rather than `caches/`
- always re-measure `du -sh ~/.gradle ~/.cache ~/.npm ~/.pm2` after cleanup instead of assuming the expected savings happened

### Build-tool caches are usually the biggest reclaimable block after an agent has been compiling

On a host where an agent has repeatedly built a project, the compiler's own caches dwarf
`node_modules`. Measure the **subdirectory**, not the parent:

```bash
du -sh ~/.gradle/caches ~/.m2/repository ~/.cache 2>/dev/null | sort -rh
du -sh ~/.cache/* 2>/dev/null | sort -rh | head -10
```

Typical yields on this VPS (safe to delete; re-downloaded on the next build/run):
- `~/.gradle/caches` — 5.1 GB
- `~/.cache/ms-playwright` + `camoufox` + `puppeteer` — 3.2 GB
- `docker builder prune -f` — 430 MB (buildkit cache; does NOT touch images/volumes)

Before deleting a browser-automation cache, prove nothing live depends on it:
```bash
ps aux | grep -icE '[p]laywright|[c]amoufox|[p]uppeteer'          # 0 = not in use now
grep -rl 'playwright\|camoufox\|puppeteer' /etc/systemd/system /etc/cron* 2>/dev/null
```
A `package.json` reference alone is not a blocker — the deps re-download on next `npm install`.

**Report measured before/after, not adjectives.** Capture `df -h /` on both sides; a cleanup that
"should" have freed gigabytes may free nothing if you targeted the wrong subtree.

---

## Second-Pass Cleanup: Rust build artifacts after service-path audit

When first-pass cache + `node_modules` cleanup is not enough, the next safest high-yield target is often Rust debug build output **only after confirming production services do not start from that debug tree**.

### Safe pattern

1. Inspect the live supervisor definition first:
   - `systemctl cat <service>`
   - verify `ExecStart`
   - confirm whether it points at `target/release/...`, `target/debug/...`, or a different repo entirely
2. If the running service uses `target/release/...` or another checkout, it is usually safe to remove stale source-repo debug artifacts:

```bash
rm -rf /path/to/repo/target/debug
```

or the heaviest subdirectories only:

```bash
rm -rf /path/to/repo/target/debug/deps \
       /path/to/repo/target/debug/incremental \
       /path/to/repo/target/debug/build \
       /path/to/repo/target/debug/.fingerprint
```

3. Re-check the user-visible surface after deletion (HTTP/healthcheck/systemctl state).

### Why this works

`target/debug/` is rebuildable compiler output. On long-lived VPSes, old debug trees can silently accumulate to 500MB–1.5GB per Rust service even when production runs from a release binary elsewhere.

### Important pitfall

Do **not** delete `target/debug/` just because a service name looks related to the repo name. Some systems keep multiple checkouts (e.g. `~/project-src` for development and `~/project` for deployed runtime). The deciding fact is the supervisor's `ExecStart`, not the folder name.

## Post-Cleanup Verification

After cleanup + recovery:

```bash
# 1. Disk usage
df -h /

# 2. All CLIs present
for cmd in node npm npx pm2 git curl vercel; do which $cmd && echo "✓ $cmd" || echo "✗ $cmd"; done

# 3. Supervisors healthy
systemctl --user status agentwa-web.service the gateway.service video-downloader.service --no-pager -l
pm2 status whatsapp-api kosatlas

# 4. HTTP/port checks
curl -I http://127.0.0.1:20128   # agentwa-web
curl -I http://127.0.0.1:20129   # the gateway (redirect to /dashboard is fine)
curl -I http://127.0.0.1:8890    # video-downloader

# 5. Memory/swap healthy
free -h
```

---

## Context: This VPS

- **Ubuntu 24.04**, 59G total
- **Node:** v22.22.2 (`~/.hermes/node/bin/node`)
- **npm:** stored in `~/.hermes/node/lib/node_modules/npm/` (rebuilds from tarball)
- **pm2:** managed as global package
- **Services:** whatsapp-api (port 3000), kosatlas (3005), next-server (20128), Hermes (8888)
- **Rebuild time:** ~16s for pm2 after npm restored
