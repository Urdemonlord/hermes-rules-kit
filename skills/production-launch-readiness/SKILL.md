---
title: Production Launch Readiness
name: production-launch-readiness
description: Pre-launch hardening for single-instance Docker deployments — disk cleanup, healthcheck configuration, zero-downtime deploy pattern, monitoring setup, and backup verification.
triggers:
  - Launching to production with tight launch window (hours, not days)
  - Need zero-downtime deploy on single VPS instance
  - Must verify backup before launch
  - Disk space critical (VPS <70GB or <20% free)
  - Want automated monitoring + alerting for first week post-launch
  - Entrypoint permission issues surfacing at restart time
  - Container health status unclear
---

# Production Launch Readiness

Hardening checklist for single-instance Docker deployments on VPS before launch day.

---

## Pre-Launch Hardening (30 minutes)

### 1. Disk Cleanup

**Respect the safety tier the user asks for — clean only that tier and report the rest.** When
the user says "only the safe stuff", delete only regenerable caches with zero rebuild cost
(Docker build cache, npm/uv/npx caches, journal vacuum, `/tmp` junk, orphaned kernels) and
**leave browser caches (playwright/puppeteer/camoufox profiles), pnpm store, git gc, and agent
checkpoints/session state untouched** — those are recoverable only by re-downloading or by
losing history, so they need an explicit yes. Present the deferred items as a short list with
sizes so the user can opt in later; do not silently upgrade the tier because a prune looked safe.

**Risk:** Docker images and old layers accumulate. One runaway log or product image upload can fill disk → app crash → data corruption.

```bash
docker system prune -af --volumes
df -h /
# Target: >15GB free (69% usage or better on 60GB disk)
```

**Do not read `docker system df`'s RECLAIMABLE column as reclaimable space.** It reports shared image layers as reclaimable, so a 4-image host can show `8.6GB (99%)` reclaimable while `docker builder prune -f` and `docker system prune -f` both return `0B`. **The column is wrong in BOTH directions, so never act on it alone** — it can also report `Build Cache ... RECLAIMABLE 0` while `docker builder prune -f` actually frees several GB. Judge by what a prune actually returns (its "Total reclaimed space" line), not by the column:

```bash
docker system df                      # the RECLAIMABLE figure is unreliable in both directions
docker builder prune -f               # actual reclaim; never touches images/containers/volumes
CONTAINERS=$(docker ps -q | wc -l); IMAGES=$(docker images -q | wc -l)
docker system prune -f                # stopped containers, dangling images, unused networks
```

**Confirm per image ID before pruning anything — `docker ps` is not enough.** The column tells you nothing about whether a given image backs a *running* container, and on a small host every image usually does. Check each one, and treat any that prints a container as off-limits:

```bash
for id in $(docker images -q); do
  docker ps -a --filter ancestor=$id --format "$id <- {{.Names}} ({{.Status}})"
done
```

On a host where all images print a running container, the honest answer is **0 reclaimable from images** — say so rather than running `prune -a` and taking the services down.

**Read the `UNIQUE SIZE` column, not `SIZE`, when deciding what an image is worth removing.** `docker system df -v` reports both: `SIZE` includes layers shared with other images, `UNIQUE SIZE` is what actually returns to disk. An image listed at 3 GB may free only a fraction. The same table's `CONTAINERS` column is the faster gate — non-zero means it is in use and cannot be removed at all. Four images showing `CONTAINERS 0` on a 15-image host are typically three base images plus one builder, i.e. ~350 MB total, most of which re-downloads on the next build.

**Never state a size you did not measure.** An invented figure in a cleanup report ("there is ~5 GB of unused images to delete") is worse than no estimate: when the user follows up on the number it has to hold up, and the real total may be an order of magnitude smaller. Derive every figure from a command's actual output; if you cannot, say "unmeasured" and run the command. When a follow-up shows an earlier number was wrong, lead with the correction — including the rows of your own table that were wrong — rather than quietly restating the smaller figure.

An already-clean host legitimately returns `0B` — that is a valid result to report, not a failure to investigate. Before deleting an unused-looking image, check whether it is a build base for a running service: `grep -rl "python:3.10-slim" ~/project/*/Dockerfile*`. Removing a base image that a live service rebuilds from saves ~200MB and costs a full re-download on the next build.

**When images and build cache are all spoken for, the real space is in crash artifacts and caches outside `/var/lib/docker`.** A process that died on OOM leaves a heap dump (`*.hprof`) or core dump beside its project — routinely 1 GB+ each, easy to miss because it sits in a project directory, not a cache directory. It is a regenerable diagnostic, not user data, but prove it first:

```bash
file <dump>.hprof                              # "Java HPROF dump" => diagnostic artifact
pgrep -af '<runtime>'                          # empty => no live process holds it
grep -n 'hprof\|core\.' <project>/.gitignore   # already ignored => never committed
systemctl list-units --type=service | grep -i <project>   # empty => service not running
```

All four agreeing makes it safe; a dump owned by a *running* service is not. Then `rm -f *.hprof core.*`. Also clear `~/.npm/_cacache` (`npm cache clean --force`) and `~/.npm/_npx` (a separate store, `rm -rf ~/.npm/_npx/*`) and `sudo apt-get clean`.

