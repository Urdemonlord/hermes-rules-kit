---
title: VPS Zero-Down Recovery & Auto-Restart Architecture
name: vps-zero-down-recovery
description: Boot-time failure diagnosis and recovery. Auto-restart chains using Docker restart policies, systemd services, and watchdog monitoring. Zero-downtime target — get every service back online within boot cycle or watchdog interval.
triggers:
  - User says 'zero down', 'biar ga down', 'kalau bisa zero down', 'prevent downtime'
  - VPS rebooted and services didn't come back
  - Kernel upgrade + reboot → services missing or stuck in restart loop
  - User asks 'ngapa service down', 'cek yg udah ada'
  - User asks to sweep for crash-loops, zombies, or duplicate/fighting services
    ('ada lagi ga program yg crashloop atau zombies dll') — a looping service is invisible to
    `systemctl --failed`; audit restart counters and PM2 instead
  - User wants '0 downtime' / 'otomatis reboot sendiri' after an OOM freeze — explain that
    auto-reboot cannot work without a hardware watchdog and implement memory limits instead (Layer 4)
  - Boot-blocking: fstab errors, missing swap files, corrupted service files
---

# VPS Zero-Down Recovery & Auto-Restart Architecture

Goal: Services auto-recover on boot, reboot, or crash without manual intervention. If anything dies, watchdog detects + restarts within 15 minutes.

## 1. Boot-Time Failure Diagnosis

When VPS reboots and services don't come back:

### Step 1a: Check what failed during boot

```bash
# Last reboot time
who -b

# Recent systemd failures
systemctl --failed --no-pager
systemctl list-units --failed --no-pager

# Swap activation failures (common after fstab drift)
systemctl status swap*.swap --no-pager

# Docker daemon up?
systemctl is-active docker

# User service failures (Hermes, PM2, custom)
systemctl --user --failed --no-pager

# Duplicate unit names across scopes (same name at system AND user level → port
# fight, one side restart-loops forever with EADDRINUSE while the other works)
ls /etc/systemd/system/*.service ~/.config/systemd/user/*.service 2>/dev/null \
  | xargs -n1 basename | sort | uniq -d
```

**Common culprits (priority order):**
1. **Swap file missing or corrupted** → fstab points to `/swap3.img` but file doesn't exist or is corrupted
2. **Missing npm/Python deps** → service restart loop on startup (e.g., `ERR_MODULE_NOT_FOUND: express`)
3. **Unattended-upgrades auto-reboot** → kernel upgrade + auto-reboot at 02:00 AM but services weren't configured to persist
4. **Docker daemon not up** → container restart policy means nothing if daemon is down
5. **Systemd service order** → A depends on B but B hasn't started yet

### Step 1d: Audit for crash-loops a `--failed` check will NOT show

`systemctl --failed` only lists units that gave up. A service with `Restart=always` that dies every
few seconds sits in `activating (auto-restart)` and is **invisible** there, while burning CPU and
filling the journal. Sweep restart counters instead — both scopes:

```bash
for u in $(systemctl list-units --type=service --all --no-legend --plain | awk '{print $1}'); do
  n=$(systemctl show "$u" -p NRestarts --value)
  [ -n "$n" ] && [ "$n" -gt 3 ] 2>/dev/null && echo "SYSTEM $u restarts=$n"
done
# repeat the same loop with `systemctl --user list-units` and `systemctl --user show`
```

**PM2 is a second, separate supervisor — a systemd-only sweep misses everything it runs.**

```bash
pm2 jlist | python3 -c "import json,sys
for a in json.load(sys.stdin): print(a['name'], a['pm2_env']['status'], a['pm2_env']['restart_time'])"
```

Status `launching` / `waiting restart` with a restart count in the hundreds is a live crash-loop.
Read the real error from the app's own log (`pm2 describe <name>` prints the log paths; they are often
`/var/log/<app>/*.log`, not the PM2 default dir).

