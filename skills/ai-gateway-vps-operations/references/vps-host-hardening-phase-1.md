# VPS Host Hardening Phase 1 — Full Session Recipe

Executed 2026-06-28 on Ubuntu 24.04 LTS VPS.
All steps verifiable, reversible, no project-code changes.

## Preflight
```bash
TS=$(date +%F-%H%M%S)
B="$HOME/ops/backups/$TS"
mkdir -p "$B"
sudo ufw status numbered > "$B/ufw-status-numbered.txt"
sudo iptables-save > "$B/iptables-save.txt"
sudo nft list ruleset > "$B/nft-ruleset.txt" 2>/dev/null || true
sudo cp -a /etc/ssh/sshd_config "$B/sshd_config"
sudo cp -a /etc/sysctl.conf "$B/sysctl.conf"
sudo cp -a /etc/sysctl.d "$B/sysctl.d"
```

## UFW cleanup

### Before
```
[ 1] 2222/tcp    ALLOW IN
[ 2] OpenSSH     ALLOW IN
[ 3] 80          ALLOW IN
[ 4] 443         ALLOW IN
[ 5] 2222        DENY IN
[ 6] 8766/tcp    ALLOW IN  # Tribute Overlay Tool - dev
[ 7-12] same rules v6
```

### Delete stale rules (highest number first)
```bash
# Find numbered lines for ports to remove
sudo ufw status numbered | grep -E '2222|8766' | sed -n 's/^\[ *\([0-9]\+\).*/\1/p' | sort -nr

# Delete each (example)
sudo ufw --force delete 12
sudo ufw --force delete 11
# ... down to lowest number

sudo ufw reload
```

### After
```
Status: active
To                         Action      From
--                         ------      ----
22/tcp (OpenSSH)           ALLOW IN    Anywhere
80/tcp                     ALLOW IN    Anywhere
443/tcp                    ALLOW IN    Anywhere
22/tcp (OpenSSH (v6))      ALLOW IN    Anywhere (v6)
80 (v6)                    ALLOW IN    Anywhere (v6)
443 (v6)                   ALLOW IN    Anywhere (v6)
Default: deny (incoming), allow (outgoing), deny (routed)
```

## DOCKER-USER shield (temporary, not survive-reboot)

### Identify Docker published ports
From `docker ps`:
- auth-service-postgres  `0.0.0.0:55432`
- platform-suite-backend  `0.0.0.0:3100`
- platform-suite-frontend `0.0.0.0:3101`
- security-gateway-gateway   `0.0.0.0:8080`

### Apply DROP rules
```bash
sudo iptables -N DOCKER-USER 2>/dev/null || true
for p in 55432 3100 3101 8080; do
  sudo iptables -C DOCKER-USER -p tcp -m conntrack --ctorigdstport "$p" -j DROP 2>/dev/null || \
  sudo iptables -I DOCKER-USER -p tcp -m conntrack --ctorigdstport "$p" -j DROP
done
```

### Verify
```bash
sudo iptables -S DOCKER-USER
# Expect:
# -A DOCKER-USER -p tcp -m conntrack --ctorigdstport 8080 -j DROP
# -A DOCKER-USER -p tcp -m conntrack --ctorigdstport 3101 -j DROP
# -A DOCKER-USER -p tcp -m conntrack --ctorigdstport 3100 -j DROP
# -A DOCKER-USER -p tcp -m conntrack --ctorigdstport 55432 -j DROP
```

### Remove individual rule (if blocking a port that must be public)
```bash
sudo iptables -D DOCKER-USER -p tcp -m conntrack --ctorigdstport 8080 -j DROP
```

## Systemd oneshot unit for reboot survival

`/usr/local/bin/docker-shield.sh`:
```bash
#!/bin/sh
for p in 55432 3100 3101 8080; do
  iptables -C DOCKER-USER -p tcp -m conntrack --ctorigdstport "$p" -j DROP 2>/dev/null || \
  iptables -I DOCKER-USER -p tcp -m conntrack --ctorigdstport "$p" -j DROP
done
```

