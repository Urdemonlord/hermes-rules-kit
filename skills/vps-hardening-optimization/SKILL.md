---
title: VPS Hardening & Optimization
name: vps-hardening-optimization
description: Full VPS security hardening + resource optimization workflow. Firewall, fail2ban, Docker RAM limits, nginx hardening, kernel cleanup, auto-prune.
triggers:
  - User asks to "optimize vps", "harden server", "secure vps", "clean up vps"
  - New VPS setup
  - VPS running out of RAM/disk/swap
  - Disk alert: disk high, disk full, df -h shows >85%
  - Watchdog: disk alert triage
  - User asks "kok bisa sampe X%" (root cause of high disk)
---

# VPS Hardening & Optimization

Sequential steps from low-risk to higher-risk.

## 1. Scan Before Touching

```bash
df -h; free -h; uptime
ps aux --sort=-%mem | head -10
ss -tlnp | grep "0.0.0.0:"   # public services
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

### Full project inventory (before any cleanup)

Run a complete inventory of every project directory before deciding what to delete:

```bash
# 1. All project dirs with sizes
du -sh /home/user/*/ 2>/dev/null | sort -rh

# 2. Running Docker containers
docker ps --format '{{.Names}} | {{.Status}} | {{.Ports}}'

# 3. PM2 processes
pm2 list 2>/dev/null

# 4. Check git remote + last commit for candidate projects
for p in /home/user/*/; do
  name=$(basename "$p")
  git -C "$p" remote -v 2>/dev/null | head -1
  git -C "$p" log -1 --format='%h %s (%ci)' 2>/dev/null
done
```

**Categorize each project into:**
- **Running Docker** (container exists with that name) — keep
- **Running PM2** (process list has it) — keep
- **Running other** (systemd, daemon) — keep
- **Stale** (no Docker, no PM2, stale git commit) — candidate for deletion
- **Tiny clones** (<1MB, no runtime) — safe to delete

**User preference pattern**: Always present the full inventory in a table with last-commit-age, runtime status, and delete-recommendation BEFORE acting. Ask user ("mau hapus yang mana?/mau detail per projek?"). Users prefer understanding before cleanup — the detailed per-project breakdown lets them make informed decisions about what's still valuable vs truly stale.

### Docker memory limit scan

Before adding limits, find containers that have none:

```bash
docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' | while IFS=$'\t' read name mem cpu rest; do
  limit=$(docker inspect "$name" --format '{{.HostConfig.Memory}}' 2>/dev/null)
  [ "$limit" = "0" ] && echo "$name | NO LIMIT — using $mem"
done
```

Compare against defaults: for most VPSes with <=4GB RAM, set `128M-256M` for frontend/api, `1G` for ML, `128M-256M` for Postgres. Containers without limits can spike during cold starts and trigger OOM kills on sibling containers.

**Pitfall**: Node Express defaults `app.listen(PORT)` → `0.0.0.0`. Fix: `app.listen(PORT, '127.0.0.1')`.

**Pitfall**: Docker containers running dev servers (e.g., `vite preview --port 3000`) can leave orphaned processes that bind host ports even after the container is "stopped". The container PID may show in `ps aux` as root-owned, with path `/app/...` (container filesystem). Fix: find the container via `cat /proc/<PID>/cgroup | grep docker`, stop/restart the container, then `kill -9` the orphaned PID. Also check for port conflicts before starting systemd services: `ss -tlnp | grep <PORT>`.

### Subagent profile bloat check

Automated subagent runs (Kanban builder, reviewer, planner) accumulate sessions fast. Check:

```bash
for p in builder reviewer planner; do
  db=~/.hermes/profiles/$p/state.db
  [ -f "$db" ] && echo "$p: $(du -sh "$db" | cut -f1) $(sqlite3 "$db" 'SELECT count(*) FROM sessions;' 2>/dev/null) sessions $(sqlite3 "$db" 'SELECT datetime(max(started_at), "unixepoch") FROM sessions;' 2>/dev/null)"
done
```

**Pattern**: builder profile can reach 569MB / 26.5K sessions in 3 weeks of active subagent use. If profile shows no recent activity (weeks old), state.db is a cleanup candidate — VACUUM to shrink without data loss, or delete entire profile if unused.

## 2. Bind Exposed Services to 127.0.0.1

Find services on `*:PORT` that should only go through nginx.

```bash
ps -p <PID> -o pid,cmd --no-headers
ls -la /proc/<PID>/cwd
# Patch listen() to bind '127.0.0.1', restart
```

Create systemd service if missing:
```bash
sudo tee /etc/systemd/system/<name>.service > /dev/null << 'EOF'
[Unit]
Description=...
After=network.target
[Service]
Type=simple
User=meowlabs
WorkingDirectory=/home/user/<path>
ExecStart=/home/user/.local/bin/node server.js
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now <name>
```

## 3. Fail2ban

```bash
sudo apt install -y fail2ban