**Prove a loop is running, and prove it stopped, by measuring the log — not by reading status.**

```bash
sudo stat -c%s /var/log/<app>/error.log    # sample
sleep 30
sudo stat -c%s /var/log/<app>/error.log    # same byte count = loop stopped
```

A frozen byte count over a window longer than the old `RestartSec` is evidence; "I disabled it" is a
claim.

### Step 1e: `pm2 delete` is not enough — the boot-time dump resurrects it

`pm2-meowlabs.service` runs `pm2 resurrect` at boot from `~/.pm2/dump.pm2`. Deleting a process leaves
the dump untouched, so the crash-loop **comes back on the next reboot**. After `pm2 stop` +
`pm2 delete`, clear the dump:

```bash
pm2 save --force        # plain `pm2 save` warns 'not managing any process, skipping save'
python3 -c "import json; print(json.load(open('$HOME/.pm2/dump.pm2')))"   # expect []
```

Read the dump BEFORE overwriting it — it lists what will be resurrected, which is how you notice a
second app you did not intend to drop. Confirm each of those is genuinely dead (its script path no
longer exists) before saving an empty list, and tell the user which names left the boot set.

### Step 1g: A killed supervisor comes back if something else POLLS it

Stopping a daemon is not the same as removing it. If any monitoring/observability process polls the
supervisor on an interval, **the poll command itself starts the daemon again** — you will see it
reappear with a new PID seconds later and misread it as "something is respawning it."

On this host: `runtimed` (a runtime-orchestration collector) has a `pm2` collector enabled with a
2-second interval. `pm2 jlist` starts the PM2 God Daemon when none is running, so `pm2 kill` freed
63 MB for ~2 seconds and then the daemon was back.

**Your own diagnostic command is the most common false culprit.** Running `pm2 list` / `pm2 jlist`
yourself starts the daemon. Kill it, then immediately run `pm2 list` to "check", and you have created
the resurrection you are now investigating.

Rules:
- Name the cgroup before guessing. `cat /proc/<pid>/cgroup` — a daemon appearing under
  `/system.slice/<other-service>.service` names the real owner; `ppid=1` alone looks like "nothing owns it."
- Find every poller before declaring the supervisor stopped:
  ```bash
  grep -rl '<supervisor-name>' /etc/systemd/system ~/.config/systemd/user /etc/cron* 2>/dev/null
  # and read the config of any running collector daemon for a poll interval
  ```
- Prove a stop with a wait **longer than the poll interval**, and with **no** supervisor command of
  your own in that window:
  ```bash
  pkill -f '<supervisor-daemon-pattern>'
  sleep 20                                   # > poll interval
  ps aux | grep '[<p]attern' | grep -c '<daemon>'   # 0 = actually stopped
  ```
- The durable fix is to disable the **poller** (e.g. turn the collector off in its own config), not
  to keep killing the daemon. But a collector owned by another project is out of scope — the
  isolation rule forbids editing another project's service/config. Report it and ask first.

### Step 1f: Distinguish a zombie from a dead service

```bash
ps aux | awk '$8 ~ /Z/ {print}'        # state Z = defunct
```

Then resolve its parent and its cgroup before acting:

```bash
ps -o pid,ppid,cmd -p <zombie-pid>
cat /proc/<zombie-pid>/cgroup           # docker-<id>.scope = inside a container
```

A zombie whose parent is container PID 1 (a `node build`, an entrypoint) **belongs to that container
and is harmless** — it consumes no CPU or memory, the container itself is usually healthy, and it
disappears when the container restarts. Do not "clean" it, and do not report it as a fault. Only a
zombie on the HOST with a parent that has itself died is a real leak.

**Related to the crash-loop above: a service can be healthy while its duplicate is looping.** A high
`NRestarts` on a unit whose port is served and whose site answers 200 means the duplicate is the
problem, not the service (see Pitfall 8).

### Step 2: Check recent logs for the boot cycle

