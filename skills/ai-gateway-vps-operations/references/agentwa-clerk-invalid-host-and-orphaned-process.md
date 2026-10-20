# AgentWA + Clerk "Invalid Host header" + Orphaned Process Recovery

## Scenario
AgentWA Next.js app deployed via PM2 on VPS. Every few hours/days, production returns:
```
{"error":"Invalid Host header. Bridge accepts loopback hosts only."}
```

All symptoms suggest Clerk middleware or Next.js config issue — but the real root cause was an **orphaned non-PM2 Express process** occupying port 3000.

## Diagnosis sequence (correct order)

### Step 1: Check PM2 state first
```bash
pm2 list
```
If PM2 shows `errored` with high restart count (`↺`), PM2 is failing to keep the app alive.

### Step 2: Check what is actually on the port
```bash
ss -tlnp | grep 3000
```
This reveals the real process. If the owning process is NOT the PM2 PID, you have an orphaned process.

### Step 3: Identify the orphan
```bash
# Get the PID from ss output, then:
cat /proc/<PID>/cmdline | tr '\0' ' '
# or
ls -la /proc/<PID>/exe  # follows symlink to actual binary
```
In the AgentWA case: `/proc/<PID>/exe -> /home/user/.hermes/node/bin/node` — a Hermes/legacy next-server orphan.

### Step 4: Kill ONLY the orphan, not PM2's process
```bash
fuser -k 3000/tcp   # kills whatever holds port 3000
# OR
kill -9 <PID>
```
**Why `fuser`**: PM2 may have lost track of the orphan (PM2 only manages processes it started). `fuser` kills by port, not by PM2 tracking.

### Step 5: Verify port is free, then restart PM2 cleanly
```bash
ss -tlnp | grep 3000 || echo "Port FREE"
pm2 delete agentwa-web 2>/dev/null; pm2 start ecosystem.config.js
```

### Step 6: Verify fix
```bash
curl -s https://agentwa.meowlabs.id/ | grep -o 'AgentWA\|Login' | sort | uniq -c
```

## Prevention: Lock nginx config immutably
`deploy.sh` was repeatedly overwriting nginx config to point to wrong port (3001 instead of 3000). Fix: make immutable until explicitly needed.
```bash
sudo chattr +i /etc/nginx/sites-enabled/agentwa.meowlabs.id
# To edit later:
sudo chattr -i /etc/nginx/sites-enabled/agentwa.meowlabs.id
```

## The "Invalid Host header" misnomer
The error message `"Invalid Host header. Bridge accepts loopback hosts only."` was initially attributed to Clerk middleware. In this case:
- The message was coming from an **unrelated Express server** (docker-proxy for auth-service-demo) that happened to be on the same port after PM2 lost the port race.
- The real fix was not Clerk config changes — it was evicting the port squatter.

Clerk's own "bridge loopback" error would occur if `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is missing from production env. That was NOT the issue here (key was present).

## PM2 + orphaned process pattern
When you see:
- PM2 `errored` state with restart count > 0
- Port still occupied
- PM2 restart doesn't help

→ Another process grabbed the port before PM2 could bind. PM2 cannot manage processes it didn't start.

## Zero-downtime deploy safety
Blue-green deploy scripts that swap nginx upstream ports are risky on multi-app VPS. Pattern that works:
- AgentWA always on port 3000
- nginx immutable-locked to port 3000
- deploy script builds fresh, then `pm2 stop && pm2 start` on same port 3000
- Brief connection drop during stop/start is acceptable for non-critical internal tools