**Log growth is usually the real cause of a creeping disk, and vacuum alone does not fix it.** When `/var/log` (typically the systemd journal) is the largest item, a one-shot `sudo journalctl --vacuum-size=200M` reclaims the space but the journal refills within days. Cap it persistently via a drop-in — never edit `/etc/systemd/journald.conf` directly (package updates clobber it):

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/size-limit.conf >/dev/null <<'EOF'
[Journal]
SystemMaxUse=200M
SystemKeepFree=1G
MaxRetentionSec=2week
EOF
sudo systemctl restart systemd-journald
sudo journalctl --disk-usage   # confirm the cap took effect
```

`SystemKeepFree=1G` guarantees the journal never eats the last gigabyte. Also check `/var/log/syslog.1` — rotated syslog is often another 100M+; truncate it (`sudo truncate -s 0 /var/log/syslog.1`) rather than deleting the file, so rsyslog keeps writing to the same inode.

**Identify WHICH service is spamming the log before truncating — the file is a symptom, the source refills it within a week.** A public VPS with a firewall logging every blocked scan packet (`[UFW BLOCK]`) can add tens of thousands of syslog lines per week on its own; truncating syslog.1 frees today's 110M and the next one is back next week. Find the dominant writer, then fix it at the source:

```bash
sudo awk '{print $5}' /var/log/syslog | sort | uniq -c | sort -rn | head   # top repeated fields = spammer
```

For firewall noise, either lower `LOGLEVEL` in `/etc/ufw/ufw.conf` (e.g. `LOGLEVEL=low`) or add a fail2ban rule so repeat scanners get banned instead of logged. Truncate/rotate first to reclaim the space, then fix the source so it does not regrow.

**Old kernels: the module tree lingers after the package is purged.** Purging an old kernel (`sudo apt-get purge -y linux-image-<old> linux-headers-<old>`) removes the `/boot` files but dpkg's `rmdir` of `/lib/modules/<old>/` fails with `Directory not empty`, leaving ~150M behind. Check `du -sh /lib/modules/*` and remove stragglers with `sudo rm -rf /lib/modules/<old-ver>` — never the version from `uname -r`. Clear leftover config-only packages too: `sudo apt-get purge -y $(dpkg -l | awk '/^rc/ {print $2}')`.

**Remove temp/build files:**
```bash
cd ~/project
rm -f shopee*.json shopee*.csv shopee*.sql inserted-products.json
rm -rf scripts/migrations build-tmp/
git clean -fdx    # if safe
```

**`/tmp` is not blanket-safe — enumerate before deleting.** On an active dev VPS `/tmp` holds live artifacts, not just junk: SQLite dev DBs (`*-dev.db`, `live-dev.db`), env files (`*.env.production.txt`), config text, generated JSON, and script tools (`*.js/.cjs/.mjs/.py`). Never `rm -rf /tmp/*`. List by mtime first (`find /tmp -maxdepth 1 -mindepth 1 -mtime +7 -exec du -sh {} \; | sort -rh`), then delete only clearly-regenerable junk — automation caches (`puppeteer_dev_chrome_profile-*`, `playwright_chromiumdev_profile-*`, `playwright-artifacts-*`, `org.chromium.Chromium.*`), `node-compile-cache`, `node_modules`, and stale review screenshots (`*.png`). Skip anything matching `*.db`, `*.env*`, `*.txt`, `*.json`, `*.conf`, and script files — those are live state or tools. Treat `-mtime +7` as a hint, not a license.

**A multi-GB file in `/tmp` may be an abandoned snapshot — prove it with four independent checks before deleting.** A killed process leaves `tempfile.TemporaryDirectory()` content behind; a multi-GB SQLite file can sit in `/tmp` for days. Do not judge by name or size:

```bash
stat -c '%i %s %y' /tmp/file.db ~/.hermes/state.db   # different inode => not a hardlink to live data
fuser /tmp/file.db                                    # empty => no process holds it open
ls -la /tmp/file.db                                   # old mtime => abandoned
find /tmp -maxdepth 1 -name 'tmp*' -newermt '-1 day'  # not being rewritten right now
```

For a database, add an identity test — `select * from state_meta where key='db_file_generation'`. An **identical generation** means it is a snapshot of the same store; if its row counts are *lower* than the live DB, it is a stale copy, not a source of truth. A file that fails all checks is safe; one that passes any is not.

**npm cache is two stores, not one.** `npm cache clean --force` clears `~/.npm/_cacache` only — it leaves `~/.npm/_npx` (the npx package cache, often 400–650M) untouched. Clear that separately with `rm -rf ~/.npm/_npx/*`.

**Build-tool caches are usually the single biggest reclaimable item after a build-heavy session, and they live OUTSIDE `~/.cache`.** A Gradle cache (`~/.gradle/caches`) routinely reaches several GB after repeated Android/Kotlin builds; `.m2` grows the same way. They are re-downloaded on the next build — but they are NOT in the `~/.cache` tree, so a `~/.cache/*` audit misses them entirely. Check both roots:

```bash
du -sh ~/.gradle ~/.m2 ~/.cache 2>/dev/null | sort -rh
ps aux | grep -c '[G]radleDaemon'    # must be 0 before removing ~/.gradle/caches
```

Confirm no build is running before deleting (`./gradlew --stop` first if a daemon lingers) — removing the cache under a live build corrupts the build, not just the cache.

**Three more verified-safe candidates — each gated on a check, because size alone is not proof.**
On a dev VPS these are routinely hundreds of MB each and are missed by a `~/.cache` audit:

| Candidate | Precondition to verify first | Typical |
|---|---|---|
| **Duplicate copy of a tool/wrapper dir** | the copy you delete is unreferenced: not on `PATH` (`echo $PATH \| tr ':' '\n' \| grep <tool>`), and the copy the build system actually uses still exists. A standalone `gradle-8.11.1/` in `$HOME` byte-identical to `~/.gradle/wrapper/dists/gradle-8.11.1-bin` is the deletable one | 100–500M |
| **Already-extracted source tarball** | `tar -tjf <f> \| wc -l` ≈ `find <dir> -type f \| wc -l`, and the dir has its `bin`/`launcher`/`src` subdir populated | 100–500M |
| **`node_modules` of a clean, non-served repo** | all three: `git status` clean AND not in `/etc/nginx/sites-enabled/` (`grep -r <name> /etc/nginx/sites-enabled/`) AND no running process from that dir | 500M–1G |

**A build artifact dir refills itself — kill the producer, not just the directory.** If the project
builds in CI (GitHub Actions etc.), a local `npm run tauri dev` / `cargo build` watcher serves no
purpose on the VPS but rewrites the artifact dir (multi-GB) on the next `git pull`. Kill the whole
process tree, then delete, then confirm nothing restarts it:

```bash
ps -eo pid,ppid,args | grep -E 'tauri dev|target/debug/<app>|node .*vite' | grep -v grep
for p in <app> <vite> <node> <sh> <npm> <bash -lic>; do kill -TERM $p; done   # children before parents
systemctl --user list-units --type=service | grep <app>    # no unit = stays down
```

**A build cache belonging to an ACTIVE project is ask-first, not free-to-delete — even though it is technically regenerable.** A Rust `target/` dir (often the single largest dir on a dev VPS, 4–5G) or `.gradle/caches` is rebuildable, but a recently-built `target/` is a warm cache whose deletion forces a full rebuild of a project the user is still working on. Detect recency and surface it as a ranked choice rather than removing it unilaterally:

```bash
du -xhd3 /home 2>/dev/null | grep -E '/target$|\.gradle$' | sort -rh | head
stat -c '%y %n' /path/to/target   # recent mtime => active project, do not delete silently
```

**Before deleting a build cache, prove nothing is compiling into it RIGHT NOW — recent mtimes are not proof.** A dev server that is merely *running* (`npm run tauri dev`, `cargo run`) looks busy but is usually idle; conversely a `git pull` triggers a one-off rebuild that writes files then goes quiet, so `find -newermt` alone gives a false positive either way. Gate on the compiler process and the load average, not on mtimes:

```bash
ps -eo pid,etime,pcpu,args | grep -E '/rustc |cargo (build|run)|tauri dev' | grep -v grep   # active compiler?
uptime                                                                                      # load average
df -h /                                                                                     # baseline before/after
```

An idle dev server shows **0% CPU and no `rustc`/`cargo` child**; only then is `rm -rf <target>/debug` safe. Two consequences to state to the user first:

- A **running binary keeps executing after its file is unlinked** (already mapped into memory), so the dev server does not crash — but it can no longer hot-reload, and the next source change forces a **full recompile** (minutes, and the 4 GB regrows). Killing the idle dev server is usually the better trade than deleting its artifacts under it.
- **The reclaim is not durable on a build host.** `target/`/`dist/` refill on the next build, so re-check `df -h /` at the start of the next session rather than trusting the last reported figure — and say so, instead of implying the disk is fixed.

Only `~/.gradle/caches`, `~/.cargo/registry`, and `~/.cache/*` on a box with **no** active Rust/Java builds are safe zero-decision deletes. **`~/.gradle/wrapper` and `~/.rustup` are toolchains, not caches** — `wrapper/` holds the pinned Gradle distribution and `~/.rustup` holds the Rust toolchain; deleting either breaks the next Android/Rust build instead of merely slowing it. Delete the cache subdirs (`caches/`, `daemon/`, `native/`) and leave the wrapper/toolchain intact. When the user says keep, report the deferred items with sizes and move on — do not silently upgrade the tier because the cache "looks rebuildable".

**A big cache is not automatically unused — prove nothing live depends on it before deleting.** The presence of a tool name in some `package.json` is a *dependency*, not proof of current use. The deciding evidence is a live process or an enabled unit/cron:

```bash
ps aux | grep -icE '[p]laywright|[c]amoufox|[p]uppeteer'                 # 0 = nothing live
sudo grep -rl '<tool>' /etc/systemd/system/ /etc/cron* 2>/dev/null      # empty = no scheduled user
grep -rl '<tool>' /home/*/package.json 2>/dev/null                       # dependency only, not proof
```

If a systemd unit or cron references the cache, leave it alone regardless of size.

**Do NOT touch Docker volumes while chasing disk space.** `docker system df` lists a volume as `RECLAIMABLE` whenever no *running* container mounts it — which includes the data volumes of a stopped stack (databases, uploads). Volume removal is irreversible and a few tens of MB is never worth the risk. Prune **build cache** (`docker builder prune -f`) and leave volumes alone; before `docker image prune`, confirm each image is not the one a running container uses.

**After any prune, verify nothing broke.** Confirm every container is still running healthy before declaring success: `docker ps --format "table {{.Names}}\t{{.Status}}"`. A cleanup that freed 7G but killed a running app is a failure, not a win — report the before/after `df -h /` alongside the container-status line as proof.

**A non-200 on a service you did not touch is not proof you broke it — establish the baseline.** During verification a domain may return `404` (or `301`) and look like collateral damage. Confirm the service's *actual* role before reporting: an app whose root serves no `index.html` (an APK/download host, an API-only service) legitimately 404s at `/` while its real endpoints return 200. Check the live artifact rather than the bare host — `curl` a known file or API path, and read the nginx `root`/`proxy_pass` to see what the host is supposed to serve. Only report a regression you have shown is new.

**A recurring watchdog "disk high" alert means the box is chronically full — clean the safe tier, then tell the truth about what remains.** Do not chase a percentage by reaching into another project's images, volumes, DBs, model files, or agent state. The deliverable is: audit → clean the zero-risk tier → report `df -h /` BEFORE/AFTER as numbers plus a ranked table of what you deliberately left alone (size + risk) so the user can opt in. Moving usage by only a few percent is a normal outcome here — say so plainly instead of framing it as fixed, and expect the alert to re-fire; that is the monitor working, not a failure.

**Audit hidden dirs explicitly — `du /home/*` skips every dot-dir.** The biggest consumers are almost always `~/.gradle`, `~/.hermes`, `~/.cargo`, `~/.local`, `~/.npm`. Enumerate them with `du -sh /home/*/.[a-z]* 2>/dev/null | sort -rh` before concluding the space is unfindable.

---

### 2. Healthcheck Configuration

**Risk:** Load balancer or nginx can't tell if app is ready. Sends traffic to container still starting → 502s, false downtime alerts.

**Add to compose.yaml:**
```yaml
services:
  app:
    healthcheck:
      test: ["CMD", "node", "-e", "fetch('http://localhost:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 30s
```

**Verify before launch:**
```bash
docker compose up -d
sleep 35
docker inspect --format='{{.State.Health.Status}}' <container>
# Expect: "healthy"
```

---

### 3. Backup Verification

**Risk:** Backup cron runs silently. First time you need it post-launch, it's broken or truncated.

**Trigger backups from the write path and an existing heartbeat — never from a cron
the box may not run.** A self-hosted single-box app has two kinds of irreplaceable
state and they need different triggers. A rotating credential is written from one
function, so snapshot inside that function: one write path means there is no second
route that can rotate the token without archiving it, and the archive is taken at
exactly the moment the value is still valid. A database has no single write point,
so ride whatever heartbeat the app already has — a successful upstream refresh,
typically every few hours — rather than adding a timer. Benefits: zero new moving
parts, nothing to supervise, and no growth while the service is down. Inline the
snapshot rather than dynamically importing the backup module when the calling
function is synchronous: an async import returns a promise, so the rotation lands
and the archive silently does not. Wrap every snapshot in a try/catch that logs —
a backup failure must never be able to fail the credential write, or the health
endpoint pages the operator for something that is not urgent.

**Retention is a count, not a date.** Keep the last N snapshots regardless of
uptime: N recoverable states is a guarantee, while a date policy silently produces
one backup per day on an idle box and none at all on a busy one. Nothing else prunes
that directory.

**Verify each snapshot on write, then discard it if it fails.** Reopen it and
check the tables it exists to protect. A backup that is never verified is a hope,
and the truncation is discovered during the restore it was supposed to prevent.

```bash
# Check backup exists and is recent
ls -lh ~/project/backups/ | head -3
# Expect: file from today, size >10KB

# Restore test — verify data integrity
cd /tmp
gunzip -c ~/project/backups/latest.db.gz > test_restore.db
sqlite3 test_restore.db "SELECT COUNT(*) FROM User; SELECT COUNT(*) FROM Product; SELECT COUNT(*) FROM Order;"
# Expect: rows returned, no errors
rm test_restore.db
```

**If cron backup missing:**
```bash
# Manually backup now
docker exec <container> sh -c 'sqlite3 /data/dev.db ".backup /tmp/backup.db"'
docker cp <container>:/tmp/backup.db ~/project/backups/manual_$(date +%s).db.gz
```

---

### 4. Permission Escalation Fix (if needed)

**Risk:** Container restarts after launch, login/checkout endpoints fail with 500 "readonly database".

**Check if vulnerable:**
```bash
docker logs <container> | grep -i "readonly\|USER app\|permission"
```

**If vulnerable, fix Dockerfile/entrypoint now:**
```dockerfile
# Dockerfile — REMOVE "USER app" before ENTRYPOINT
RUN groupadd -r app && useradd -r -g app -s /bin/sh app
RUN chown -R app:app /app /data
# NO USER app here
EXPOSE 3000
ENTRYPOINT ["/docker-entrypoint.sh"]
```

```bash
# docker-entrypoint.sh
#!/bin/sh
set -e
chown -R app:app /data 2>/dev/null || true
npx prisma migrate deploy
exec node build
```

---

## Zero-Downtime Deploy Pattern

### Single-Instance Rolling Swap

For minimal downtime on single VPS:

```bash
cd ~/project

# 1. Build new image (old container still serving)
docker compose build app

# 2. Rolling swap — ~1-3 second gap
docker compose up -d --no-deps app

# 3. Verify health
sleep 35
docker inspect --format='{{.State.Health.Status}}' <container>
# Expect: "healthy"
```

**Total downtime:** ~2 seconds.
**Why so fast:** Node.js startup is quick, healthcheck passes after 30s start_period.

### Redeploying an existing service (new image / new artifact)

When you replace a running service with a rebuilt image (new code, new model artifact, new config):

```bash
# 1. Tag the RUNNING image first — :latest is about to be overwritten
docker tag <image>:latest <image>:rollback-$(date +%Y%m%d)

# 2. Build the new image (old container keeps serving)
docker build -t <image>:latest -f <Dockerfile> .

# 3. Smoke-test the NEW image on a scratch host port — do NOT swap yet
docker run -d --name <svc>-test -p 127.0.0.1:8099:8000 <image>:latest
curl -s http://127.0.0.1:8099/health
# run real probes, confirm the SEMANTIC change (new labels/version), then:

# 4. Swap
docker rm -f <svc>-test
docker stop <svc> && docker rm <svc>
docker run -d --name <svc> --restart unless-stopped -p 127.0.0.1:<hostport>:<containerport> <image>:latest
```

**Tag before overwrite:** `:latest` is mutable. If you build over it without tagging the running image first, there is no rollback target — the old layers may still exist but you have no name to reference. Tag with a dated rollback tag before every build.

**Smoke-test on a scratch port, and assert the semantic change.** A container that answers 200 is not proof the *new* artifact is live. Read the change out of the service itself — e.g. `/health` echoing the label set or model version — and confirm it differs from the old one before swapping. A health check alone will happily pass on a container still serving the previous model.

**Give the scratch container its own volume — never the prod one.** The scratch container seeds itself on first boot, so mounting the production volume means the test run creates users, writes orders, and migrates live data. A separate named volume also gives a genuinely empty DB, which is the only way to exercise the first-boot path (migrations + seed) that production already ran months ago.

```bash
docker run -d --name <svc>-test -p 127.0.0.1:8099:3000 \
  -v <svc>_scratch:/data -e DATABASE_URL=file:/data/dev.db ... <image>:latest
```

**Confirm production is untouched before and after.** A build that accidentally retargets the live container looks identical from the outside until data changes. Record the running container's image ID and the public HTTP status, then re-read both after the build:

```bash
docker inspect <prod-container> --format '{{.Image}}'   # before
docker compose build
docker inspect <prod-container> --format '{{.Image}}'   # after — must be identical
curl -s -o /dev/null -w '%{http_code}\n' https://prod.example/
```

An unchanged ID plus a 200 is the proof that nothing was swapped. `docker ps` showing `Up 5 days (healthy)` is *not* enough on its own — a restart resets that text too.

**`:latest` is overwritten by the build even though the running container is not.** The container keeps serving the old image by ID; the tag just points at the new one. So a later bare `docker compose up -d` — by you, a cron job, or the user — silently promotes the new build with no further review. Either tag the build output (`docker compose build` then `docker tag <image>:latest <image>:candidate-<sha>`) or hold the tag until after the swap decision; state plainly in the handoff that the tag has moved, so nobody assumes the running container is pinned to whatever `:latest` now means.

**A feature with a graceful fallback can be silently degraded, not broken.** When a new capability degrades gracefully — a translation/remote-API step that falls back to heuristics, a cache miss that recomputes, an optional enrichment that no-ops — the endpoint still returns 200 and the response still looks plausible, so a status-code check proves nothing. Read the feature's own status field out of the response (e.g. `status: offline_fallback` vs `adapted`) and confirm it reports the *active* path, not the fallback. A feature that always reports the fallback path is not working in production even though every request succeeds.

**A rebuild can silently pull gigabytes of CUDA deps.** If the upstream `requirements.txt` pins `torch` (or similar) without a CPU index, `pip` resolves the default wheel and downloads the full CUDA stack (~3 GB), which can fill a small VPS disk mid-build. Watch `df -h /` and `docker images` during the build; if disk climbs toward full, kill the build, `docker builder prune -af`, and pin the CPU wheel (see `text-classifier-training-deployment`).

### Never report "ready to deploy" without an explicit verified/unverified split

Before anyone deploys, sort every claim into three buckets and report them as such — the user
needs to know the shape of the remaining risk, not a green checkmark.

- **verified** — real tool output proving it, quoted with the status code or return value
- **unverified** — plausible but untested; say *what specifically* was never exercised
- **blocked** — a check that failed, with the actual error

The unverified bucket is the one that matters. Naming it is the whole point of the report: "build
passes and the unit suite is green" is not deploy readiness, because unit tests never exercise the
order-creation path, the container entrypoint, or the build args. Before writing the report, ask
what the *riskiest* edit in the diff would break, and check whether that was actually run — for a
payment or order flow, that means driving a real order end-to-end against the scratch container, not
curling the landing page.

**`npm run build` and `docker compose build` are different claims.** Only the latter proves the
Dockerfile, its `ARG`/`ENV` declarations, and the compose build args. If the diff touched any of
those, the container build is the gate — and an env var the image inlines at compile time (any
`$env/static/public` import) makes the build fail outright when it is missing, which is a
*different* symptom from a runtime misconfiguration. Run the container build even when the host
build is green.

## Launch Verification Checklist

A healthy container is not enough to declare a launch complete. After deploy, verify the live surface in this order:

1. DNS resolves the apex and `www` domains to the intended VPS.
2. The TLS certificate subject/SANs cover the canonical domain.
3. Nginx has an active site file for the new domain and any legacy host is redirect-only.
4. The app answers on localhost when forced through the expected `Host` header.
5. Public HTTPS returns the final page, redirects `www` if needed, and does not expose the legacy hostname.
6. Public HTML contains canonical metadata that matches the live domain.

For a compact command set, see `references/launch-verification.md`.

---

## "Site is down" while the container is healthy — host-wide freeze

A user reports the site "can't be opened" or "can't save anything", yet `docker ps` shows the container `Up (healthy)` and `curl localhost:PORT` returns 200. Do **not** conclude "server is fine" and stop. The failure is one layer down. Check, in order:

```bash
# 1. Reverse-proxy log — 499 = client gave up, 504 = upstream timed out (app HANGING)
sudo grep -E '" (499|504) ' /var/log/nginx/access.log | tail -20

# 2. Kernel OOM — the root cause of a frozen host
sudo journalctl -k --since "24 hours ago" | grep -iE 'oom|killed process|invoked oom'

# 3. Collateral freeze evidence: watchdog timeouts + an unexplained recent reboot
uptime -s
sudo journalctl --since "24 hours ago" | grep -iE 'watchdog|timed out.*Killing'
```

**Reading it:** clean app log + `499`/`504` in the proxy log + OOM lines in the kernel log = the host ran out of RAM and froze; the app never got a chance to answer. `docker inspect <c> --format 'OOMKilled={{.State.OOMKilled}}'` may still read `false` — the *host*, not the container cgroup, was the victim, so that flag does not clear it.

**Fix:** cap the offending container so one service can never freeze the whole box, then recreate:

```yaml
services:
  app:
    mem_limit: 512m
    memswap_limit: 768m
    deploy:
      resources:
        limits: { memory: 512M }
```

```bash
docker compose up -d --force-recreate app
```

**Commit the limit immediately.** A memory limit that lives only in the working tree is one `git checkout` away from disappearing — the freeze returns. Note the limit also changes nothing until the container is recreated (a plain `restart` reuses the old cgroup config).

**Rule out the code bug first.** If the app log shows a real `500` with a stack trace, that is a code bug, not host pressure — a genuine app error logs `500` in the app; host pressure shows as `499`/`504` in the proxy and nothing in the app log. For that path see `sveltekit-runtime-patterns` ().

### Swap that looks full is usually accumulated paging, not a leak — restart the holders

On a long-uptime multi-container host, swap sits at 1–2.5 GB and reads as an emergency. It is
almost always **accumulated page-out from idle containers**, not a leak. The authoritative
per-container figure is the cgroup counter — `VmSwap` in `/proc/<pid>/status` is per-process and
misses the aggregate:

```bash
for c in $(docker ps --format '{{.Names}}'); do
  id=$(docker inspect -f '{{.Id}}' "$c")
  s=$(cat /sys/fs/cgroup/system.slice/docker-$id.scope/memory.swap.current 2>/dev/null)
  [ -n "$s" ] && echo "$((s/1048576)) MB  $c"
  done | sort -rn
```

`docker restart <name>` clears that swap immediately and the container reloads from its volume;
`restart: unless-stopped` brings it back with no manual start. Restarting the holders one at a
time freed ~1.1 GB in a single pass (the STT container alone held ~1.3 GB) with zero data risk.
**This is the default move — do not open a heap-dump investigation first.** A container capped at
384 MB holding 1.3 GB of swap is normal page-out for a long-idle worker, not proof of a bug.

**Confirm real pressure before optimising anything.** PSI shows whether the kernel is actually
stalling:

```bash
cat /proc/pressure/memory     # some avg10=0.46 ... full avg10=0.11 ...
```

`some avg10` under ~1 means no real pressure — the swap is just accumulated paging and will
refill. "Swap is 60% full" is not a problem on its own; do not present it as one.

**Do NOT `swapoff -a` to force swap back into RAM** — it needs free RAM ≥ swap in use and will
thrash or OOM-kill services. Restart the holders instead.

---

## Monitoring Setup (5 minutes)

### Uptime + Disk Alert Script

Create `~/.hermes/scripts/launch-monitor.sh`:

```bash
#!/bin/bash
DISK_USAGE=$(df -h / | awk 'NR==2{print $5}' | tr -d '%')
DISK_AVAIL=$(df -h / | awk 'NR==2{print $4}')
APP_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' iki-tenun-app-1 2>/dev/null || echo "not_found")
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:3301/ 2>/dev/null || echo "000")