```bash
# Kernel messages (OOM, panic, I/O errors)
journalctl -b 0 -p err --no-pager | head -100

# Service crash patterns (look for "Restart=")
journalctl -b 0 --no-pager | grep -iE 'failed|error|killed|exit' | tail -50

# Specific service (e.g., video-downloader)
journalctl -u video-downloader.service --no-pager | tail -100
```

### Step 1c: Port health check

Services may be running but ports not listening (e.g., npm deps missing):

```bash
# All critical ports at once
for port in 3101 8890 8765 8080 3301 20129; do
  status=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:$port/ 2>/dev/null || echo "000")
  echo "Port $port → HTTP $status"
done

# Compare against known mapping
# 3101 = platform-suite-frontend, 8890 = video-downloader, 8765 = clipper
# 8080 = security-gateway-gateway, 3301 = iki-tenun, 20129 = the gateway
```

---

## 2. Recovery Priority Stack

Fix in this order to minimize recovery time:

### Level 1: Boot-blocking (fix first)

**Corrupted/missing swap file in fstab**

Symptom: `Failed to activate swap /swap3.img`

```bash
# Check fstab
cat /etc/fstab

# If /swap3.img entry exists but file is gone:
sudo cp /etc/fstab /etc/fstab.bak
sudo sed -i '/swap3\.img/d' /etc/fstab

# Mask the systemd unit so it doesn't retry
sudo systemctl mask swap3.img.swap
```

**Unattended-upgrades auto-reboot**

Symptom: Reboot happened at 02:00 AM and caught services off-guard

```bash
# Check if auto-reboot is enabled
grep -n 'Automatic-Reboot' /etc/apt/apt.conf.d/50unattended-upgrades | head -5

# Should be commented out or "false"
# If "true", comment it:
sudo sed -i 's/Unattended-Upgrade::Automatic-Reboot "true"/\/\/Unattended-Upgrade::Automatic-Reboot "false"/' /etc/apt/apt.conf.d/50unattended-upgrades
```

### Level 2: Service deps (fix second)

**Missing node_modules or Python venv**

Symptom: Service crashes with `ERR_MODULE_NOT_FOUND` or `ModuleNotFoundError`

```bash
cd /home/user/video-downloader
npm install  # or: pip install -r requirements.txt

# Restart service
sudo systemctl restart video-downloader.service
```

### Level 3: Restart policies (fix third)

All long-lived services need explicit restart policy:

```bash
# Docker containers
docker ps -a --format '{{.Names}} {{.HostConfig.RestartPolicy.Name}}'

# Should all be: unless-stopped
# If not:
docker update --restart unless-stopped <container>

# Systemd services
systemctl list-unit-files --type=service | grep -E 'hermes|the gateway|agentwa|video'

# Should be: enabled + Restart=always in the .service file
```

---

## 3. Zero-Down Architecture

Layer three types of restart triggers:

### Layer 1: Docker (immediate)

```bash
# Every container must have restart policy
for c in $(docker ps -a --format '{{.Names}}'); do
  docker update --restart unless-stopped "$c"
done

# Verify
docker ps -a --format '{{.Names}}\t{{.HostConfig.RestartPolicy.Name}}'
```

**Why:** Docker daemon is always running. Containers die → restarted in <5 seconds.

### Layer 2: Systemd services (boot persistence)

```bash
# For user services (Hermes, the gateway, custom apps)
# Create ~/.config/systemd/user/<name>.service:

[Unit]
Description=My Service
After=network.target

[Service]
Type=simple
User=meowlabs
WorkingDirectory=/path/to/service
ExecStart=/path/to/binary
Restart=always
RestartSec=10
StartLimitInterval=60s
StartLimitBurst=5

[Install]
WantedBy=default.target
```

**Key directives:**
- `Restart=always` — restart on any exit (even 0)
- `RestartSec=10` — wait 10s between restarts (avoid restart storms)
- `StartLimitInterval=60s` `StartLimitBurst=5` — fail if crashes >5 times in 60s (circuit breaker)
- `WantedBy=default.target` — start on boot when user logs in