sudo tee /etc/fail2ban/jail.local > /dev/null << 'EOF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
[sshd]
enabled = true
[nginx-http-auth]
enabled = true
logpath = /var/log/nginx/error.log
[nginx-botsearch]
enabled = true
logpath = /var/log/nginx/access.log
maxretry = 2
findtime = 30m
bantime = 24h
EOF

sudo fail2ban-client reload
```

### Jail `ufw-block` — redam noise port scan (UFW BLOCK)

Port scan ke port tertutup membanjiri log. Gejala: `syslog`/`ufw.log` penuh `[UFW BLOCK]`
(ribuan entri; sering ~66% ke satu port yang tidak listen). Dua langkah:

**a) Stop dobel-log.** UFW BLOCK masuk ke `ufw.log` DAN `syslog`. Di
`/etc/rsyslog.d/20-ufw.conf`, uncomment `& stop` di baris terakhir, lalu
`sudo systemctl restart rsyslog`. Hasil: `syslog` bersih, `ufw.log` tetap lengkap
(backup filenya dulu). Ini yang paling banyak memangkas noise.

**b) Jail fail2ban.** Filter `/etc/fail2ban/filter.d/ufw-block.conf`:
```ini
[Definition]
failregex = \[UFW BLOCK\].*SRC=<HOST>
ignoreregex =
```
Jail `/etc/fail2ban/jail.d/ufw-block.conf`:
```ini
[ufw-block]
enabled  = true
filter   = ufw-block
logpath  = /var/log/ufw.log
banaction = iptables-allports
maxretry = 5
findtime = 10m
bantime  = 24h
ignoreip = 127.0.0.1/8 ::1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 <IP-PUBLIK-SENDIRI>
```

Pitfalls:
- **`ignoreip` wajib** memuat loopback + rentang Docker (10/8, 172.16/12, 192.168/16)
  + IP publik VPS sendiri — kalau tidak, container/host bisa ter-ban sendiri.
- **Set ambang dari data, bukan tebakan.** Ukur dulu:
  `grep 'UFW BLOCK' /var/log/ufw.log | grep -oE 'SRC=[0-9.]+' | sort | uniq -c | sort -rn | head`.
  Scan biasanya terdistribusi (ribuan IP berbeda, jarang >6 hit/10m per IP), jadi
  `maxretry=20` terlalu longgar dan tidak pernah ban — `5` lebih realistis.
- **Ukur ukuran log sebenarnya sebelum panik soal disk.** Klaim "110M/minggu" bisa
  keliru; `du -ch /var/log/ufw.log*` sering cuma beberapa MB — masalahnya *noise*,
  bukan ruang disk.
- Verifikasi: `sudo fail2ban-client status ufw-block` (lihat Currently banned) dan
  `sudo iptables -L f2b-ufw-block -n` (chain dibuat setelah ada ban pertama).
- Tes regex sebelum reload: `sudo fail2ban-regex /var/log/ufw.log /etc/fail2ban/filter.d/ufw-block.conf`
  — targetkan match mendekati 100% baris.

## 4. UFW Firewall (Docker Compat)

**Risk**: Docker bypasses UFW. Set forward policy first.

```bash
sudo sed -i 's/DEFAULT_FORWARD_POLICY="DROP"/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

**Safety**: Always `ufw allow 22` BEFORE enable. Keep SSH session alive.

## 5. Docker RAM Limits

```bash
docker update --memory <hard> --memory-swap <swap> <container>
```

Profile defaults:
| Type | RAM | Swap |
|------|-----|------|
| API/gateway | 128M | 256M |
| ML/inference | **1024M** | 1024M |
| Backend | 256M | 512M |
| Frontend | 128M | 256M |
| Postgres | 128-256M | 256-512M |

**ML note**: ONNX model files are large. A 498MB model needs 1024M+ container RAM (2× file size minimum). With 384M the model silently never loads — no crash, no log, just timeouts → fail-open bypass.

**Pitfall**: `--memory-swap` MUST be set together with `--memory` whenever a swap limit was previously set. Docker refuses update saying "Memory limit should be smaller than already set memoryswap limit".