# Only alert on problems (no output = silent = OK)
[ "$DISK_USAGE" -gt 85 ] && echo "🔴 DISK CRIT: ${DISK_USAGE}% (${DISK_AVAIL} free)"
[ "$APP_HEALTH" != "healthy" ] && echo "🔴 HEALTH: ${APP_HEALTH}"
[ "$HTTP_STATUS" != "200" ] && echo "🟡 HTTP ${HTTP_STATUS}"
```

### Schedule Cron (via hermes)

```bash
# Every 5 minutes, silent if OK, alert if problem
hermes cron create \
  --name launch-monitor \
  --schedule '*/5 * * * *' \
  --script launch-monitor.sh \
  --deliver telegram:YOUR_CHANNEL
```

---

## Launch Day Checklist

| Time | Task | Command |
|------|------|---------|
| T-30m | Disk cleanup | `docker system prune -af && df -h /` |
| T-30m | Backup verify | `gunzip -c backups/latest.db.gz \| sqlite3 - "SELECT COUNT(*) FROM User;"` |
| T-15m | Build new image | `docker compose build app` |
| T-5m | Deploy | `docker compose up -d --no-deps app` |
| T-0m | Health check | `sleep 35 && docker inspect --format='{{.State.Health.Status}}' <container>` |
| T+1m | HTTP test | `curl -w "%{http_code}" https://domain/` |
| T+5m | Monitor active | Verify cron sending alerts to Slack/Telegram |