**Enable:**
```bash
systemctl --user daemon-reload
systemctl --user enable <name>.service
systemctl --user start <name>.service
```

**Verify user services persist after logout:**
```bash
loginctl show-user meowlabs --property=Linger
# Should be: Linger=yes
# If not: sudo loginctl enable-linger meowlabs
```

### Layer 3: Watchdog (safety net)

Run `vps-watchdog.sh` every 15 minutes to detect + restart stale services:

```bash
# Cron job
every 15m | script: vps-watchdog.sh

# Script checks:
# - systemd services (only ones that still exist)
# - Docker containers (discovered automatically, see below)
# - HTTP endpoints for app-level crashes
# - Resource thresholds (RAM >92%, Swap >90%, Disk >88%)
```

**Watchdog should:**
1. Check service status
2. Attempt restart if down
3. Report to Telegram if still down after retry
4. Log all events to a PERSISTENT path — `~/.hermes/logs/vps-watchdog.log`, never `/tmp` (wiped on reboot, so you lose the evidence exactly when you need it)

**The watchdog's own target list is its #1 failure mode.** A watchdog whose targets no longer
exist emits a false alert every interval; the user learns to ignore it; it is then effectively
dead while still reporting "active". On this host it sat disabled for 7 weeks because 6 of 9
targets (`agentwa-web`, `security-gateway-*`, `platform-suite-postgres`) had been retired. Rules:

- **Prefer auto-discovery over a hardcoded list for containers.** Keep a baseline file
  (e.g. `~/.hermes/state/watchdog-containers.txt`); register new containers automatically, try
  `docker start` on ones that vanished, and drop ones that no longer exist (`RETIRED`, logged
  without an alert). To deliberately stop monitoring a container, add it to an `*.ignore` file —
  do NOT delete it from the baseline or it is re-added.
- **Guard against docker being unresponsive.** If `docker ps -a` returns empty while a baseline
exists, ALERT and leave the baseline untouched — otherwise one docker hiccup erases every target
  and silently blinds the watchdog (the same bug, reintroduced).
- **Verify the ALERT path, not just the quiet path.** A script that prints nothing when healthy
  looks identical to a broken one. Test by injecting a bogus target into a COPY and confirming it
  shouts:
  ```bash
  cp ~/.hermes/scripts/vps-watchdog.sh /tmp/wd.sh
  sed -i 's|^check_thresholds$|check_docker_container "FAKE" "container-xyz"\ncheck_thresholds|' /tmp/wd.sh
  bash /tmp/wd.sh   # must print ALERT
  ```
- **The watchdog cannot report its own supervisor's death.** If the watchdog runs as a Hermes cron
  job, Hermes dying means no watchdog either. Only `Restart=always` + `StartLimitIntervalSec=0`
  (systemd, outside the agent) covers that; a true external check needs a systemd timer or remote
  monitoring. State this limitation instead of implying full coverage.

---

### Layer 4: Memory limits — the only real defence against a freeze

Restart policies do NOT save you from memory exhaustion. When the kernel thrashes, the machine is
frozen but not panicked: processes cannot run, so nothing restarts anything. Prevention is the only
fix, and it is what actually delivers zero downtime.

**Why reboot-on-freeze is not a plan.** Confirm the host's capabilities before promising it:

```bash
ls /dev/watchdog*                     # absent on almost every VPS/VM — no hardware watchdog
cat /proc/sys/kernel/panic            # >0 reboots after a PANIC, not after thrashing
cat /proc/sys/vm/panic_on_oom
systemctl is-active systemd-oomd
```

Without `/dev/watchdog` nothing inside a frozen machine can reboot it. Compare the freeze duration
against boot time: an 84-minute freeze versus a 32-second boot (`systemd-analyze`) proves the box was
frozen, not rebooting. Even a working auto-reboot only converts this into repeated 30-second
outages — the cause is still there.