## 5b. Docker DNS — Cloud Provider DNS Hijack

Docker copies `/etc/resolv.conf` from host, but cloud providers (Tencent Cloud, Alibaba, etc.) may route DNS through regional resolvers (e.g. China Telecom `183.60.x.x`) that block Google/Yandex/Cloudflare for some domains. This causes **silent failures** inside containers: SSL timeouts, HTTP 500, or wrong IPs for Google services.

**Check container DNS:**
```bash
docker run --rm alpine:latest cat /etc/resolv.conf | grep nameserver
```

**Expected bad output** (Tencent Cloud Asia):
```
nameserver 203.0.113.10
nameserver 203.0.113.10
```

**Fix:**
```bash
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "dns": ["1.1.1.1", "203.0.113.10"]
}
EOF
sudo systemctl restart docker
```

**Verify fix:**
```bash
docker run --rm alpine:latest cat /etc/resolv.conf | grep nameserver
# Expected: 1.1.1.1, 203.0.113.10
```

**Pitfall**: `sudo` required for `/etc/docker/daemon.json` — plain write returns "Permission denied" silently in some Hermes terminal sessions. Always use `sudo tee`.

## 6. Disk Alert Triage

When watchdog reports high disk (≥85%). Ordered safe-to-risky, each step yields and stops.

### Step 1: Top-level breakdown

```bash
df -h / && echo "---"
du -sh /* --exclude=/mnt --exclude=/media --exclude=/proc --exclude=/sys --exclude=/dev 2>/dev/null | sort -rh | head -15
```

Identify the top 3 dirs. Drill each:

```bash
du -sh /home/user/* 2>/dev/null | sort -rh | head -15   # projects
du -sh /var/* 2>/dev/null | sort -rh | head -10              # logs, lib
du -sh /tmp/* 2>/dev/null | sort -rh | head -10              # temp
du -sh /snap/* 2>/dev/null | sort -rh                        # snap images
swapon --show; ls -lh /swap*.img 2>/dev/null                 # swap files
```

### Step 1b: Ground truth is `df -h`, not `du`

**Critical pitfall**: `du -sh /*` runs as current user and silently misses root-owned directories (`/var/lib/containerd`, `/var/lib/docker`, `/var/lib/snapd`). The reported "total" can be 10-20GB less than what `df -h` shows. Always use `df -h /` as ground truth, then drill with `sudo du` for root-owned paths.

```bash
df -h /           # ground truth — always start here
sudo du -sh /var/lib/* 2>/dev/null | sort -rh | head -10  # containerd, docker, snapd
```

### Step 1c: Deleted-but-open files

Files unlinked from the filesystem but still held open by running processes consume disk invisibly.

```bash
sudo lsof +L1 2>/dev/null | awk '$7 > 10000000 {print $1, $2, $7, $NF}' | sort -k3 -rn
```

Common culprits: journal files (systemd-journald), deleted binaries during package upgrades (tat_agent), Python binaries during uv upgrades. Most are small — journal files (100MB+) are the biggest. Fix: `sudo journalctl --vacuum-size=100M` or restart the holding process.

### Step 1d: state.db / SQLite VACUUM check

Before running `VACUUM` on any SQLite database (Hermes state.db, etc.), check free pages first:

```bash
sqlite3 <db> "PRAGMA page_count; PRAGMA page_size; PRAGMA freelist_count;"
# Free pages × page_size = reclaimable space
# If freelist < 1% of page_count → VACUUM is pointless
```

Typical finding: a 1.4GB state.db with 114K messages may have only 8MB free pages — VACUUM wastes time for negligible savings.

### Step 1e: Docker mystery gap analysis

`du -sh /var/lib/docker` often reports less than `docker system df` shows. Root cause: overlay2 dirs counted in `du` don't match image-layer accounting because of snapshot hardlinks and shared layers.

**Authoritative source for reclaimable image space:**
```bash
docker system df            # shows RECLAIMABLE per type
docker system df -v         # shows per-image breakdown
```

When all containers are running (14/14), Images shows 100% UNRECLAIMABLE — every image in use. The "mystery gap" of 5-10GB between `du -sh /` items and `df -h /` is typically:
- **Containerd blobs** (`/var/lib/containerd/io.containerd.content.v1.content/blobs/sha256/`) — cached layer blobs, 2-11GB typical, **safe to keep** — they're the content store
- **Snapd cache** (`/var/lib/snapd/cache/`) — 1-2GB, safe to clear
- **Docker overlayfs root** (`/var/lib/docker/rootfs/overlayfs/`) — 1-3GB of shared layer files, often duplicated in containerd