`/etc/systemd/system/docker-shield.service`:
```ini
[Unit]
Description=Docker published ports firewall shield
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/docker-shield.sh

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable docker-shield.service
sudo systemctl start docker-shield.service
sudo systemctl status docker-shield.service
```

### iptables-persistent TRIPWIRE
Installing `iptables-persistent` / `netfilter-persistent` on Ubuntu with `ufw` present **removes ufw** during install. Recovery:

```bash
export DEBIAN_FRONTEND=noninteractive
sudo apt-get remove -y iptables-persistent netfilter-persistent
sudo apt-get install --reinstall -y ufw
sudo ufw --force enable
```

Do NOT attempt the iptables-persistent path. Use the systemd oneshot above instead for Docker iptables persistence.

## fail2ban

### Install & configure
```bash
sudo apt-get install -y fail2ban

sudo tee /etc/fail2ban/jail.d/local-ssh.conf >/dev/null <<'EOF'
[sshd]
enabled = true
backend = systemd
maxretry = 4
findtime = 10m
bantime = 1h
EOF

sudo systemctl enable --now fail2ban
```

### Verify
```bash
sudo fail2ban-client status
sudo fail2ban-client status sshd
# Expected: Currently banned >= 0, Total banned > 0 if any attacker hit port 22
```

## SSH hardening (staged)

### Stage A (immediately safe)
`/etc/ssh/sshd_config.d/99-hardening.conf`:
```
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication yes
KbdInteractiveAuthentication no
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowUsers meowlabs
```

```bash
sudo sshd -t
sudo systemctl reload ssh
sudo sshd -T | grep -E '^(permitrootlogin|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|maxauthtries|logingracetime|x11forwarding|allowusers) '
```

### Test from second SSH session
```bash
# Second terminal:
ssh meowlabs@<host>
# If this succeeds, Stage A is safe.
```

### Stage B (defer days later)
```bash
echo 'PasswordAuthentication no' | sudo tee -a /etc/ssh/sshd_config.d/99-hardening.conf
sudo sshd -t
sudo systemctl reload ssh
```

### Rollback (if lockout happens)
```bash
sudo rm /etc/ssh/sshd_config.d/99-hardening.conf
sudo systemctl reload ssh
```

## Sysctl hardening

`/etc/sysctl.d/99-vps-hardening.conf`:
```
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1
```

```bash
sudo sysctl --system
sysctl net.ipv4.conf.all.send_redirects
sysctl net.ipv4.conf.default.send_redirects
sysctl net.ipv4.tcp_syncookies
```

All values should show `0` (or `1` for syncookies).

## Phase 2: Permanent rebind in compose

### Before (0.0.0.0 published)
```yaml
ports:
  - "55432:5432"
  - "3100:3000"
  - "3101:3000"
  - "8080:8080"
```

### After (loopback only)
```yaml
ports:
  - "127.0.0.1:55432:5432"
  - "127.0.0.1:3100:3000"
  - "127.0.0.1:3101:3000"
  - "127.0.0.1:8080:8080"
```

### Restart
```bash
docker compose up -d --no-deps <service>
# If container name conflicts: docker rm -f <container> first
```

### Verify
```bash
ss -ltnp | grep -E ':(55432|3100|3101|8080)\b'
# Expected: all show 127.0.0.1:<PORT>
```

## Final verification matrix

| Check | Command | Expected |
|---|---|---|
| UFW | `sudo ufw status verbose` | `22/80/443 only, default deny` |
| Docker ports | `ss -ltnp \| grep -E ':(55432\|3100\|3101\|8080)\b'` | `127.0.0.1:<PORT>` |
| fail2ban | `sudo fail2ban-client status sshd` | jail active, IPs banned |
| SSH config | `sudo sshd -T \| grep ...` | `permitrootlogin no`, `allowusers ...` |
| sysctl | `sysctl net.ipv4.conf.all.send_redirects` | `= 0` |
| nginx | `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80` | `200` or `302` |
| Docker shield | `sudo iptables -S DOCKER-USER` | DROP rules present |