**Layer 4a — fix the root cause.** Gradle is a common culprit on build hosts: the default daemon
`idleTimeout` is 3 hours, so a finished build leaves ~1.6 GB resident. Cap it globally in
`~/.gradle/gradle.properties`:

```properties
org.gradle.daemon.idletimeout=60000        # 3h -> 60s
org.gradle.jvmargs=-Xmx768m -XX:MaxMetaspaceSize=384m
kotlin.daemon.jvmargs=-Xmx512m
org.gradle.workers.max=2
```

Better still: **do not build on a production VPS** — use CI or a local machine.

**Layer 4b — bound each service so one process cannot take the box.** A systemd drop-in
(`~/.config/systemd/user/<svc>.service.d/memory-limit.conf`):

```ini
[Service]
MemoryHigh=1700M      # start reclaiming here; set ABOVE normal usage or you throttle day-to-day work
MemoryMax=2G          # hard cap -> OOM-kill only this cgroup
MemorySwapMax=512M    # the swap thrash is what freezes the box — cap it
OOMScoreAdjust=200    # prefer killing this over others
```

**Measure before choosing the numbers.** `systemctl --user show <svc> -p MemoryCurrent` next to the
configured `MemoryHigh`; a cap below steady-state usage silently strangles the service. The cgroup
covers everything the unit spawns, including builds it launches.

Apply without restarting the service you are standing on:
`systemctl --user daemon-reload && systemctl --user set-property <svc> MemoryHigh=1700M`.

For containers, `docker update --memory ... --memory-swap ...` takes effect live, but **is lost when
the container is recreated** — also write `mem_limit` / `memswap_limit` into the compose file.

**Layer 4c — systemd-oomd kills the offender before the freeze.** Requires PSI
(`ls /proc/pressure/`). Install `systemd-oomd`, then **restart it** (see pitfalls).

```bash
sudo oomctl | sed -n '/Memory Pressure Monitored/,$p'   # what it will actually kill
```

**Pitfall — oomd's default scope is far too broad.** Ubuntu ships
`/usr/lib/systemd/system/user@.service.d/10-oomd-user-service-defaults.conf` with
`ManagedOOMMemoryPressure=kill` on `user@.service`, so a trigger kills **every** user service at
once. On this host that was Hermes **and** `the gateway` — and the gateway was Hermes's own LLM provider, so
killing them together left Hermes with no model. Override the broad scope and target the leaf:

```ini
# /etc/systemd/system/user@<UID>.service.d/oom-scope.conf
[Service]
ManagedOOMMemoryPressure=auto
```

…plus `ManagedOOMMemoryPressure=kill` + `ManagedOOMMemoryPressureLimit=60%` on the specific leaf
unit you are willing to sacrifice. Check the blast radius before trusting the default: list what
lives in the slice (`systemctl --user list-units --type=service --state=running`) and ask what
breaks if all of it dies at once.

**Prove the kernel actually enforces the cap** (isolated cgroup, does not touch the live service):

```bash
sudo bash -c 'CG=/sys/fs/cgroup/t-$$; mkdir -p $CG; echo 100M > $CG/memory.max; echo 0 > $CG/memory.swap.max
  ( echo $BASHPID > $CG/cgroup.procs; exec python3 -c "
b=bytearray()
for i in range(300): b.extend(bytearray(1024*1024))" ) 2>&1 | tail -1
  cat $CG/memory.events; rmdir $CG'
# expect: Killed (exit 137) and oom_kill 1
```

**Pitfalls found while installing oomd:**
- `oomctl` times out right after install (`Failed to activate service 'org.freedesktop.oom1'`) even
  though the unit says `active` — socket-activation race. `sudo systemctl restart systemd-oomd`.
- `apt install systemd-oomd` pulls a **systemd upgrade** as a dependency. Verify with
  `systemctl is-system-running`, `systemctl --failed`, and a live-site check afterwards. The user
  manager keeps running the old binary until `daemon-reexec` — which risks killing an agent session
  running inside it, so treat it as cosmetic and do not do it casually.