**Before claiming mystery space exists:** sum `sudo du -sh /var/lib/docker /var/lib/containerd /var/lib/snapd 2>/dev/null` and compare to `df -h /`. The total usually accounts for the gap.

**Containerd GC after image removal**: containerd snapshots (`/var/lib/containerd/io.containerd.snapshotter.v1.overlayfs/`) are NOT auto-cleaned when Docker images are removed via `docker rmi` or `docker system prune`. Old snapshot layers persist until containerd's garbage collector runs — which may not trigger automatically. After significant image removal (deleting 3+ images, especially large ones like ML containers), force containerd GC:

```bash
sudo systemctl restart containerd
sleep 3
sudo du -sh /var/lib/containerd/io.containerd.snapshotter.v1.overlayfs/
# Expected: drops 2-5GB after restart if stale snapshots existed
```

**Real-world example**: after removing imgseeker (3.0G), auth-service-inference-worker (1.75G), and auth-service-core (200M) images, containerd snapshotter dropped from 7.6G → 3.5G and content store from 4.0G → 2.5G — reclaiming ~5.6GB of stale layers that `docker system prune -af` left behind.

### Step 1f: `.git` pack file audit

Oversized `.git` dirs on repos with committed binary blobs are common but hard to shrink safely.

```bash
cd /path/to/repo/.git && du -sh objects/pack
git verify-pack -v objects/pack/*.idx 2>/dev/null | sort -k3 -n -r | head -5
```

If a single blob >100MB, standard `git gc` (even `--aggressive`) does nothing — the pack is already compressed. Options:
- **BFG repo-cleaner** — rewrites history, recovers ~90% of the blob size
- **`git gc --aggressive`** — rarely helps more than a few MB on already-packed repos
- **Accept it** — the blob is in history; it's only a one-time cost

Threshold for action: if the big blob was committed by accident (2G binary, 600M model), BFG is worth it. If it's intentional (large assets), accept the size.

Recommended: skip aggressive gc on repos >300MB if only a few MB at stake — `git gc` already ran during this session and gained 0-2MB.

### Step 2: Safe cleanup targets (ordered by safety)

| Target | Typical savings | Command | Risk |
|--------|----------------|---------|------|
| `/tmp/*` stale files | 200M–2G | `rm -rf /tmp/pip-unpack-* /tmp/ocr-env /tmp/node-compile-cache` | None |
| **`~/.cache/` package managers** | 1–5G | See cache audit below | None |
| **Docker build cache** | 1–6G | `docker builder prune --all --force` | None |
| **Docker dangling + stopped** | 500M–2G | `docker system prune -f && docker container prune -f` | None — only removes dangling (untagged) images |
| **Docker ALL unused images** | 1–5G | `docker image prune -a -f` | None — check `docker ps` first. Removes every image not referenced by a running container. The gap vs `system prune` was **1.95G on this VPS** from the session below. |
| Journal vacuum | 200–500M | `sudo journalctl --vacuum-size=200M` | None |
| APT cache | 50–200M | `sudo apt-get clean` | None |
| Snap old revisions | 300M–1G | See snap cleanup below | Low |
| Unused snap packages | 1–4G | See snap cleanup below | Low |
| **Hermes session dumps** (.json/.jsonl) | 200–400M | `rm -f ~/.hermes/sessions/*.json ~/.hermes/sessions/*.jsonl` | Low — verify not actively used first (db stores them) |
| **Hermes state-snapshots** | 0.5–1.5G | `rm -rf ~/.hermes/state-snapshots/*` | Medium — only if snapshot is confirmed stale for rollback |

**Pitfall**: `journalctl --vacuum-size=X` without `sudo` frees 0B even when it appears to succeed. Always use `sudo journalctl --vacuum-size=X`. The command runs without error for non-root users but cannot write to `/var/log/journal/`.

**Pitfall**: `docker builder prune --all --force` is separate from `docker system prune`. Build cache (2–3G after heavy builds) is NOT cleaned by `docker system prune -f`. Run both.

### Step 2a: `~/.cache/` deep audit

`~/.cache/` is often the single largest reclaimable directory (2–5G on active ML/DevOps VPSes). Drill into it:

```bash
du -sh ~/.cache/*/ 2>/dev/null | sort -rh | head -10
```

Common big items:

