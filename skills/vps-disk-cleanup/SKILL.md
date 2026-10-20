---
name: vps-disk-cleanup
description: Use when freeing disk space on a Linux VPS or server.
---

# VPS Disk Cleanup

Audit first, execute second, verify after. Never delete before the user confirms scope.

## Audit commands (read-only, run these first)

```bash
df -h; df -i                                    # ruang + inode
du -xh --max-depth=1 / 2>/dev/null | sort -rh   # top dir
du -xh --max-depth=2 /home /var /usr | sort -rh
```

Then drill into candidates: `~/.cache`, `~/.npm`, `~/.hermes`, node_modules, venv, `.git`, logs.

## Zero-risk to delete (safe without asking)

| Target | Command |
|---|---|
| Docker build cache | `docker builder prune -af` (often the biggest win) |
| npm cache | `npm cache clean --force` |
| uv cache | `uv cache clean` |
| npx cache | `rm -rf ~/.npm/_npx/*` |
| systemd journal | `sudo journalctl --vacuum-size=50M` |
| old kernels | `sudo apt-get autoremove --purge` |

## Requires user decision (never delete unilaterally)

- Browser automation caches (`~/.cache/ms-playwright`, `camoufox`, `puppeteer`) — re-downloaded on next use
- pnpm store — `pnpm store prune` (safe subset only)
- `/tmp` contents — inspect first, many files are live
- Hermes checkpoints — git-backed, GC rather than rm

## NEVER delete

- **Docker images/volumes of running apps** — `docker system prune -a` kills live services. Check `docker ps` first.
- `node_modules` / `.git` of active projects
- Anything you cannot explain

## Pitfalls

- **`du` on Docker dirs lies without sudo.** `du -sh /var/lib/docker` may report 4.0K while Docker reports GBs. Re-run with `sudo`, and check `/var/lib/containerd` too (containerd-backed Docker stores snapshots there, not in `/var/lib/docker`).
- **Systemd system services can embed `node_modules` paths in `ExecStart`.** `systemctl --user` misses them. Grep all `/etc/systemd/system/*.service` before blanket-deleting dependency dirs, or you silently break a service.
- **`docker system df` "RECLAIMABLE 100%" on images does not mean they are unused** — it means they are not shared. Deleting removes running apps' images.
- **A suspected duplicate must be hash-verified, never size-matched.** Two model
  directories at the same reported size held *different* weights; `sha256sum` on
  the largest file decided it. The candidate was `.gitignore`d, so deleting the
  "copy" would have destroyed a distinct trained artifact with no way back.
  Equal `du` output is not evidence — run the hash and report both hashes when
  they differ.
- **A host directory is not runtime data just because a container uses it.**
  `docker inspect <container> --format '{{json .Mounts}}'` returning `[]` means
  no host bind mounts: the code/model is baked into the image (`COPY ...` in the
  Dockerfile, `ENV MODEL_PATH=...`). The host copy is a *build input* — deleting
  it breaks the next image build and is invisible from the running service.
  Treat it as user-decision, not zero-risk.
- **Browser caches are the safe batch-one win, but still ask.**
  `~/.cache/ms-playwright` + `~/.cache/puppeteer` measured 658M + 581M = 1.2 GB
  on this host and re-download on next use; the screenshot skills stop working
  until then. Report the freed number from `df -h /` before and after, not the
  `du` of the directory you removed.

## Verified cleanups on 203.0.113.10 (2026-10-05, 89% -> 76%)

Biggest real wins, in the order they mattered:

| Target | Freed | Note |
|---|---|---|
| `docker builder prune -af` | 2.93 GB | The only safe Docker win — build cache, not images |
| `~/.gradle/caches` etc. | 1.8 GB | Gradle build cache is dead weight when local Android builds are prohibited (shared prod host) |
| `/opt/<project>/.assets/models` (facefusion) | 1.9 GB | Not running, no systemd unit, no cron reference. Repo/compose intact -> models re-download on next run. Inventory the files with `ls -la > /tmp/<name>.txt` first. |
| Old release APKs in `/var/www/<app>/` | 528 MB | 54 the player APKs, only the one in `update.json` was referenced. **Move to a staging dir first, verify the live artifact still returns 200, then delete the staging dir** — not `rm` in place. |
| `/tmp` build residue (`dexout`, `m3check`, `<tool>-res`) | ~460 MB | |

Config cap: `~/.hermes/config.yaml` -> `checkpoints.max_total_size_mb`. `hermes
checkpoints prune -f` on a store already at its cap reclaims almost nothing (26.9
KB observed). Do not expect it to be the win.

Never touch: `uv cache clean` hung for >90 s and the 481 MB in
`~/.local/share/uv` is `uv/tools` (installed tools), not cache — deleting it
breaks tool installs. Kill the command if it hangs.

## Verified cleanup 2026-10-05 (87% -> 77%, +6.5GB)

`docker builder prune -af` reclaimed **6.544GB** (build cache only). Nothing else
was needed.

Cause: three back-to-back `docker compose build app` runs on iki-tenun. Each SvelteKit
build (npm ci + vite build + Prisma) leaves ~2GB of cache layers, and Build Cache grows
to N x that with no bound. **Expect ~2GB of cache per Docker build and prune after
deploy batches, not weekly.**

What was deliberately NOT touched:

| Left alone | Size | Why |
|---|---|---|
| `Images` 13.63GB / "99% reclaimable" | 13.55GB | Flag means "not shared", NOT "unused". All 11 images are referenced by a running container. `docker system prune -a` would take down every live app. |
| `/home/user/iki-tenun/node_modules` | 478M | Needed by `npm run check` / vitest; deleting it re-costs 447MB + 30s and Prisma's postinstall does not run. |
| `~/.npm` | 197M | Below the pain threshold; the win is small. |
| `/tmp/*` | ~40MB | Already negligible. |
| `node:22-slim` image | 329MB | Unreferenced build base, but `builder prune -af` already reclaimed its cache layers. |
| journal | 48.5M | Already under the 50M cap. |

## Containerd backend: `docker builder prune -af` can reclaim 0B (verified 2026-10-09)

This host stores snapshots in `/var/lib/containerd` (18G), not `/var/lib/docker`.
`du` on `/var/lib/docker/overlay2` reports nothing useful; check
`sudo du -sh /var/lib/containerd`.

Symptom: `Build Cache 0B` in `docker system df` AND `Total reclaimed space: 0B`
from `builder prune -af`, yet `df` shows the space freed anyway. Reclaiming build
layers does **not** show up as build cache in the df output.

What actually works: name the images explicitly.

```bash
docker images -f dangling=true --format '{{.ID}} {{.CreatedAt}}'   # untagged leftovers
docker rm <exited-container>                                        # holds its image alive
docker rmi <dangling-id> [<other-id>]
```

Order matters — deleting the image first fails or leaks while an exited
container still references it. `docker system df -v` shows the CONTAINERS column;
`0` means no live reference.

Live container can run a snapshot ID absent from `docker images` (containerd
leak from a tag overwrite: `iki-tenun-app-1` ran `156c7179e942` while
`docker images` only listed `e1d6f613a4d2`). Pruning the unused `latest` tag
works, but a later `docker compose up -d` cannot just re-create — no matching
image ID, so it rebuilds from scratch (~2GB cache). Warn the user before
deleting the tag that the *next* start is a full build.

Also useful: `docker system df -v` `UNIQUE SIZE` vs `SHARED SIZE`. Two images at
the same repo tag family (e.g. `prompt-check-app:ui` = production, plus unused
`:gate` / `:guard`) show 2.346GB UNIQUE each — big win but **ask the user**,
those tags may be deliberate rollback points.

Verify with `df -h /` before and after; report both numbers.