- The directive is **`OOMPolicy=`**, not `MemoryOOMGroup=` (the latter does not exist;
  `set-property` rejects it). `OOMPolicy=stop` is already the default for services and gives the
  behaviour you want: if any process in the cgroup is OOM-killed, systemd stops the whole unit and
  `Restart=always` brings it back clean — no half-dead service.

**Layer 4d — attribute RAM usage and name the OOM victim before blaming an app.**

When the box froze, is sluggish, or the user asks "siapa yang paling makan RAM", attribute memory
top-down. Do NOT name the app the user complained about until a cgroup confirms it — on a ≤4 GB VPS
the freeze is usually the **sum** of many services (JVM/Gradle daemon, gateway, node, dockerd,
mariadbd), not one runaway.

```bash
free -h; swapon --show
cat /proc/pressure/memory           # PSI: sustained some/full avg > 0 = real memory pressure
ps -eo pid,ppid,user,rss,pmem,etime,comm --sort=-rss | head -15
systemd-cgtop -m -n 1 | head -15    # per slice/cgroup: system.slice vs user.slice vs each docker scope
# Who the kernel actually killed, across reboots:
sudo journalctl -k --since '7 days ago' | grep -iE 'Killed process|Memory cgroup out of memory'
```

Per-container headroom — flag any container near its own limit, not just the largest, and check
whether it was already OOM-killed once:

```bash
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}'
for c in $(docker ps --format '{{.Names}}'); do
  lim=$(docker inspect "$c" --format '{{.HostConfig.Memory}}')
  [ "$lim" = 0 ] && echo "$c: NO LIMIT" || echo "$c: $((lim/1024/1024)) MB"
done
docker inspect <container> --format 'OOMKilled={{.State.OOMKilled}} RestartCount={{.RestartCount}}'
```

**Trace an anonymous process to its owner** — a bare `node build` / `python3` in `ps` tells you
nothing:

```bash
sudo readlink /proc/<pid>/cwd /proc/<pid>/exe   # working dir + real binary
cat /proc/<pid>/cgroup                           # docker-<id>.scope or a systemd unit name
ps -o pid,ppid,args -p <pid>                     # then identify the parent
```

The OOM victim is frequently **not** the app the user reported (a JVM or gateway is killed while the
web app merely times out). Read which process died before assigning blame, and pair this with the
proxy-log 499/504 check in `sveltekit-runtime-patterns` →
.

**Pitfall 9: Two schedulers doing the same job — check before you "fix" anything**
- The same task is often already handled by a *different* scheduler you have not looked at yet:
  user `crontab`, root `crontab`, a Hermes cron job, a systemd timer, or a Docker healthcheck.
  On this host the same the client site backup ran at 03:00 from both a user crontab AND a Hermes cron
  job, and `docker system prune` ran from both a root crontab and a Hermes job.
- **The trap:** one copy fails silently, you "repair" it, and now two copies run — double load,
  interleaved retention windows where each script's cleanup deletes the other's output.
- **Before repairing any scheduled task, enumerate every scheduler first:**
  ```bash
  crontab -l; sudo crontab -l
  ls /etc/cron.d/ /etc/cron.*/ 2>/dev/null
  systemctl list-timers --all --no-pager
  # plus the agent's own cron store (e.g. ~/.hermes/cron/jobs.json)
  ```
- When two exist, **merge rather than pick**: keep the more robust implementation but run it under
  the scheduler you can actually monitor (e.g. keep the checkpoint+integrity-check backup logic, but
  run it as a monitored cron job), then remove the other entry. Back both crontabs up first.
- Corollary — **a missing output is not proof of a bug.** Before concluding a job is broken,
  check whether a *different* scheduler produced the artefact. An absent file at 03:00 may just mean
  the machine was still booting then (`journalctl --list-boots`), not that the job is faulty.
- Mark the superseded script obsolete in its header so the next person does not "fix" it back.