| Cache | Typical Size | Clean Command | Notes |
|-------|-------------|---------------|-------|
| `~/.cache/huggingface/hub/` | 1–5G | `rm -rf ~/.cache/huggingface/hub/models--<name>` | Verify model unused first |
| `~/.cache/camoufox/` | 1–2G | Skip if imgseeker is running | Needed for browser automation |
| `~/.cache/uv/` | 1–5G | `rm -rf ~/.cache/uv/` | `uv cache clean` may hang; manual rm is faster |
| `~/.cache/ms-playwright/` | 600M–1G | Skip if Playwright tests active | Needed for browser testing |
| `~/.cache/pip/` | 50–200M | `rm -rf ~/.cache/pip/` | Safe, regrows on next install |
| `~/.cache/go-build/` | 50–200M | `rm -rf ~/.cache/go-build/` | Regrows on next `go build` |
| `~/.cache_git_backup_*` | 100–200M | `rm -rf ~/.cache_git_backup_*` | Old git backups, safe if data backed up |

**Pattern**: for each big cache item, check if any running container or service depends on it before deleting. `camoufox` and `ms-playwright` are commonly needed by active services — verify with `docker ps` and `pm2 list` first.

### Step 2b: `.hermes` deep scan

When `~/.hermes` is >2G, drill into it:

```bash
du -sh ~/.hermes/* 2>/dev/null | sort -rh | head -15
ls -lh ~/.hermes/state.db ~/.hermes/state.db-wal 2>/dev/null
ls -lh ~/.hermes/sessions/*.json 2>/dev/null | wc -l   # count session dumps
ls -lh ~/.hermes/sessions/*.jsonl 2>/dev/null | wc -l  # count old-format dumps
```

**Key**: session .json/.jsonl files are redundant if `state.db` exists. Safe to delete.

### Step 2c: Deployment-aware node_modules audit

Before deleting any `node_modules`, map each project to its runtime:

```bash
pm2 list 2>/dev/null | grep "│"   # which projects are pm2 apps?
docker ps --format "{{.Names}}"   # which are Docker?
git -C /path/to/project log -1 --format="%ai"  # last activity
```

Categorize:
- **Docker-based** (code runs in container): host `node_modules` safe to drop
- **pm2-based** (runtime needs local deps): keep `node_modules`
- **Vercel/remote** deployed: safe to drop
- **Idle** (no container, no pm2, stale): safe to drop

See `vps-node-cleanup-recovery` skill for the full deployment-mapping methodology.

### Step 3: Report before/after `df -h /`

### ⚠️ Swap safety rule

**On low-RAM VPS (≤4G): do NOT remove swap files without explicit user consent.**

```bash
free -h
swapon --show
```

If swap Used > 100M, warn user. Suggest removing only the least-used swap file (highest priority number, lowest Used). **Swap files with 0B used and small size (≤512M) are lowest-risk** — drop first if disk is critical.

**Pitfall: Deleted swap file still in fstab = boot-blocking failure.** If a swap file is removed (cleanup, corruption, mount issue) but `/etc/fstab` still lists it, systemd fails activation on every boot with `Failed to activate swap /swap3.img`. This can delay boot by 30-60 seconds or cause systemd to fail other dependent services. **Always edit fstab in the same session as swap file removal:**

```bash
# Before deleting any swap file, check fstab references
grep swap /etc/fstab

# After deletion, remove the entry + mask the generated systemd unit
sudo cp /etc/fstab /etc/fstab.bak
sudo sed -i '/swap3\.img/d' /etc/fstab
sudo systemctl mask swap3.img.swap  # prevents auto-restart attempts
```

**Prevention:** Keep only 2-3 swap files max in fstab (e.g., `/swap.img` and `/swap2.img`). Document which swap files are persistent vs ephemeral. If adding new swap, verify file exists BEFORE adding to fstab: `ls -lah /swap3.img` must succeed first.

### Snap cleanup on Ubuntu

Snaps accumulate old revisions and hidden caches. Major disk hog on Ubuntu.

```bash
# List disabled (old) snap revisions
snap list --all | awk '/disabled/{print $1, $3}'

# Remove old revisions
snap list --all | awk '/disabled/{print $1, $3}' | while read snap rev; do
  sudo snap remove "$snap" --revision="$rev"
done

# Clear snap cache
sudo rm -rf /var/lib/snapd/cache/*

# Check for removable GUI snaps (headless VPS)
which Xorg 2>/dev/null || echo "No Xorg — safe to remove GUI snaps"
# Example: sudo snap remove android-studio  # 3.5G on this VPS
```

