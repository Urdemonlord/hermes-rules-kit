# Nginx Immutable Lock — Prevent Deploy Scripts from Overwriting Proxy Config

## The Problem

On a VPS running multiple apps (e.g., AgentWA on port 3000, the auth service on 3001), a blue-green deploy script that swaps nginx `proxy_pass` between ports will **permanently redirect traffic to the wrong app** if the swap logic is incorrect or the script fails mid-execution. Unlike process-level failures (which are visible in `pm2 list`), nginx config misdirection is silent — traffic silently routes to the wrong app until someone notices.

Real-world symptom:
```
curl https://agentwa.meowlabs.id/ → returns the auth service HTML
```

## The Fix: `chattr +i`

Make the nginx site config **immutable** (even root cannot write to it without explicitly removing the attribute):

```bash
# Lock the config (immutable flag)
sudo chattr +i /etc/nginx/sites-enabled/agentwa.meowlabs.id

# Verify lock is active
lsattr /etc/nginx/sites-enabled/agentwa.meowlabs.id
# Output: ----i---------e------- (the 'i' = immutable)

# To temporarily allow editing (e.g., certbot renewal):
sudo chattr -i /etc/nginx/sites-enabled/agentwa.meowlabs.id
# ... make changes ...
sudo chattr +i /etc/nginx/sites-enabled/agentwa.meowlabs.id
```

## Why This Works

- `chattr +i` sets the **immutable attribute** on the file at the filesystem level
- Even `root` cannot write to the file without first removing the attribute
- Certbot's auto-renewal hook can still work if the hook explicitly removes and restores the attribute
- No service restart or special tooling required

## Deploy Script Rule

**Never modify nginx `proxy_pass` in a deploy script on a multi-app VPS.**

Instead, always run the target app on the same port (e.g., 3000) and let PM2 manage the process lifecycle:

```bash
# WRONG — modifies nginx, causes cross-app misdirection
sed -i "s|proxy_pass http://127.0.0.1:[0-9]*|proxy_pass http://127.0.0.1:$NEXT_PORT|" "$NGINX_CONF"
nginx -s reload

# CORRECT — PM2 manages the port, nginx stays untouched
pm2 stop agentwa-web
pm2 delete agentwa-web
pm2 start ecosystem.config.js
```

## Certbot + Immutable Config

If Let's Encrypt certbot tries to write to the config during renewal, the immutable flag will block it. Add to certbot's renewal hook:

```bash
# /etc/letsencrypt/renewal-hooks/pre/ unlock-nginx-config
#!/bin/bash
chattr -i /etc/nginx/sites-enabled/your-domain.conf

# /etc/letsencrypt/renewal-hooks/post/ relock-nginx-config
#!/bin/bash
chattr +i /etc/nginx/sites-enabled/your-domain.conf
```

Make both scripts executable: `chmod +x`.

## Verification After Deploy

After any deploy, always verify the correct app is responding:

```bash
curl -s https://agentwa.meowlabs.id/ | grep -o 'AgentWA\|the auth service' | head -1
# Expected: AgentWA
```
