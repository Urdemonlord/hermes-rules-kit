# Disk Alert Triage — Reference Data (2026-07-04 to 2026-07-14)

## VPS: 59G root, 3.6G RAM, Ubuntu 24.04

## 2026-07-18 session (98% → 75%)

**Trigger**: Watchdog 98% (55G/59G, 1.7G free) + swap 90%

**Root cause**: Docker build cache (5.7G) + accumulated logs (syslog 372M, journal 257M, whatsapp-api 118M) + npm cache (327M) + uv cache (248M). Docker images 17GB but all in-use by 14 running containers. Containerd blob store 17GB — necessary infrastructure.

### Cleanup

| Step | Action | Saved | Risk |
|------|--------|-------|------|
| 1 | `docker builder prune -af` | 5.7G | None |
| 2 | `sudo truncate -s 0 /var/log/syslog` | ~372M | None |
| 3 | `sudo journalctl --vacuum-size=100M` | ~257M | None |
| 4 | `npm cache clean --force` | ~327M | None |
| 5 | `uv cache clean` | ~248M | None |
| 6 | `/tmp` stale files (tgz, db, html, jpg) | ~50M | None |
| 7 | `sudo truncate -s 0 /var/log/whatsapp-api/*.log` | ~118M | None |
| 8 | `docker image prune -f` | 0B | None — no dangling images |
| **Total** | | **~7.1G** | |

**Result**: 98% → 75% (55G → 43G, 1.7G → 15G free)

### Key observations

- **Build cache hit 5.7G** — second occurrence in 4 days (was 5.3G on Jul 14). Weekly `vps-cleanup` cron alone isn't enough; build cache regrows fast with active Docker builds.
- **`du -sh /tmp` without sudo can mislead**: showed 2.8G but `sudo du -sh /tmp` revealed only 50M. Sticky-bit files owned by other users cause `du` to report directory inode size without descending. Always use `sudo du` for ground-truth on `/tmp`.
- **14 Docker containers on 3.6G RAM** — swap at 87% is chronic, not a disk issue. Memory overcommit, not a cleanup problem.
- **`docker image prune -f` returned 0B** because all 11 images are referenced by running containers. Only `prune -a` would free space, but risks removing needed images.
- **`uv cache clean` freed 248M** — uv cache regrows from `uv run`/`uv pip install`. On this VPS with active Hermes (uv-managed), expect 200-300M accumulation between cleanups.
- **WhatsApp API logs** (`/var/log/whatsapp-api/out.log` + `combined.log` = 118M) are a recurring target — PM2 app with persistent output logging.

## 2026-07-14 session (88% → 75%)

**Trigger**: Watchdog 88% (50G/59G, 7.3G free)

**Root cause**: Docker build cache (5.3G) + IDE server caches (720M) + unused venvs (415M) + swap3 with 0B used (512M) + playwright cache (646M) + thesis-pipeline node_modules (600M) + git backups (135M) — accumulated between cleanups.

### Cleanup

| Step | Action | Saved | Risk |
|------|--------|-------|------|
| 1 | `docker builder prune -af` | 5.3G | None |
| 2 | Snap old revisions | ~100M | Low |
| 3 | Hermes session dumps | 2M | Low |
| 4 | `rm -rf ~/.cache/ms-playwright/` | 646M | Low — playwright not used by any service |
| 5 | `swapoff /swap3.img && rm /swap3.img` | 512M | Low — 0B used |
| 6 | `rm -rf ~/.cursor-server ~/.antigravity-ide-server` | 720M | Safe — no IDE connected |
| 7 | `rm -rf ~/.venvs/` | 415M | Low — unused |
| 8 | `rm -rf ~/.cache_git_backup_*` | 135M | Safe |
| 9 | `rm -rf thesis-pipeline/node_modules` | 600M | Safe — not deployed |
| **Total** | | **~8G** | |

**Result**: 88% → 75% (50G → 42G, 7.3G → 15G free)

### Key observations

- **`docker builder prune` ≠ `docker system prune`.** 5.3G build cache untouched by system prune alone. Always run both.
- **Playwright cache (646M) persisted from past Playwright tests.** No running service uses it.
- **swap3 with 0B used can be safely dropped** on 3.6G RAM VPS with 3.9G remaining swap.
- **IDE server dirs (.cursor-server, .antigravity-ide-server)** accumulate on VPSes where no IDE is ever connected — always safe to clear.
- **`~/.venvs/` (plural)** is separate from `~/.venv/` (singular). Whole dir was unused.
- **thesis-pipeline not dockerized, not pm2-managed** — node_modules safe to drop.

## 2026-07-06 session (94% → 76%)

... (previous content unchanged) ...
