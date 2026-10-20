# VPS Stability Hardening

Multi-service VPS (2 CPU / 3.6GB RAM) running Hermes, Postgres ×2, Next.js, WhatsApp API, security-gateway services, the gateway, MariaDB — practical steps to prevent OOM, disk-full crashes, and service downtime.

## Swap & Memory Tuning

### Add swap (Docker nsenter — no sudo needed)
```bash
# Create 2GB swap file
docker run --rm --pid=host --privileged alpine sh -c '
nsenter -t 1 -m -u -i -n -p -- sh -c "
  fallocate -l 2G /swap2.img
  chmod 600 /swap2.img
  mkswap /swap2.img
  swapon /swap2.img
  grep -q /swap2.img /etc/fstab || echo \"/swap2.img none swap sw 0 0\" >> /etc/fstab
"'
```

### Set swappiness (disk-writes avoidance)
Default `vm.swappiness=60` starts swapping at moderate RAM pressure. On VPS with SSD, lower to 10:
```bash
# Same nsenter pattern
sysctl vm.swappiness=10
echo "vm.swappiness=10" > /etc/sysctl.d/99-swap.conf
```

### Target
- Total swap ≥ RAM total (e.g., 4GB for 3.6GB RAM)
- Swappiness 10 so swap only kicks in when RAM is genuinely full (>90%)

## Docker Container Memory Limits

Apply to running containers without restart:
```bash
docker update --memory 256m --memory-swap 512m security-gateway-web
docker update --memory 1g --memory-swap 2g security-gateway-ml-service
docker update --memory 512m --memory-swap 1g platform-suite-postgres
docker update --memory 256m --memory-swap 512m meowattend_pg
```

On fresh `docker run`, add `-m 256m --memory-swap 512m` for the same effect.

**Critical: `--memory-swap` pairing pitfall** — `docker update --memory 256m <container>` (without `--memory-swap`) fails with:
`"Memory limit should be smaller than already set memoryswap limit, update the memoryswap at the same time"`
Because Docker default swap = 2× memory, and when the current container has a non-standard swap value, a single-arg update can't resolve. **Always pass both `--memory X --memory-swap Y` together** where Y > X.

Recommended limits per service type (for 3.6G RAM host):

| Service type | RAM limit | Swap limit | Example containers |
|---|---|---|---|
| ML inference | 384M | 768M | security-gateway-ml-service |
| Postgres | 128-256M | 256-512M | any pg container |
| Node gateway | 128M | 256M | security-gateway-gateway, auth-service-core |
| Static frontend | 128M | 256M | platform-suite-frontend |
| API backend | 256M | 512M | platform-suite-backend, auth-service-worker |
| Demo/light | 128M | 256M | auth-service-demo |

Apply with `docker update --memory <X> --memory-swap <Y> <name>`.

## nginx hardening

See `references/vps-nginx-hardening.md` for hardened `nginx.conf` template with rate limits, security headers, gzip, client limits, and modern SSL.

## fail2ban jails

Apply via `/etc/fail2ban/jail.local`:
- `sshd` — maxretry 5, bantime 1h
- `nginx-http-auth` — auth failure protection
- `nginx-botsearch` — aggressive (maxretry 2, bantime 24h)

## Weekly auto-prune (disk)

```bash
# sudo crontab -e
0 3 * * 1 docker system prune -af --filter 'until=24h' >/dev/null 2>&1
```

## Old kernel cleanup

`apt autoremove --purge` skips kernel images (marked manual). Explicit purge:
```bash
dpkg -l | grep -E 'linux-(image|modules)-[0-9]+' | grep -v $(uname -r | sed 's/-generic//')
# For each:
sudo dpkg --purge linux-image-6.8.0-XXX-generic linux-modules-6.8.0-XXX-generic linux-modules-extra-6.8.0-XXX-generic
```

## Watchdog (auto-restart + alert)

### Script pattern (`~/.hermes/scripts/vps-watchdog.sh`)
A bash script run via Hermes cron (`no_agent=true`) that:
1. Checks critical ports/processes: `ss -tlnp` or `pgrep -f`
2. Auto-restarts dead services (Docker `start`, PM2 `restart`, systemd `restart`)
3. Alerts if any restart fails
4. Checks memory (>90%), swap (>85%), disk (>85%) and alerts

Only outputs text when something is wrong — silent when healthy (`no_agent=true` delivers stdout only).

### Hermes cron setup
```bash
# Create: runs every 5 minutes
hermes cron create \
  --name vps-watchdog \
  --no-agent \
  --every 5m \
  --script vps-watchdog.sh

# Must have repeat=forever (default for --every is once; adjust with cronjob action=update)
```

### Services to monitor
- **the security gateway gateway**: systemd (`security-gateway.service`) — check port 8080
- **the security gateway web**: Docker (`security-gateway-web`) — check port 3003
- **the security gateway ML**: Docker (`security-gateway-ml-service`) — check process
- **the gateway**: user process — check port 20129
- **WhatsApp API**: PM2 — `pm2 start whatsapp-api`
- **the platform suite Postgres**: Docker (`platform-suite-postgres`) — check port 5432

## Weekly Auto-Cleanup

Script (`~/.hermes/scripts/vps-cleanup.sh`):
```bash
#!/bin/bash
docker system prune -af
docker builder prune -af
journalctl --vacuum-size=200M    # via nsenter for root
```

Hermes cron (Sunday 3 AM):
```bash
hermes cron create \
  --name vps-cleanup \
  --no-agent \
  --schedule "0 3 * * 0" \
  --script vps-cleanup.sh
```

## Pitfalls

- **Swap file via `dd` is slow on low-end VPS**: use `fallocate -l 2G` instead of `dd if=/dev/zero` — instant allocation.
- **Docker nsenter for journalctl**: `journalctl` requires root. Run inside `nsenter -t 1 -m -u -i -n -p` from a privileged Docker container. The Alpine image is ~4MB and gets pulled fresh each time.
- **Watchdog runs as `meowlabs` user**: can manage Docker and PM2, but not systemd (use nsenter-only operations for root-level commands).
- **Cron job silent output**: With `no_agent=true`, only non-empty stdout is delivered. If the watchdog detects nothing wrong, the job produces nothing and no message is sent — this is the desired pattern.
- **Repeat is "once" by default**: When creating a recurring watchdog/cleanup job, always check `repeat` is "forever" after create, and update it if needed with `cronjob action=update`.