**Pitfall**: `snap remove` keeps a data snapshot. Check `snap saved` — if tiny (bytes), it's fine. If large, `snap forget <set>` to fully reclaim.

**Pitfall**: `snap remove` is VERY slow on low-RAM VPS (30-60s+ per snap). Don't block the terminal waiting for it — queue the removal and check via `snap changes` later. `snap list --all | awk '/disabled/{print $3}'` shows which revisions are removable.

**Pitfall**: snaps can reappear after updates. On headless VPS, consider disabling snapd auto-refresh for removed GUI packages.

### Reporting style

Present as a markdown table: what was done, what was freed, what remains and why. User wants to see root cause ("kok bisa sampe 88%") not just cleanup results.

See also: `references/disk-alert-triage-2026-07.md` for real VPS baseline data.

## 6b. ML/Python Venv Cleanup (CPU-Only VPS)

On CPU-only VPSes, ML venvs waste ~3-5G on GPU packages (nvidia, triton, cuda) that can never run.

**Identify GPU waste in venvs:**
```bash
find /home -maxdepth 4 -name ".venv" -type d -exec du -sh {} \; 2>/dev/null | sort -rh
# For each big venv, check for GPU packages:
for v in $(find /home -maxdepth 4 -name ".venv" -type d 2>/dev/null); do
  nvidia=$(du -sh "$v"/lib/python*/site-packages/nvidia 2>/dev/null | awk '{print $1}')
  triton=$(du -sh "$v"/lib/python*/site-packages/triton 2>/dev/null | awk '{print $1}')
  [ -n "$nvidia" ] && echo "$v: nvidia=$nvidia triton=$triton"
done
```

**⚠️ Cannot simply `rm -rf` GPU packages** — torch binary links to CUDA libs, so removing nvidia causes `OSError: libcudart.so.*: cannot open shared object file`. Fix:

1. Identify CPU-only torch index: `https://download.pytorch.org/whl/cpu`
2. Replace torch + torchvision (must do BOTH — mismatched = `operator torchvision::nms does not exist`):
```bash
cd /path/to/project
uv pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision --python .venv/bin/python --reinstall
```
3. Verify: `.venv/bin/python -c "import torch; print(torch.__version__)"` should show `+cpu`

**uv-managed venvs**: No `pip` binary — use `uv pip install --reinstall` from project dir, or `rm -rf` site-packages dirs directly and reinstall.

**Pitfall**: `uv pip install --reinstall` may silently skip if versions match. Force with `--reinstall` flag. After replacement, old nvidia/triton dirs can be safely deleted:
```bash
rm -rf .venv/lib/python*/site-packages/{nvidia,nvidia_*,triton,triton_*,cuda,cuda_*,cuda_bindings*}
```

**Typical savings**: 2.5-4G per ML venv on CPU-only VPS.

## 6c. HuggingFace Model Cache Cleanup

Models cached in `~/.cache/huggingface/hub/models--*` can be 1-5G each.

**Identify and audit:**
```bash
du -sh ~/.cache/huggingface/hub/models--*/ 2>/dev/null | sort -rh
```

**Check which models are actually used by running code:**
```bash
# For each model, grep the project source
grep -rl "model-name" /path/to/project/src/ 2>/dev/null | grep -v __pycache__
# Also check .env for env overrides (config defaults may differ from runtime model)
cat /path/to/project/.env | grep -i "model\|hf_"
```

**Pitfall**: config.py default model ≠ runtime model. .env `ML_HF_MODEL=...` overrides config defaults. Always check both before deciding a model is unused.

**Remove unused models:**
```bash
rm -rf ~/.cache/huggingface/hub/models--google--siglip-*  # if not in code
```

**Typical savings**: 1-3G per unused model. BLIP-large ~1.8G, SigLIP ~3.3G.

## 6d. UV Cache Cleanup

UV cache at `~/.cache/uv/` regrows from every `uv run` / `uv pip install` command.

```bash
du -sh ~/.cache/uv/
# Clean:
uv cache clean --force  # may timeout if uv is in use
rm -rf ~/.cache/uv/     # nuclear option, works
```

**Pitfall**: cache regrows. On disk-critical VPS, consider periodic cleanup via cron. Typical size: 4-5G after heavy use, 0-100M after clean.

## 7. Deep Cleanup — Hidden Caches & Unused Packages

After basic setup, scan for big hidden dirs that accumulate over time:

```bash
# Big hidden dirs
du -sh /home/*/.* 2>/dev/null | sort -rh | head -15
du -sh /home/*/.cache/* 2>/dev/null | sort -rh | head -10
du -sh /home/*/.npm/_cacache 2>/dev/null
```

Common reclaimable targets (always verify if actively used):

| Path | Typical Size | When to Delete |
|------|-------------|----------------|
| `~/.cache/ms-playwright` | 600+M | If not running Playwright tests |
| `~/.gradle` | 500+M | If no Java builds |
| `~/.insightface` | 600+M | If not doing face rec on host |
| `~/.rustup` | 1.4G | If not compiling Rust |
| `~/.cache/go-build` | 70+M | If no Go builds |
| `~/.cache/uv` | 70+M | If no UV pip installs |
| `~/.npm/_npx` | 180+M | Temp npx caches |
| `~/.npm/_cacache` | 60-200M | `npm cache clean --force` |
| `~/.hermes/lsp` | 160+M | If no IDE connected |
| `~/.antigravity-ide-server` | 350+M | If no IDE connected |
| `~/.cursor-server` | 350+M | If no IDE connected — always on VPS |
| `~/.venvs/` (plural) | 400+M | Multiple unused Python venvs. Check `du -sh ~/.venvs/*/` |
| `~/.cache_git_backup_*` | 100–200M | Old git repo backups, safe if data backed up elsewhere |

**Pattern**: always check `docker exec` or `grep` to verify the host cache is actually used by running containers before deleting.

## 8. Clean Old Kernels + APT Cache + Java

```bash
# List all kernel packages
dpkg -l | grep -E 'linux-(image|modules)-[0-9]+' | grep -v "$(uname -r)"
dpkg -l | grep -E 'linux-modules-extra-[0-9]+' | grep -v "$(uname -r)"

# Purge old ones — must purge modules-extra FIRST if they depend on modules
sudo dpkg --purge linux-modules-extra-<old> linux-modules-<old> linux-headers-<old>

# Remove Java if unused (check no Docker container uses it)
sudo dpkg --purge openjdk-*-jre-headless openjdk-*-jdk-headless

# Remove unused Go src
sudo dpkg --purge golang-*-src golang-*-go

# APT
sudo apt autoremove --purge -y
sudo apt clean
```

**Pitfalls**:
- `apt autoremove --purge` skips manually-installed kernels. Must purge by name.
- `linux-modules-extra` dependencies block `linux-modules` removal — purge extra first, then modules.
- `dpkg --purge` on golang-* may fail with "dependency problems" when both -src and -go are interdependent. Install one first to break the cycle.

## 8b. Verify unattended-upgrades ACTUALLY installs security patches

`systemctl is-active unattended-upgrades` → `active`, `enabled`, timer firing daily, and a log
saying `No packages found that can be upgraded unattended` is **not** proof it works. Verify the
scope, not the status:

```bash
apt list --upgradable 2>/dev/null | wc -l
apt list --upgradable 2>/dev/null | grep -c 'noble-security'   # or -security for your release
sudo apt-config dump | grep -i 'Allowed-Origins' -A3           # what it will actually install
sudo unattended-upgrade --dry-run --debug 2>&1 | head -3       # 'Allowed origins are: ...'
```

**The failure mode: `Allowed-Origins` lists only the base pocket.** Ubuntu's
`/etc/apt/apt.conf.d/50unattended-upgrades` can ship with the `-security` line commented out:

```
Unattended-Upgrade::Allowed-Origins {
	"${distro_id}:${distro_codename}";              # base pocket — has NO upgradable packages
	//"${distro_id}:${distro_codename}-security";   # the line that actually matters
```

All real updates land in `-security` / `-updates`, so the base-pocket-only list matches nothing,
the run exits "successfully", and security patches pile up silently. Seen with **126 security
updates pending** (openssh, systemd, nginx, libc6, sudo, bind9) on a host that reported healthy.

**Why it never self-heals — check this before assuming an upgrade will fix it:**

```bash
dpkg -S /etc/apt/apt.conf.d/50unattended-upgrades
# 'no path found matching pattern' => NOT a dpkg conffile
```

When it is not a conffile, the package only ships a template to
`/usr/share/unattended-upgrades/50unattended-upgrades`, and upgrading the package **will never
overwrite or repair** the live file. The misconfiguration is permanent until edited by hand. This
distinguishes it from ordinary "host is behind on updates" — do not prescribe `apt upgrade` as the
fix for the config; fix the config, then let the timer do the work.

