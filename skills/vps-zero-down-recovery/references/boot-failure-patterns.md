# VPS Boot Failure Patterns & Recovery

## Session Aug 2 2026: Kernel Upgrade + Reboot Cascade

**Timeline:**
- Jul 29 04:40: Kernel 6.8.0-136 installed via unattended-upgrades
- Aug 2 00:08: VPS reboots (either scheduled upgrade-reboot or provider-triggered)
- Aug 2 00:08-00:17: Boot failures cascade
  - swap3.img.swap activation fails (file missing)
  - video-downloader service restart loop (npm deps missing)
  - Hermes gateway starts (has auto-recovery)
  - Docker containers auto-restart via `unless-stopped`

**Root causes:**
1. `/swap3.img` referenced in fstab but file corrupted/deleted during reboot
2. `node_modules` deleted (manual cleanup or mount issue) but systemd doesn't reinstall on start
3. Unattended-upgrades default config doesn't gracefully handle service restart

**Recovery actions:**
1. Remove `/swap3.img` from fstab (keep only `/swap.img` and `/swap2.img`)
2. Mask `swap3.img.swap` systemd unit
3. Restore npm deps: `cd video-downloader && npm install`
4. Restart service: `sudo systemctl restart video-downloader.service`
5. Verify all containers restarted: `docker ps | grep Up`
6. Verify all ports healthy: port sweep 3101, 8890, 8765, 8080, 3301, 20129

**Time to recovery:** ~15 minutes (watchdog detected + alerted at 00:23)

## Pattern: Swap File as Boot Blocker

**Symptom:** `systemd-fstab-generator[XXX]: Failed to activate swap /swap3.img`

**Root cause:** fstab points to `/swap3.img` but file doesn't exist or is corrupted:
- Deleted manually during cleanup
- Lost on corrupted filesystem
- Not recreated after kernel/boot process changes

**Prevention:**
- Keep only 2 swap files in fstab (e.g., `/swap.img` and `/swap2.img`)
- Document swap files in ops notes
- Never reference swap file in fstab unless it's generated/persisted by reliable mechanism
- If adding new swap, verify it exists BEFORE adding to fstab: `ls -lah /swap3.img`

**Quick fix:**
```bash
sudo cp /etc/fstab /etc/fstab.bak
sudo sed -i '/swap3.img/d' /etc/fstab
sudo systemctl mask swap3.img.swap
```

## Pattern: Missing npm Deps on Service Restart

**Symptom:** Service crashes with `ERR_MODULE_NOT_FOUND: express` immediately after boot

**Root cause:**
- `node_modules` deleted (cleanup, mount issue, or accidental `rm -rf`)
- Service starts before npm install completes
- systemd `ExecStart` points to `node server.js` which can't find `express`

**Prevention:**
- Use Docker (deps inside image) for critical services, not host npm
- If host npm, ensure `node_modules` is on reliable persistent storage (not tmpfs)
- Add pre-start hook: `ExecStartPre=/usr/bin/npm install`

**Quick fix:**
```bash
cd /path/to/service
npm install
sudo systemctl restart <service>
```

## Pattern: Unattended-Upgrades Auto-Reboot

**Symptom:** VPS reboots at 02:00 AM without warning, services crash

**Root cause:**
- Ubuntu default: kernel updates trigger automatic reboot
- Services configured with `Restart=always` but recovery time > boot time
- No graceful shutdown window

**Prevention:**
```bash
# Disable auto-reboot
sudo sed -i 's/Unattended-Upgrade::Automatic-Reboot "true"/\/\/Unattended-Upgrade::Automatic-Reboot "false"/' \
  /etc/apt/apt.conf.d/50unattended-upgrades

# Or set specific window + notify
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-WithUsers "false";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
```

## Verified Recovery Checklist

After reboot or service restart:
- [ ] `who -b` shows recent boot time
- [ ] `systemctl --failed --no-pager` is empty (no failed units)
- [ ] `docker ps | wc -l` matches expected container count
- [ ] Port sweep all ports return 200/307/308 (no 000 or 502)
- [ ] Public domains return 200/307/308
- [ ] Watchdog log clean: `grep -c ALERT /tmp/vps-watchdog.log`
- [ ] Swap usage reasonable: `free -h | grep Swap`
- [ ] RAM <90%: `free -h | grep Mem`
- [ ] Disk >10GB free: `df -h /`