## `docker compose up -d --force-recreate` **and `docker compose down`** silently no-op (verified 2026-10-09; `down` re-confirmed 2026-10-17)

Not just "does not re-create when the tag is unchanged". On this host
`docker compose up -d --force-recreate app` ran 3 times and returned **empty
output, exit -1, container unchanged** — same image ID, same start time. It
It printed nothing to signal failure. Only `docker compose up -d app` after a
manual `docker rm -f <container>` actually re-created it.

`docker compose down` has the same failure mode: **exit 0, empty output, container
still `Up`**. Never report "container removed" off its return code. Remove it
explicitly, in this order:

```bash
docker rm -f <container>                      # image delete fails before this
docker rmi <repo>:<tag>                       # frees the GB, not the container
docker ps -a --filter name=<container> | wc -l   # must be 0
```

Skipping the `rm` gives `conflict: unable to delete <image> (must be forced) -
container <id> is using its referenced image`, and the disk number does not move
at all. Leaving the compose file in place keeps the service restorable with a
single `docker compose up -d` (re-pull, then `up`).

Do not report a deploy off the `up -d` return code. Verify:

```bash
docker inspect <container> --format '{{.Image}}'
docker images <repo>:latest --format '{{.ID}}'
```

Both must match. Also: the terminal tool refuses `docker compose up -d` as a
"long-lived server process" — run it with `background=true, notify=true`, then
poll the health endpoint from a separate call.

## Headless-Chrome CDP probe without installing anything

`~/.cache/puppeteer` already holds a Chrome binary, and Node 22 has a global
`WebSocket`. So a real browser check needs zero new dependencies: spawn the
binary with `--headless=new --remote-debugging-port=N`, then speak CDP by hand
(`Page.navigate`, `Runtime.evaluate` with `returnByValue`).

Use it for client-side behaviour that SSR curl cannot prove — filters, router
state, hydration. ~60 lines, no `puppeteer-core`, no `chrome-remote-interface`.

Gotcha: `agent-browser` in `~/.hermes/node/bin` is a **broken symlink** into
`~/.npm/_npx/...`. Don't try to use it; the raw CDP script works.

## Never pipe `git fetch` to `head`/`tail` — it strands GB of orphan packs

`git fetch origin main | tail -5` kills git with **SIGPIPE** mid-transfer, and `$?` still reads
**0** because you are reading `tail`'s exit code, not git's. Two symptoms that look like a broken
repo and are not:

- `origin/main` never advances, so the checkout looks "stuck on an old commit" (observed: local 18
  Sep vs remote 16 Oct). `FETCH_HEAD` is 0 bytes and `git rev-parse FETCH_HEAD` fails.
- Each aborted fetch leaves an orphan `tmp_pack_*` in `.git/objects/pack/` — **5 files / 1.35 GB**
  after a few attempts, which silently pushed disk 85% -> 88%.

Redirect instead of piping:

```bash
git fetch origin main > /tmp/fetch.out 2>/tmp/fetch.err; echo "exit=$?"
```

Identify orphans: a `tmp_pack_*` with **no matching `.idx`** is an aborted fetch. Legitimate packs
always have both `.pack` and `.idx`. Safe to remove:

```bash
ls -la .git/objects/pack/tmp_pack_*
rm -f .git/objects/pack/tmp_pack_*
git fsck --connectivity-only && git rev-parse HEAD origin/main
```

Verify the disk number before/after — this is a real reclaim, not a rounding artifact.

## Watch for the compose trap

`docker compose up -d app` does **not** re-create the container when the image
tag is unchanged; it prints nothing and the old container keeps running the old
build. Verify with `docker inspect <container> --format '{{.Image}}'` against
`docker images`. Use `--force-recreate` to actually cut over. Reporting "deployed"
off `docker compose up -d` alone is a false claim.

## Verify before reporting success

After cleanup, always confirm workloads still alive:

```bash
df -h /
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

Report before/after numbers, not adjectives.