Fix = uncomment the `-security` line. Verify with `apt-config dump` (origin list now includes
`-security`) and a `--dry-run --debug` that prints `Checking:` per package instead of
`No packages found`. Note `--dry-run --debug` is slow on a host with 100+ pending packages
(multi-minute; expect a timeout in a 300 s window — take the first 3 lines and move on).

**Kernel will ride along and needs a reboot.** The kernel metapackage is usually `-security` too,
so the fix schedules a new kernel. Confirm `Automatic-Reboot` is unset/false (the default) so the
box does not reboot itself, and warn the user that activating it needs a reboot — which restarts
every container and service. Also check `/boot` headroom first: on hosts where `/boot` is not a
separate partition it shares `/`, so the "disk full during kernel install" failure does not apply.
Leave `Remove-Unused-Kernel-Packages` off deliberately so the old kernel stays as a rollback path,
then enable it once the new kernel proves stable.

**Corroborate urgency with exposure, not adjectives:**

```bash
sudo journalctl --since '7 days ago' | grep -c 'Failed password\|Invalid user'
for j in sshd ufw-block nginx-botsearch; do sudo fail2ban-client status $j; done
```

## 9. Node_modules Audit

Running projects need their deps, but stale projects waste 500M-1.5G each:

```bash
# Find biggest node_modules
find /home -maxdepth 4 -name "node_modules" -type d -exec du -sh {} \; 2>/dev/null | sort -rh | head -10

# Check if the project is actually deployed
pm2 list 2>/dev/null                     # PM2 apps
docker ps --format "{{.Names}}"          # Docker services
git -C /path/to/project log -1 --format="%ai"  # last activity

# Categorize: Docker → safe, pm2 → keep, Vercel → safe, stale → safe
```

**Key insight**: don't blanket-delete all `node_modules`. Map each project to its deployment method first. Docker-based projects have deps inside the image. Only pm2/systemd apps need host node_modules.

See `vps-node-cleanup-recovery` skill for the full deployment-mapping methodology and recovery procedures.

## 10. Swap Tuning

### Diagnose swap root cause

Docker stats shows container RSS inside each cgroup. Heavily swapped processes show **low RSS** because pages are on disk. Use VmSwap from /proc to find real swap hogs:

```bash
for pid in $(ps aux --sort=-%mem | awk '{print $2}'); do
  swap=$(grep VmSwap /proc/$pid/status 2>/dev/null | awk '{print $2}')
  if [ -n "$swap" ] && [ "$swap" != "0 kB" ]; then
    comm=$(head -1 /proc/$pid/comm 2>/dev/null)
    echo "$swap $pid $comm"
  fi
done | sort -rh | head -15
```

Common swap hogs on 3.6G RAM VPS:
- WhatsApp API Node process (>7d uptime, memory leak) — 600-700MB swap
- Uvicorn workers inside Docker containers — 600-700MB each (pages paged out)
- Hermes gateway (large Python venv) — 400-500MB
- MariaDB / Postgres buffer — ~200MB

**Remediation priority:** restart long-running Node apps first (frees most swap, zero service risk), then `docker compose restart` swapped uvicorn workers (they page back cleanly), then set Docker RAM limits + swappiness.

### Reduce swap tendency

```bash
sudo sysctl -w vm.swappiness=1
echo "vm.swappiness=1" | sudo tee -a /etc/sysctl.d/99-swap.conf

# Check current swap drain
free -h
swapon --show
```

Swap drain is gradual — with Docker RAM limits + swappiness=1, swap usage drops over hours as processes settle.

## 11. Nginx Hardening

In `nginx.conf` http block:
```nginx
server_tokens off;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "0" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_conn_zone $binary_remote_addr zone=addr:10m;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
gzip on; gzip_vary on; gzip_proxied any; gzip_comp_level 6;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;
client_body_buffer_size 16k; client_header_buffer_size 1k;
client_max_body_size 20m; client_body_timeout 12; client_header_timeout 12;
```

Apply: `sudo nginx -t && sudo nginx -s reload`

## 12. Weekly Docker Auto-Prune

```bash
(crontab -l 2>/dev/null; echo "0 3 * * 1 docker system prune -af --filter 'until=24h' >/dev/null 2>&1") | crontab -
```

## Verify

```bash
sudo ufw status verbose
sudo fail2ban-client status
ss -tlnp | grep "0.0.0.0:"  # only 22,80,443
curl -sI http://localhost/ | grep -E "X-Frame|X-Content|Referrer"
df -h; free -h
docker stats --no-stream
```