---

## 4. Verification Checklist

After recovery or setup changes:

### Boot persistence
```bash
# All Docker containers should auto-start
docker inspect <container> --format '{{.HostConfig.RestartPolicy.Name}}'
# → unless-stopped

# All systemd services should auto-start
systemctl list-unit-files | grep enabled
# → hermes-gateway, the gateway, agentwa-web, video-downloader all enabled

# User linger enabled
loginctl show-user meowlabs --property=Linger
# → Linger=yes
```

### Port health
```bash
for port in 3101 8890 8765 8080 3301 20129; do
  curl -sS -o /dev/null -w ":%{http_code}\n" --max-time 3 http://127.0.0.1:$port/ || echo ":000"
done
# All should be 200, 307, or 308 (redirects OK)
```

### Public endpoints
```bash
for domain in security-gateway.meowlabs.id client-site.id deploy.meowlabs.id; do
  curl -sS -o /dev/null -w "$domain:%{http_code}\n" --max-time 5 https://$domain/
done
# All should be 200, 307, or 308
```

### Resource state
```bash
# Watchdog should report clean
tail -20 /tmp/vps-watchdog.log | grep -iE 'alert|failed|error' || echo "✓ Clean"

# RAM + Swap reasonable
free -h | grep -E 'Mem|Swap'

# Disk free >10GB
df -h / | tail -1
```

---

## 5. Pitfalls & Common Mistakes

**Pitfall 1: Swap file referenced in fstab but file is missing**
- Kernel upgrade or disk cleanup can delete `/swap3.img`
- systemd boot hangs waiting for swap activation
- **Fix:** Remove from fstab, mask systemd unit
- **Prevent:** Use fallocate-based swap files with version guards, or keep only 2 swap files

**Pitfall 2: npm deps deleted but systemd service left running**
- Common after `rm -rf node_modules` in a live service dir
- Service restart loop: `ERR_MODULE_NOT_FOUND`
- **Fix:** `npm install` before systemctl restart
- **Prevent:** Use Docker (deps inside image) or separate app dir from static mounts

**Pitfall 3: Docker daemon restarts → all containers restart**
- If Docker daemon crashes or gets restarted, it kills all running containers
- Containers have `unless-stopped` so they auto-restart after daemon comes back
- BUT there's a window (5-30s) when services are unreachable
- **Mitigation:** Watchdog should detect this and alert; nginx should return graceful error page instead of 502

**Pitfall 4: Systemd service timeout too short**
- If `TimeoutStartSec=10` but app takes 15s to boot, systemd kills it
- Service goes into restart loop
- **Fix:** Set `TimeoutStartSec=60` or higher for slow apps

**Pitfall 5: User services don't start on boot if user never logged in**
- `WantedBy=default.target` only works if user session is active
- **Fix:** `sudo loginctl enable-linger meowlabs` so user session persists even with no login

**Pitfall 6: Unattended-upgrades reboots at 02:00 AM without warning**
- Default Ubuntu behavior: kernel updates auto-reboot
- Services crash if they were counting on staying up
- **Fix:** Disable auto-reboot or set it to a maintenance window when all services are expected to restart

**Pitfall 8: The SAME unit name defined at BOTH system and user level — one holds the port, the other restarts forever**
- A service migrated between systemd scopes (or duplicated during setup) leaves two unit files with the same name: `/etc/systemd/system/<name>.service` and `~/.config/systemd/user/<name>.service`. Both run the same `ExecStart`, so both want the same port.
- Symptom: a service reports `Restart=always` and a huge restart counter (`systemctl show <name> -p NRestarts` → hundreds/thousands) with `Error: listen EADDRINUSE: address already in use 127.0.0.1:<port>` in its journal, while the port IS listening and the app works fine.
- **The trap: the service looks broken but the user-facing function is healthy.** Whichever scope started first holds the port; the other dies on bind and systemd respawns it every `RestartSec`, burning CPU and flooding the journal (thousands of lines). Do not "fix" the working process — find the duplicate.
- Diagnose: list both scopes and intersect the names.
  ```bash
  systemctl --user list-units --type=service --no-pager
  systemctl list-units --type=service --no-pager
  ls /etc/systemd/system/*.service ~/.config/systemd/user/*.service | xargs -n1 basename | sort | uniq -d
  ```
  Then confirm which side owns the port: `ss -tlnp | grep <port>` gives the PID, and `ps -o ppid= -p <pid>` names the parent — `systemd --user` (PID of `/usr/lib/systemd/systemd --user`) means the user unit won, `1` means the system unit did.
