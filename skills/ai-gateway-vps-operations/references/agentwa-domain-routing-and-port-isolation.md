# AgentWA + the gateway coexistence on one VPS (routing + port isolation)

## Problem pattern
- `agentwa.meowlabs.id` showed wrong app branding/content because Nginx pointed to a process on the expected port, but the process was a different app (the gateway).
- Request to close DB public port was interpreted as stopping DB service, causing avoidable downtime.

## Proven fix sequence
1. Identify actual process behind app port:
   - `ss -ltnp | grep <port>`
   - map PID -> cwd/cmdline (`readlink -f /proc/<pid>/cwd`, `tr '\0' ' ' < /proc/<pid>/cmdline`)
2. Ensure domain-specific Nginx vhost points to intended upstream port.
3. If two apps need coexistence, assign dedicated ports and dedicated services:
   - AgentWA web: `20128`
   - the gateway: `20129`
4. Keep DB service running while removing internet exposure:
   - bind publish target to loopback only (e.g., `127.0.0.1:5433:5432`).
5. Verify all layers:
   - local upstream health
   - origin HTTPS host-resolve check
   - public domain check through CDN/proxy

## Verification matrix (minimal)
- AgentWA public health: `https://agentwa.meowlabs.id/api/health` => 200 + `service=agentwa-web`
- the gateway public API: `https://api.meowlabs.store/v1/models` => 200
- the gateway local API: `http://127.0.0.1:20129/v1/models` => 200
- DB exposure: `ss -ltnp | grep 5433` should show `127.0.0.1:5433` (not `0.0.0.0`)

## Pitfalls observed
- Changing upstream to "currently alive port" can still be wrong if that port serves another app.
- Cloudflare can mask origin state temporarily; always test origin with `--resolve` before concluding app is down.
- When rotating/rerouting services, disable/enable systemd units explicitly to avoid zombie restarts on old ports.