---

## Post-Launch Week

### Daily Checks (automation via cron)

- **Disk trending:** Watch for rapid growth. If >80% in 3 days, investigate logs + image sizes.
- **Backup integrity:** Daily restore-test (non-prod volume, discard after).
- **Error rates:** Check app logs for unexpected 500s.

### Quick Rollback

If something breaks immediately post-launch:

```bash
# Stop broken container
docker compose stop app

# Revert to previous image (if you tagged it)
docker tag <previous_image_id> iki-tenun-app:latest

# Restart old version
docker compose up -d --no-deps app
```

---

## References

- See `docker-compose-operations` for entrypoint permission fixes and SQLite readonly debugging
- See `references/launch-verification.md` for the post-deploy live checklist (DNS, TLS, nginx, redirects, canonical metadata)
- See `templates/basic-auth-admin-vhost.conf` for a loopback panel exposed behind HTTP Basic (proxy-injected secret, cert-before-SSL ordering)

---

## Subdomain Routing on Shared Nginx (multi-app VPS)

When several apps share one nginx and a catch-all exists, a new subdomain launch has a specific failure mode.

### Wildcard catch-all hijacks new subdomains → 502

**Symptom:** app answers `HTTP 200` on `127.0.0.1:<app-port>`, but public HTTPS returns 502 and nginx error.log shows `connect() failed ... upstream: http://127.0.0.1:3100/` (the catch-all's port) for the new host.

**Cause:** an existing `server_name *.meowlabs.id` block (e.g. platform-suite → 3100) matches every subdomain. Nginx routes by most-specific `server_name`, so a dedicated block fixes it:

```
/etc/nginx/sites-enabled/<subdomain>   # exact server_name, own cert, own proxy_pass port
```

Create the specific block (or add the exact server_name to the shared file), `nginx -t && systemctl reload nginx`, then re-test. Wildcard remains fallback for other subdomains.

### Exposing a private admin panel behind nginx (password-only)

A small operator panel on `127.0.0.1` that must become reachable at a subdomain, gated by
HTTP Basic alone — no VPN, no identity provider. Starter config: `templates/basic-auth-admin-vhost.conf`.

**Decide the exposure posture in writing before building the proxy.** A panel that holds a
live third-party credential (merchant session token, cloud key) is a different class of
service from a public site. State the tradeoff once — password-only means no lockout, no
per-user revocation, and unlimited brute-force — then build what the operator chose. Do not
re-litigate a decision the operator has already made, and do not silently substitute a
different gate (IP allow-list, mTLS) for the one they asked for.

**Cloudflare Access cannot be created by API.** `POST /accounts/<id>/access/apps` returns
`9999 access.api.error.not_enabled` until an operator clicks *Enable Access* in the
dashboard. Check that before promising Access as the mitigation:

```bash
curl -s -H "Authorization: Bearer $CF_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/apps" | jq -r '.errors[0].message'
```

If Access is unavailable, password-only means fail2ban is **not optional** — it is the
lockout. Enable `nginx-http-auth` on the same vhost and say so explicitly in the handoff
rather than shipping an unlimited-attempt password gate.

**`set $var` in `server{}` is too late for `proxy_set_header`.** `nginx -t` fails with
`unknown "<var>" variable`: `proxy_set_header` is resolved at config parse time, before any
`set` in that server has run, so the variable was never registered. Both directives must
live inside the same `location`:

```nginx
location / {
    include /etc/nginx/<name>.inc;        # contains: set $secret "<value>";
    proxy_set_header x-secret   $secret;
    proxy_set_header x-secret-a $secret;  # repeat per header — no wildcards
}
```

Keep the secret in its own `0600` root-owned include rather than inline, so `grep -r` over
`sites-enabled/` does not leak it. Rebuild it from the app's env on rotation and
`nginx -s reload`.

**Let the proxy inject the credential so the browser never holds one.** When the app
requires a secret header on every API call, terminating auth at nginx and having the proxy
supply that header removes the token from the page entirely — delete it from the frontend's
localStorage/prompt flow rather than leaving both paths. The app-side exemption must be
gated twice: an explicit opt-in flag, **and** a check that the bind address is still
loopback and the peer really is local. A flag alone makes any local process able to drive
the panel the moment the app binds to a public interface.

**Issue the cert before enabling the SSL vhost, in two passes.** Installing the final config
first deadlocks on `cannot load certificate ... BIO_new_file() failed`. Instead: install an
HTTP-only vhost that leaves the ACME path reachable, reload, run certbot, then install the
real file.

```nginx
location ^~ /.well-known/acme-challenge/ { root /var/www/html; allow all; }
location / { return 301 https://$host$request_uri; }
```

`^~` matters — a regex location would otherwise swallow the challenge. Keep that
`location` in the final config too, or `certbot renew` silently fails later.

**`sudo` rewrites `HOME` to `/root`.** Any script that does `os.path.expanduser('~/project/.env')`
fails under `sudo` with a missing-file error that looks like the file was deleted. Read
secrets as the real user and pass them in explicitly (`VAR=... sudo --preserve-env=VAR`), or
`chown` the target first. Same trap for a heredoc-written script that expands `~`.

**Verify every required env var is actually non-empty before writing the config that
consumes it.** A `KEY=` line with nothing after `=` passes "does the key exist" and produces a
zero-length secret that lands in the proxy config as `set $secret ""`. Check the value, not
the key:

```bash
awk -F= '/^KEY=/{print length($2)}' .env      # 0 = empty, not "set"
node -e "require('dotenv').config(); console.log((process.env.KEY||'').length)"
```

**Load env files with a parser, not `source`.** `set -a; . ./.env; set +a` dumps every
secret into the terminal output (and into the transcript) and merges any line that lost
its newline into the next key's value — which, when the swallowed line is a token,
silently renames the app's database file to `panel.db<secret>` and every `-wal`/`-shm`
sidecar with it. SQLite finds sidecars by the main file's name, so the app then reports
`no such table` while the data is intact in a WAL nobody is reading. Parse per line with
`partition('=')`, and find the genuinely open file with
`for f in /proc/$(pgrep -f <app>)/fd/*; do readlink "$f"; done | grep db` before
trusting any configured path.

**Build multi-line config blocks by writing the file, not by `sed` injecting them.** A
`sed 's|^    auth_basic |...\n\n    auth_basic |'` substitution emitted a bare `include `
line and failed with `invalid number of arguments in "include"`. `patch`/whole-file writes
are the right tool; reserve `sed` for single-line in-place edits.

**Push API calls with nested quotes into a script file.** A `bash -c` heredoc containing
both a Python `-c` f-string and a shell `$VAR` dies on quoting before it runs, and the error
points at a syntax error rather than the real cause. `write_file` the `.py`, then run it.

**`nginx -t` warnings from other sites are not yours.** `protocol options redefined for
0.0.0.0:443` comes from pre-existing vhosts; the test still passes. Filter them out or you
will read a clean config as broken.

**`nginx -t` will not tell you the secret is wrong, only undefined.** A bare
`proxy_set_header x-panel-token <value>;` written into the secret's include file
fails with `unknown "panel_token" variable`, because `proxy_set_header` resolves at
parse time and the file was supposed to carry a `set $panel_token "…";` line that
defines it for the `location`. Keep both the `set` and the `proxy_set_header` that
consumes it, and re-derive the include from the app's env on every secret rotation
rather than retyping it — a rotation is exactly when the shape gets mangled.

**Report the unrun steps as unrun.** Config installed, cert issued, `nginx -t` green is not
a live site: the app is not started and the reload has not happened. Say exactly which
command the operator still has to run rather than implying the panel is up.

### Cloudflare DNS via API (before certbot)

Token locations: `~/.hermes/.env` → `CF_API_TOKEN`; `platform-suite/backend/.env` → `CLOUDFLARE_API_TOKEN`.

**Important:** Zone ID must be **full 32-char id** — truncated prefix (e.g. `66c88a0f6`) → API error `"Could not route ... object identifier is invalid"`. Always fetch via `curl -s "https://api.cloudflare.com/client/v4/zones?name=meowlabs.id"` to get the full ID.

```bash
source ~/.hermes/.env
ZONE_ID=$(curl -s "https://api.cloudflare.com/client/v4/zones?name=meowlabs.id" -H "Authorization: Bearer $CF_API_TOKEN" | jq -r '.result[0].id')

curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"type":"A","name":"<sub>.meowlabs.id","content":"<vps-ip>","ttl":3600,"proxied":false}'
```

**Order:** create DNS → verify `nslookup <domain> 8.8.8.8` → `certbot certonly --nginx -d <domain>` → write nginx server block → reload → `curl -I https://<domain>/`. Keep `proxied:false` so Let's Encrypt HTTP-01 and the VPS IP are hit directly.

---

## Pitfalls

- **Healthcheck takes 30s to pass:** Don't curl before start_period expires or you'll see "unhealthy" false positives
- **Disk cleanup frees less than expected:** Check `/var/lib/docker/volumes/` for orphaned volume files
- **Snapshot a WAL database with `VACUUM INTO`, never `cp` and never
  checkpoint-then-`cp`.** In WAL mode recent writes live in the `-wal` sidecar, so
  copying the main file yields a database missing its last few minutes — a backup
  that restores to a stale state, which is worse than having none. `VACUUM INTO
  '<file>'` writes a consistent self-contained snapshot in one statement, sidecars
  included, and refuses to overwrite so a collision errors instead of clobbering.
  Do **not** settle for `PRAGMA wal_checkpoint(TRUNCATE)` before a `cp`: it makes
  the copy correct, and therefore makes a red-to-green injection of `cp`-for-
  `VACUUM INTO` come back **green**, teaching you the test is weak when the real
  defect is untested. Set file modes where snapshots are created, not only where
  they are installed — an app also runs by hand and under a service manager whose
  umask is permissive.
- **Monitor cron sends spam after brief blip:** Script only sends output on error (exit 0 on success = silent), so false positives are rare
- **A monitor that exits non-zero on a disk threshold is WORKING — do not pause it.** A "DISK CRIT" alert is the alarm doing its job; the fix is on the disk, not the monitor. Re-run the script after cleanup and confirm it exits 0. Pausing or editing the monitor because it "failed 3 runs in a row" removes the alarm that caught the problem.
- **A tool's own cache prune can hang while a live service runs through that tool.** `uv cache prune` blocked for minutes because a long-running service had been started with `uv run ...` and held the cache lock. Check for a live process first (`ps aux | grep -E '[u]v |[p]npm'`); if one is running, skip that cache and move to the next candidate — blocking on the lock wastes the session for a small win.
- **Map every running service's `ExecStart` + `WorkingDirectory` before deleting any `node_modules`, `.venv`, or `dist`.** A service can run directly out of a project's `node_modules` (`ExecStart=/usr/bin/node dist/main.js`, `WorkingDirectory=<project>/apps/api`), so a directory that looks like a rebuildable artifact is actually a runtime dependency. `systemctl --user list-units` misses system-scope units — enumerate both (`systemctl list-units --type=service --state=running` + `systemctl cat <unit>` per unit). A bare `node_modules` size scan is not enough.
- **A container built with `COPY --from=build` does NOT need the host's `node_modules`/`.venv`.** Read the Dockerfile: if deps are copied from a build stage inside the image, the host dirs are build-only artifacts and safe to delete even while the container runs. "Container is up" does not imply "host deps are live".
- **A `curl` failure against a service is not proof the service is down — verify the port first.** `docker port <container>` gives the real published port; testing a guessed port returns `000` and reads as an outage that never happened.
- **Nginx wildcard catch-all hijacks new subdomain:** Use `server_name exact.domain` in `/etc/nginx/sites-enabled/exact.domain` (specific before wildcard in load order) to override
- **Cloudflare API rejects zone ID:** Always use full 32-char ID from `zones?name=` query, not truncated prefix