- Fix the DUPLICATE only, never the healthy one. If the user unit works: `sudo systemctl disable --now <name>.service`. This touches only the system cgroup (`/system.slice/`), leaving the healthy process in `/user.slice/` untouched — **zero downtime**. Verify after: `ss -tlnp | grep <port>`, `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:<port>/`, and re-read `NRestarts` after waiting longer than one restart interval to prove the loop stopped.
- If the service is behind nginx (`grep -rn '<port>' /etc/nginx/`), check which sites depend on it BEFORE touching anything — those sites must still answer 200 afterwards.
- **Pitfall 10: `active` + `enabled` + a daily "No packages found" log is not proof the patcher works**
- A security auto-updater can be running on schedule, exit successfully, and install nothing —
  because its allowed-origins list only names the base pocket (`noble`), which holds no upgradable
  packages, while every real update lives in `-security` / `-updates`.
- Seen with 126 security updates pending (openssh, systemd, nginx, libc6) on a host that reported
  healthy. Confirm scope, not status: `apt-config dump | grep -i Allowed-Origins` must list
  `-security`; `unattended-upgrade --dry-run --debug` must print `Checking:` per package.
- Worse, if `dpkg -S` says the config file is *not* a conffile, upgrading the patcher package will
  never repair it — the misconfiguration is permanent until edited by hand. Check that before
  promising that `apt upgrade` fixes it.
- Cross-reference the disk/security audit in `vps-hardening-optimization` section 8b for the full
  procedure and the `/boot` + reboot caveats.

**Pitfall 7: Watchdog sends alerts but doesn't fix**
- Alert fatigue if watchdog keeps complaining instead of auto-recovering
- **Fix:** Watchdog should attempt restart FIRST, then alert only if retry fails

---

## 6. Real-World Example: Post-Kernel-Upgrade Recovery

**Scenario:** Kernel 6.8.0-136 installed Jul 29, VPS reboots Aug 2, services down

**Recovery steps:**

```bash
# 1. Check what failed
who -b                          # Aug 2 00:08
systemctl --failed              # swap3.img.swap FAILED
systemctl --user --failed       # (none, but check PM2)

# 2. Fix swap
cat /etc/fstab | grep swap3
# /swap3.img none swap sw 0 0  ← file doesn't exist
sudo sed -i '/swap3.img/d' /etc/fstab
sudo systemctl mask swap3.img.swap

# 3. Check services
docker ps                       # containers UP
systemctl --user list-units | grep hermes-gateway  # UP
pm2 list                        # whatsapp-api UP

# 4. Check ports
for port in 3101 8890 8765; do curl -I http://127.0.0.1:$port/; done
# 8890: HTTP 200 ✓
# 3101: HTTP 307 ✓ (redirect)
# 8765: HTTP 200 ✓

# 5. Public check
curl -I https://security-gateway.meowlabs.id  # 200 ✓
curl -I https://client-site.id          # 200 ✓

# Result: Zero-down, all systems recovered on boot
```

---

## 7. Script: Quick Recovery Validation

See `scripts/zero-down-validate.sh` for automated port + service health check.

---

## 8. Related Skills

- `vps-hardening-optimization` — cleanup, resource management, firewall
- `vps-node-cleanup-recovery` — safe node_modules deletion
- `devops/docker-compose-operations` — multi-container orchestration
