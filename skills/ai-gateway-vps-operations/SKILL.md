---
name: ai-gateway-vps-operations
description: Class-level operations guide for deploying and running AI gateways and Hermes services on VPS with systemd, reverse proxying, auth, and troubleshooting.
---

# AI Gateway + VPS Operations

Umbrella for production operations of:
- AI routing gateways (the gateway/OpenAI-compatible)
- Hermes gateway/API services
- Reverse-proxy/topology and no-sudo fallback patterns

## Core model
`Client -> Public domain/reverse proxy -> app wrapper/user service -> gateway/hermes backend`

## Standard workflow
1. Confirm target project root/repo explicitly before running scaffold/install commands. If multiple apps exist, create/use a dedicated directory for new products.
2. Discover live state first (ports, processes, systemd, proxy rules).
3. Before disruptive actions (stop service/container, close tunnel, change public port), state exact impact and get explicit user OK.
4. For user-facing ops requests that can be interpreted as normal-vs-disruptive (e.g., "close public port" vs "keep service running"), confirm intent before execution and prefer least-disruptive path first.
5. Never print raw secrets from env/service files in chat output; redact values and recommend rotation if exposure occurred.
6. Configure secrets in env files (never frontend).
7. Deploy as user-owned service when possible.
8. Wire public routing and auth layers explicitly.
9. Verify both local-backend and public-domain paths.
10. Add rate-limit/quota/logging before exposure.
   - If user intent is ambiguous (e.g. "tutup port publik"), default to read-only audit first (ports/process map), then ask scope confirmation before any stop/restart.
   - On Hermes-managed hosts, explicitly confirm whether `hermes-gateway`/chat connectivity must stay up before touching services.
4. Configure secrets in env files (never frontend).
5. Deploy as user-owned service when possible.
   - If a partial action was started and interrupted, re-verify live state before continuing; do not assume prior stop/disable succeeded.
4. Configure secrets in env files (never frontend).
5. Deploy as user-owned service when possible.
6. Wire public routing and auth layers explicitly.
7. Verify both local-backend and public-domain paths.
8. Add rate-limit/quota/logging before exposure.

## High-frequency pitfalls (VPS multi-app hosts)
- **xAI/Grok API Confusion**: Users with X Premium (\"Cenblu\" / Centang Biru) get Grok access *in the Twitter/X app*, but this does **not** grant free API credits on `console.x.ai`. API access is strictly pay-as-you-go. When users ask why `console.x.ai` asks for credits despite having X Premium, explain the separation between app access and API access. Provide fully free alternatives (e.g. Gemini via AI Studio, OpenRouter free tier, or Hermes's built-in OAuth providers like `nous` or `openai-codex`) if they want to avoid top-ups.
- **xAI OAuth Callback Timeout in VPS/Headless**: When using `hermes model` to auth with `xAI Grok OAuth` in a VPS/SSH session, Hermes starts a local listener (e.g. `http://127.0.0.1:56121/callback`). The user clicks the auth URL on their local machine, but the resulting callback URL fails because `127.0.0.1` points to their local machine, not the VPS.
  - **Fix**: Instruct the user to copy the failed `http://127.0.0.1...` URL from their local browser's address bar.
  - Then, in a *second* SSH terminal on the VPS, run `curl "COPIED_URL"` to manually deliver the callback payload to the waiting Hermes process. Do not let the user wait idly while Hermes blocks.
- **Deploy-script nginx config overwrite trap**: Blue-green deploy scripts that hot-swap nginx `proxy_pass` on each deploy will clobber other services running on that host. On a multi-app VPS, `sed -i 's|proxy_pass http://127.0.0.1:3000|proxy_pass http://127.0.0.1:3001|' /etc/nginx/sites-enabled/<domain>` in a deploy script can silently redirect AgentWA traffic to the auth service or vice versa. Fix: make the nginx config immutable with `sudo chattr +i /etc/nginx/sites-enabled/<domain>` — this survives script execution and `nginx reload`. Verify with `lsattr /etc/nginx/sites-enabled/<domain>` (should show `----i---------e`).
- **Docker compose port isolation on shared VPS:** When deploying docker-compose stacks on a VPS with existing services, always (a) check `ss -ltnp` for ALL ports the compose file maps to host; (b) bind critical services to `127.0.0.1:HOST_PORT:CONTAINER_PORT` so they're only accessible via local nginx reverse proxy, not directly from internet; (c) remove host port mapping for internal-only services (workers, extra nginx containers) — they communicate via docker internal network; (d) prefer 127.0.0.1 binding for any port that doesn't need direct external access.
- **DNS/proxy ownership mismatch:** if public domain returns provider-specific errors (e.g., Vercel deployment-not-found), domain is not pointing to current VPS route yet. Separate app readiness from DNS cutover tasks.
- **80-only vhost trap:** creating only `listen 80` can look correct in local HTTP checks while public HTTPS still hits a different app/vhost. Always validate `:443` mapping and certificate for the exact host.
- **Cloudflare proxy misread:** with orange-cloud enabled, `dig` returns Cloudflare IPs, not origin. Use host-header/local origin checks to validate Nginx mapping before blaming app code.
- **Cloudflare free-tier proxy 100s timeout:** orange-cloud proxied records have a hard 100-second timeout on the free tier. Any backend taking longer (Playwright scraping, file processing, ML inference) returns `504 Gateway Timeout` from Cloudflare — not nginx. Fix: use **grey cloud** (`DNS-only`) for long-running backends where IP protection is not critical. Verify by checking `dig +short <domain>` returns origin IP (not CF IPs) after flipping.
- **Stale static asset trap after deploy:** public UI may still show old JS/login due to CDN/browser cache even when origin files are updated. Add immediate script-version cache busting in entry HTML (`app.js?v=...`, `api.js?v=...`) and verify with explicit `?v=` URL before concluding deploy failed.
- **Nginx Permission Denied for `/home/user/` serving:** Nginx runs as `www-data`. Serving static files from `/home/user/app/ui/` fails with `stat() "/home/user/..." failed (13: Permission denied)` because www-data cannot traverse `/home/user/`. Fix: copy the static files to `/var/www/<appname>/` with `755` on dir and `644` on files, then point `root` to that path.
- **Nginx proxy_pass with trailing URI strips location prefix:** `proxy_pass http://127.0.0.1:8082/api/;` (WITH trailing URI) replaces the matched location prefix with `/api/`. For `location /api/`, request `/api/v1/healthz` becomes `http://127.0.0.1:8082/api/v1/healthz` (prefix unchanged, no issue). But request `/api/v1` becomes `http://127.0.0.1:8082/api/v1` (also fine). However, with axum `.nest("/api/v1", router)`, the backend router only matches paths under `/api/v1`, so the root `/api/v1` returns 404 unless the nested router has a handler at `/`. Fix: (a) add a root `GET /` handler in the nested router returning API info, OR (b) use `proxy_pass http://127.0.0.1:8082;` (NO trailing URI) which passes the full original request URI unchanged — combined with `rewrite ^/api/v1/?$ /api/v1 break;` if needed for normalizing trailing slash. When using no-URI proxy_pass, the backend receives the exact same path the client sent, preserving axum nest behavior.
- **Public-port closure vs service shutdown confusion:** when user asks to "close public port" for Dockerized DB/app, do not stop the service/container unless explicitly requested. Prefer rebinding publish target to loopback (`127.0.0.1:HOST:CONTAINER`) or host firewall rules so service remains up while internet exposure is removed.
- **Operator intent confirmation failure:** requests like "close tunnel/port" often mean "reduce exposure while keeping service alive." Confirm whether service uptime must be preserved before stopping units/processes.
- **Container exposure confusion:** "close public DB port" does not mean "stop database". On Docker hosts, close exposure by rebinding host port to loopback (`127.0.0.1:host_port:container_port`) or firewalling, while keeping container running.
- **Wrong service behind correct port:** a port can be healthy but served by the wrong app (e.g., stale the gateway service owning target port). Verify process identity (`ss -ltnp` + `/proc/<pid>/cwd` + cmdline), not just HTTP 200.
- **Cross-project inference trap on multi-app VPS:** do not infer that two projects share infrastructure just because names, ports, folders, or runtimes look similar. "There is a Postgres on this box" is not evidence that a broken sibling app should use it. Cross-project relationships are valid only when explicitly stated in env, compose, systemd, nginx, deploy scripts, or project docs.
- **Free-looking port trap:** a dead listener or an expected-but-missing port is not automatically available for reuse. It may be the reserved port of a stale or parked project. Before reusing a port, classify the service state (active-but-broken, intentionally parked, obsolete candidate, or another project's asset) and verify ownership from the project's source of truth.
- **Docker host-network loopback trap:** A container running with `network_mode: host` that points `DATABASE_URL` or another upstream at `127.0.0.1:<port>` is talking to the VPS host loopback, not to a sibling container. If the host is not actually listening on that port, the service will crash-loop forever with `connect: connection refused`. Diagnose by checking both the container's network mode (`docker inspect ... .NetworkSettings.Networks`) and the real host listener map (`ss -ltnp | grep <port>`).
- **Firewall parity trap on shared VPS:** A service listening on `0.0.0.0:<port>` is not automatically internet-exposed. On hosts with `ufw` default `deny incoming`, the port may still be effectively private unless explicitly allowed. Before telling the user a port is "public", verify BOTH the bind address and firewall policy (`ss -tulpen` + `ufw status verbose`). This avoids unnecessary emergency rebinding of ports that are already blocked at the firewall layer.
- **PM2 false-green trap:** `pm2 ls` / `pm2 describe` can say `online` even when the app has no working listener. Treat `PID N/A`, missing port listeners, or ownership conflicts (`EADDRINUSE` with another supervisor already bound) as proof the PM2 entry is stale/broken. If `pm2 describe` points to a missing `exec cwd` or missing runtime path, classify it as a stale supervisor entry, not a live app. Safe cleanup pattern: back up `~/.pm2/dump.pm2`, run `pm2 delete <name>`, then `pm2 save`, and verify removal from both `pm2 ls` and the dump file.
- **Stale-log after flush pitfall:** `pm2 flush` is safe for no-downtime cleanup, but it also erases the easy tail evidence you might need for later debugging. If you suspect a broken PM2 app, read/backup its error log before flushing, or at least collect `pm2 describe` + port-ownership evidence first.
- **Intermittent 502 / Bad Gateway despite occasional success:** if public requests alternate between success (`200`/`307`) and `502`, suspect an upstream **restart loop / flapping service**, not just nginx misrouting. Check the reverse-proxy target first, then inspect the owning systemd unit's `restart counter`, `MainPID`, and recent journal lines for patterns like `Ready` followed seconds later by `Exiting...`. A single successful local `curl` is not enough to clear the backend — if the upstream exits every few seconds, nginx will randomly catch it down and emit `502`.
- **Cross-user process ownership trap:** On multi-user VPS, a gateway may have been started by `ubuntu` (or another login user) while the current operator is `meowlabs`. The current user cannot `kill`, `systemctl --user`, or directly restart that process. Symptom: "Operation not permitted" when trying to manage the PID. Fix: either (a) ask the owning user to restart with updated `EnvironmentFile`, or (b) recreate as a proper systemd user service owned by the target operator user. Never assume you can manage processes started by other UNIX users.
- **Runtime-manager fragmentation on shared VPS:** when a user says "nyalakan semua service", do not check only one supervisor. Audit **systemd user services + PM2 + Docker + nginx upstream targets** together, then recover in that order: discover listeners/domains first, start the missing runtime, and only then verify public routes.
- **Compose revival with pre-existing named containers:** old VPS stacks often leave a healthy DB container alive while app containers are gone. `docker-compose up` can fail with `container name ... already in use` or create a fresh network that the old DB is not attached to. Safer recovery pattern: keep the existing stateful DB container, connect it to the new compose network if needed (`docker network connect --alias postgres <compose_net> <db_container>`), then start only app services with `docker-compose up -d --no-deps <services>`.
- **Docker-proxy ghost blocking port after container disappears:** A container can be completely gone (`docker ps -a` shows nothing) while its docker-proxy process survives and holds the port. `docker compose up -d` fails with `Bind for 0.0.0.0:<PORT> failed: port is already allocated`, but `ss -tlnp | grep <PORT>` shows `docker-pr` processes with no matching container. Fix: kill the orphan docker-proxy PIDs (`sudo kill <PID>`), verify port is free, then retry. See `references/docker-proxy-ghost-port-cleanup.md` for full diagnosis, fix, and prevention (including watchdog integration and the reappearance pitfall).
- **Frontend/backend host-port drift after reboot or rebuild:** nginx may still proxy to the old frontend port while compose maps the backend onto that port. For app-control panels, verify host port intent explicitly from nginx and compose together: frontend/public UI should usually keep the legacy nginx upstream port, while backend/API should move to a different host port. Do not declare recovery complete until both the public page and direct backend health text match the intended services.
- **Partial compose source loss with surviving containers:** if compose labels show a project/working_dir but the original repo/config is missing or incomplete on disk, recover by cloning the repo again, rebuilding only the missing image, and attaching the new container to the existing compose network/services instead of tearing down healthy siblings.
- **Static nginx 403 on bind-mounted web root:** when an `nginx:alpine` web container returns `403` on `/` and logs `directory index of "/usr/share/nginx/html/" is forbidden`, inspect `docker inspect` mounts before touching nginx config. On shared VPS this often means the host bind source (for example `web/dist`) is empty, missing, or unreadable after reboot/cleanup/source drift. Restore or create `index.html`, fix traverse/read perms on parent dirs/files, and if the container still sees an empty mount, recreate the static container explicitly.
- **TanStack Start preview trap in production checks:** `vite preview` may fail or drift from real runtime expectations when server artifacts differ (e.g., plugin expects `dist/server/server.js` while build emits `dist/server/index.js`). Do not treat preview failure as production outage by default. First validate the currently serving process and public routes, then choose an explicit production serve mode (SSR entrypoint or static `dist/client`) and make it persistent with systemd.
- **ML security gateway fail-open bypass (the security gateway pattern):** A security gateway with `fail_open: true` + short timeout (5s) and a Python inference worker with exception-swallowing creates a silent zero-alert bypass. The model (498MB ONNX) OOMs in a 384MB container; the Python scan endpoint catches the exception and returns `SAFE` with `source="classifier-unavailable"`; the Rust gateway times out at 5s and also returns `is_safe: true`; the health endpoint hardcodes `"detectors_loaded": True`. **All prompts pass through unscanned.** Prevention triad: (1) health endpoint must actually load the model on each check, (2) container memory must exceed model.size × 2, (3) gateway timeout must exceed model p99 inference time. Monitor for `"source": "classifier-unavailable"` in scan responses — that is the signal the model is not running.

## Application layer hardening

After Phase 2 (port rebind), harden the application/routing layer:

### nginx.conf hardening

See `references/vps-nginx-hardening.md` for a complete hardened `nginx.conf` template with:
- Rate limiting zones (general 30r/s, login 5r/m)
- Security headers (X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy)
- `server_tokens off` to hide nginx version
- gzip tuning (vary, proxied, compression level 6, SVG support)
- Client body/buffer/timeout limits
- SSL modern: TLSv1.2+v1.3 only, session cache

Apply: overwrite `/etc/nginx/nginx.conf`, then `nginx -t && nginx -s reload`.

### fail2ban — multi-jail

```ini
# /etc/fail2ban/jail.local
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true
logpath = /var/log/nginx/error.log

[nginx-botsearch]
enabled = true
logpath = /var/log/nginx/access.log
maxretry = 2
findtime = 30m
bantime = 24h
```

### Docker RAM limits (stability, not just security)

Without limits, any container can exhaust RAM and trigger swap saturation. Apply to ALL running containers (not just a few):

```bash
# --memory and --memory-swap MUST be set together
docker update --memory 128m --memory-swap 256m <container>
```

Pitfall: `--memory-swap` default is 2× `--memory`. If the container previously had a different swap value, Docker rejects the update with:
`"Memory limit should be smaller than already set memoryswap limit, update the memoryswap at the same time"`
Fix: always pass both `--memory X --memory-swap Y` (where Y > X) as a pair. Single-arg `--memory` is never enough.

See `references/vps-stability-hardening.md` for full container profile table and recommended limits per service type.

### Weekly auto-prune (disk management)

Prevent build cache + dangling images from accumulating:

```bash
# crontab (root)
0 3 * * 1 docker system prune -af --filter 'until=24h' >/dev/null 2>&1
```

This runs every Monday 3AM, skipping images <24h old. The `until` filter is important — without it a daily-running service's images get pruned immediately, triggering re-downloads on restart.

Old kernel cleanup: `apt autoremove --purge` often skips `linux-image-*` packages because they're marked manual. Use `dpkg --purge` explicitly:

```bash
dpkg -l | grep -E 'linux-(image|modules)-[0-9]+' | grep -v $(uname -r | sed 's/-generic//')
# For each non-current:
sudo dpkg --purge linux-image-6.8.0-XXX-generic linux-modules-6.8.0-XXX-generic linux-modules-extra-6.8.0-XXX-generic
```

## Host hardening sequence (multi-app VPS)

When hardening a VPS from scratch or closing public exposure gaps, use this order for safest results. Every step is reversible and no step requires project-code changes.

### Phase 0: Pre-flight
- Open **2 SSH sessions**. Keep the original session alive until every step is verified.
- Backup: `ufw status numbered`, `iptables-save`, `sshd_config`, `/etc/sysctl.conf`, `/etc/sysctl.d/`.
- Audit live ports, Docker publish maps, nginx upstreams, and supervisor state before touching any config.

### Phase 1: Firewall + exposure reduction (safe, no service restart)
1. **Tighten UFW to minimum**:
   - Remove stale rules (dev ports, experimental services, duplicate allow/deny pairs).
   - Remove by number from highest to lowest to avoid renumbering issues.
   - Target: only `22/tcp`, `80/tcp`, `443/tcp`.
2. **Shield Docker published ports** (temporary, survive-reboot optional):
   - Use `iptables -I DOCKER-USER -p tcp -m conntrack --ctorigdstport <PORT> -j DROP` for ports that don't need direct external access but are still published to `0.0.0.0`.
   - Verify: `ss -ltnup` still shows the port, but external clients cannot reach it through the Docker bridge.
   - For reboot survival: create a systemd oneshot unit (`After=docker.service`) that re-applies these rules. See `DOCKER-USER shield via systemd oneshot` below.
3. **Install fail2ban for sshd**:
   - Minimum config: `maxretry=4`, `findtime=10m`, `bantime=1h`, `backend=systemd`.
4. **Apply SSH hardening (staged)**:
   - **Stage A** (safe, test-gated): create `/etc/ssh/sshd_config.d/99-hardening.conf` with:
     - `PermitRootLogin no`
     - `PubkeyAuthentication yes`
     - `KbdInteractiveAuthentication no`
     - `MaxAuthTries 3`
     - `LoginGraceTime 30`
     - `X11Forwarding no`
     - `AllowUsers <username>`
   - Validate: `sudo sshd -t`
   - Reload: `sudo systemctl reload ssh`
   - **Test** from the second SSH session. If login fails, rollback: remove the drop-in and reload.
   - **Stage B** (days later, after confirming key auth is stable): append `PasswordAuthentication no`.
   - Sanity check before Stage B: `test -s ~/.ssh/authorized_keys && echo OK || echo MISSING`
5. **Apply sysctl network hardening**:
   - `/etc/sysctl.d/99-vps-hardening.conf`:
     - `send_redirects = 0`
     - `accept_redirects = 0`
     - `accept_source_route = 0`
     - `tcp_syncookies = 1`
     - `log_martians = 1`
   - Verify: `sysctl <key>` returns the new value.

### Phase 2: Permanent rebind (requires brief service restart)
After Phase 1 is verified and stable:
1. For each Docker container published to `0.0.0.0` that should only be accessed via nginx:
   - Edit compose port mapping from `"PORT:CONTAINER_PORT"` to `"127.0.0.1:PORT:CONTAINER_PORT"`.
   - Restart only the affected container: `docker compose up -d --no-deps <service>`.
   - Verify: `ss -ltnp | grep <PORT>` shows `127.0.0.1`.
   - Verify upstream nginx can still reach it via loopback.
2. Non-Docker services (systemd/PM2/Node):
   - Bind to `127.0.0.1` explicitly in runtime args (e.g., `-H 127.0.0.1` for Next.js, `HOST=127.0.0.1` for Node env).
3. Remove the Phase 1 DOCKER-USER shield rules for ports that are now permanently loopback-bound (they become redundant but harmless — optional cleanup).

### Pitfalls
- **iptables-persistent removes ufw on Ubuntu**: Installing `iptables-persistent` / `netfilter-persistent` on a system where `ufw` is installed causes apt to remove `ufw` because of conflicting package architecture. After removal, firewall state reverts to all-ACCEPT. Recovery: `sudo apt-get remove iptables-persistent netfilter-persistent && sudo apt-get install --reinstall ufw && sudo ufw --force enable`. Prefer the systemd oneshot pattern below instead of `iptables-persistent` for Docker iptables rules.
- **Second SSH session is mandatory**: Every SSH config change must be validated from a second session before closing the first. Locking yourself out of a remote VPS requires provider console access to fix. The staged approach (defer `PasswordAuthentication no`) further reduces this risk.
- **Reboot survival gap**: UFW rules persist across reboot by default. Docker `DOCKER-USER` iptables rules do NOT survive reboot unless persisted. The systemd oneshot unit below is the safest way to persist them without introducing the `iptables-persistent` conflict.

### DOCKER-USER shield via systemd oneshot

This pattern restores DOCKER-USER DROP rules after Docker starts, surviving reboot with zero dependency on `iptables-persistent`:

```bash
# /usr/local/bin/docker-shield.sh
for p in 55432 3100 3101 8080; do
  iptables -C DOCKER-USER -p tcp -m conntrack --ctorigdstport "$p" -j DROP 2>/dev/null || \
  iptables -I DOCKER-USER -p tcp -m conntrack --ctorigdstport "$p" -j DROP
done
```

```ini
# /etc/systemd/system/docker-shield.service
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

Enable: `sudo systemctl enable --now docker-shield.service`.

Post-reboot verification: `sudo iptables -S DOCKER-USER`.

This is strictly an interim shield for Phase 1. Once Phase 2 (permanent loopback rebind in compose) is complete, the unit becomes redundant but harmless.

### Reference checklist for host hardening final state
| Layer | Expected |
|---|---|
| UFW | Only `22`, `80`, `443` allowed; default `deny incoming` |
| Docker direct access | No `0.0.0.0` bind for internal services (DB, gateway, backend) |
| fail2ban | sshd jail active |
| SSH | `PermitRootLogin no`, `MaxAuthTries 3`, `AllowUsers <user>` set |
| sysctl | `send_redirects=0`, `tcp_syncookies=1`, `log_martians=1` |

## Auth-layer rule
Always test two layers independently:
- backend direct endpoint (`127.0.0.1:<port>`)
- public routed endpoint (`https://domain/...`)

If keys work locally but fail publicly, debug wrapper/proxy auth mismatch first.

## Route-mapping verification (critical)
Do not trust a single health endpoint as proof the domain points to the intended app.
Use a small verification matrix:
- `GET /api/health` on local and public
- one write path (e.g. `POST /api/agents`) on local and public
- a temporary fingerprint route (e.g. `/api/debug/routes`) that returns service marker

## Multi-project VPS boundary control (critical)
When a VPS hosts several unrelated apps, establish a source of truth before any write action:
- create `~/ops/vps-project-registry.md`
- create `~/ops/ports.md`
- add per-project `.ops-boundary.md`

These files should define owned ports, owned DB/Redis, project status (active / parked / obsolete candidate), and explicit do-not-cross rules. This prevents agents from "cleaning up" or repointing sibling projects based on guesswork.

Boundary rollout rule:
- do not stop at top-level repos only; add `.ops-boundary.md` to meaningful subprojects/runtime roots too (`backend/`, `frontend/`, `deploy/`, hidden runtime roots under `.hermes/`, `.the gateway/`, `.config/`) when they may be operated independently.
- exclude build artifacts like `.next/` and cache directories from boundary coverage math.
- do not treat an expected-but-dead port as free for reuse until the owning project's registry/boundary says the project is obsolete.

Preflight for multi-project boundary-sensitive changes:
- `ss -tulpen`
- `docker ps -a`
- `docker network ls`
- `docker volume ls`
- `pm2 ls`
- `systemctl list-units --type=service`
- nginx config for the affected hostname/upstream
- env / compose / systemd / deploy source for the target project

Reference: `references/multi-project-vps-boundary-registry.md`
- Additional rollout/stale-supervisor reference: `references/shared-vps-boundary-rollout-and-stale-supervisor-recovery.md`

### Mobile tunnel login pitfall: `Failed to fetch` even when CORS looks correct
Symptom pattern:
- Public frontend and backend tunnels both return `200` on health checks.
- CORS preflight (`OPTIONS`) also returns expected headers.
- Desktop/CLI requests can succeed, but mobile browser login still throws `Failed to fetch`.

Root cause class:
- Cross-origin tunnel-to-tunnel traffic is brittle on mobile networks/devices (DNS/proxy/intercept variance), even when backend CORS is configured correctly.
- Stale frontend state (cached `apiBase` pointing to old host/localhost) amplifies failures.

Preferred fix order:
1. **Eliminate cross-origin dependency** for public demos: serve frontend and proxy `/api/*` from the same origin.
2. Frontend default API base should be same-origin (`${window.location.origin}/api/v1`) in public/tunnel mode.
3. Add frontend session-healing for stale `apiBase` values (localhost/old tunnel host) and auto-migrate to same-origin default.
4. Keep cache-busting on entry script (`main.js?v=...`) during rapid tunnel debugging to force mobile clients off stale JS.
5. Verify with one real write endpoint through the frontend domain (e.g. `POST https://<frontend-domain>/api/v1/auth/login`), not only direct backend-domain checks.

If health is 200 but feature routes are 404 publicly, treat as wrong upstream/proxy mapping until proven otherwise.

Add a third check for route parity:
- test both a **read endpoint** and a **write endpoint** (`POST`) on public domain.
- do not accept `GET /health` alone as proof of correct routing.
- if health works but app endpoints 404, domain is likely pointing to a different app/proxy target.

HTTPS parity guardrail:
- run host-header check locally: `curl -H 'Host: <domain>' http://127.0.0.1/<route>`
- run direct app check: `curl http://127.0.0.1:<app_port>/<route>`
- if local host-header works but public HTTPS fails, inspect TLS vhost/cert for `<domain>` and issue cert (`certbot --nginx -d <domain>`) before deeper app debugging.

## TLS/vhost parity pitfall (new-domain cutovers)
A common false signal: HTTP host-header checks on `127.0.0.1` look correct, but public `https://domain/...` still serves a different app/404 page.

### Cert-first rollout pitfall (critical)
When onboarding a fresh domain, **do not** install an Nginx `listen 443 ssl` block that references `/etc/letsencrypt/live/<domain>/...` before the cert exists. `nginx -t` will fail with `cannot load certificate ... No such file or directory`, which blocks reload.

Safe sequence:
1. Install **HTTP-only** vhost (`listen 80`) proxying to app upstream.
2. `nginx -t && systemctl reload nginx`.
3. Run `certbot --nginx -d <domain> ...` to mint and inject TLS config.
4. Re-test `nginx -t`, reload, then verify public `https://<domain>` routes and API POST path.

Alternative for headless/origin-only (grey-cloud) setup:
1. Create HTTP-only vhost with `.well-known/acme-challenge/` location block: `location /.well-known/acme-challenge/ { root /var/www/<domain>; }`
2. `sudo mkdir -p /var/www/<domain>`
3. `certbot certonly --webroot -w /var/www/<domain> -d <domain>`
4. Then add `listen 443 ssl` block with the cert paths.
5. `nginx -t && reload`

This avoids the 80→443 redirect problem during cert provisioning.

Typical cause on multi-app VPS:
- new vhost exists for port 80 only, while port 443 is still handled by an older default TLS server block.
- Cloudflare/front proxy then shows responses that appear “mixed context” even though app/process is fine.

Required checks after enabling a new domain:
1. Verify local nginx host routing: `curl -H 'Host: <domain>' http://127.0.0.1/...`
2. Verify direct app port: `curl http://127.0.0.1:<app-port>/...`
3. Verify public HTTPS response headers/body fingerprint.
4. Ensure domain has its own TLS vhost/cert (e.g. `certbot --nginx -d <domain>`), not just HTTP proxy block.

Interpretation rule:
- If local host-header check is correct but public HTTPS is wrong, debug TLS server-block/certificate attachment first, before blaming app routes.

### HTTPS parity trap (new)
On multi-app hosts, HTTP (`:80`) can point to the right upstream while HTTPS (`:443`) silently serves a different app via default TLS vhost.
Always verify both layers explicitly:
1. `curl -H 'Host: <domain>' http://127.0.0.1/<fingerprint-route>` (HTTP host-routing)
2. `curl -k --resolve <domain>:443:<origin_ip> https://<domain>/<fingerprint-route>` (direct HTTPS on origin)
3. `curl https://<domain>/<fingerprint-route>` (public through CDN/proxy)

Interpretation:
- (1) OK, (2) wrong app => TLS vhost/cert/site block on origin is incomplete (common when only `listen 80` exists).
- (2) OK, (3) wrong app => CDN/proxy/edge rules are overriding origin mapping.

Operational fix pattern:
- Ensure dedicated `server_name <domain>` block exists for HTTPS on origin.
- Provision cert and bind to that same vhost (e.g., `certbot --nginx -d <domain>`).
- Re-run the 3-step parity checks before claiming routing is fixed.

### Public-vs-local split diagnosis (Cloudflare/proxy hosts)
When local `Host` header checks succeed but public domain still serves a different app:
1. Verify local Nginx vhost routing explicitly:
   - `curl -i -H 'Host: <domain>' http://127.0.0.1/<fingerprint-route>`
   - `curl -i http://127.0.0.1:<app-port>/<fingerprint-route>`
2. If both local checks return expected marker, treat origin app mapping as correct.
3. Then isolate edge-layer routing (Cloudflare/other CDN):
   - confirm DNS record exists for exact host
   - remember `Proxied` records return CDN IPs in `dig`; this is normal
   - inspect/disable conflicting Workers Routes, Origin Rules, Redirect/Transform rules, Load Balancer/Tunnel mappings
4. Use a temporary `DNS only` toggle for the host to prove whether CDN edge rules are the source of mismatch.
5. Keep a unique marker route in app during cutover; remove after parity is confirmed.

## No-sudo production fallback (Docker-based root operations)
When root-owned files (nginx config, system files) need editing but `sudo` requires interactive password:

### Technique: Docker volume-mount + nsenter
1. **Write config files to root-owned paths** via a temporary Alpine container with a volume mount:
   ```
   docker run --rm -v /etc/nginx/sites-available:/target alpine \
     sh -c 'cat > /target/<domain>.conf'
   ```
   — OR write to `/tmp/` first as user, then copy with `cp /tmp/<file> /target/<file>` inside the container.

2. **Reload services** via `nsenter` into PID 1's namespaces:
   ```
   docker run --rm --pid=host --privileged alpine \
     sh -c 'nsenter -t 1 -m -u -i -n -p -- sh -c "nginx -s reload && echo RELOADED"'
   ```
   This bypasses the need for sudo entirely because Docker runs as root and can access host PID/mount namespaces.

### Critical pitfalls (Docker-based operations)
- **Shell variable expansion in heredocs**: When writing nginx config (which contains `$host`, `$remote_addr`, `$proxy_add_x_forwarded_for`, etc.) through a Docker container shell, those variables get expanded to empty if the heredoc delimiter is not properly quoted. Even `<< 'EOF'` inside `sh -c "..."` won't protect them — the container's shell sees `$host` etc. as undefined shell variables and expands them to empty strings, silently corrupting the config.
  - **PROVEN FIX** (never fails): Write the file to `/tmp/` first using the host-side `write_file` tool (which preserves literal `$`), then copy into place via Docker:
    ```bash
    # Step 1: write to /tmp/ as user (no shell interpretation)
    write_file content="..." path="/tmp/<name>.conf"

    # Step 2: copy into target via Docker volume mount
    docker run --rm -v /tmp:/tmp -v /etc/nginx/sites-available:/target alpine \
      sh -c 'cp /tmp/<name>.conf /target/<domain>.conf'
    ```
  - Or use a Python/Tool script on the host that writes the file with proper escaping.
  - **NOK**: `echo '<config-with-$variables>' | docker run ... tee /target/file` — shell expansion WILL corrupt the content.
  - **NOK**: Heredoc inside `sh -c "..."` even with `<< 'EOF'` — the outer double quotes eat the single-quote delimiter protection.

- **Nginx proxy_pass IP gets rewritten**: If you see `172.17.0.1` in the written config instead of `127.0.0.1`, the shell inside the container mangled the content. Use the pre-write-to-/tmp/ approach to avoid this.
### Closing public ports without breaking services (critical)

When user asks to "close public port" for a stateful service (DB/queue/cache), do NOT default to stopping the container/service.
Preferred order:
1. Keep service running.
2. Restrict bind address from `0.0.0.0` to `127.0.0.1` (or private interface/VPN interface).
3. Verify both security and availability:
   - security check: `ss -ltnp` shows local-only bind
   - availability check: service health/app path still works
4. Only stop service if user explicitly asks to shut the service down.

#### Pre-scan: discover exposed services
Before touching anything, audit what's actually public:
```bash
# Services on *:PORT (accessible from internet)
ss -tlnp 2>/dev/null | grep "0.0.0.0:"

# Services on *:* (accessible from all interfaces)
ss -tlnp 2>/dev/null | grep ":\*\s\|:::"
```
For each `0.0.0.0` or `*:` entry, identify process owner (`ps -p <pid> -o pid,cmd`), check if it has an nginx or Cloudflare layer in front, and decide: should it be localhost-only?

Common false positives: `sshd` (must stay public), nginx (`:80/:443` must stay public). Everything else (Node apps, Docker containers not behind nginx, dev servers) should be localhost-only.

#### Express/Node.js `app.listen()` trap (not covered by `HOST` env)
Express apps default to `0.0.0.0` when calling `app.listen(PORT)` without a host argument:
```js
// BIND TO 0.0.0.0 (DEFAULT) — publicly exposed
app.listen(PORT, () => { ... });

// BIND TO LOOPBACK — safe
app.listen(PORT, '127.0.0.1', () => { ... });
```
Unlike Next.js (which respects `-H`, `HOST`, or `host` env), Express requires the host as a **second positional argument** to `listen()`. There's no env var to set.

**Scan technique**: after patching, verify the bind changed:
```bash
ss -tlnp 2>/dev/null | grep ":3005"
# Before: *:3005
# After:  127.0.0.1:3005
```

#### Restart after patching
**PM2**: `pm2 restart <app>` then `pm2 save`
**Systemd**: create unit if not exist, enable + start
**Bare Node** (no supervisor): migrate to systemd service for reboot survival — see `templates/express-systemd-unit.service`

For Node/Next.js stacks on multi-app VPS:
- Next.js systemd service: bind loopback explicitly with `next start -H 127.0.0.1 -p <port>`.
- **Critical runtime env parity:** if service is launched by systemd user unit, explicitly load app env with `EnvironmentFile=/path/to/.env` (or inline `Environment=` entries). Do not assume `.env` auto-load at runtime.
- PM2 Node app: set `HOST=127.0.0.1` in ecosystem env and restart with `pm2 restart ecosystem.config.js --only <app> --update-env`.
- Keep Hermes gateway online unless user explicitly authorizes gateway downtime.

Pitfall:
- Interpreting "close port" as "stop Docker" causes avoidable downtime and user frustration.
- On migration windows, public DB exposure can be temporary; prefer explicit temporary-access patterns (IP allowlist/tunnel) and then revert to private bind.

## Runtime env parity check (systemd/pm2)
A frequent false-positive: `npm run build` passes (because build loads `.env`) but production requests still 500 because runtime process lacks env vars (DB URL, auth keys, base URLs).

Required verification after restart:
1. Confirm service env source:
   - systemd user: unit includes `EnvironmentFile=/path/to/.env` (or explicit `Environment=`)
   - PM2: restart with `--update-env`
2. Confirm live process actually has vars (masked evidence only):
   - get PID (`systemctl --user show <svc> -p MainPID --value`)
   - inspect `/proc/<pid>/environ` and verify key presence (`DATABASE_URL`, auth vars), never print raw secrets.
3. Re-test public endpoint; expected unauth route should be 401 JSON, not 500.

Symptom signature when missing env in this class:
- intermittent/route-specific 500 despite successful build
- misleading auth/proxy errors that mask the actual missing runtime config.


## Organization rule
- Keep incident-specific fixes in `references/`.
- Keep copy-ready units/config snippets in `templates/`.
- Keep probes/checkers in `scripts/`.
- See `references/whatsapp-gateway-route-parity-check.md` for OpenAPI-vs-runtime drift handling and domain parity checks.
- See `references/https-vhost-cloudflare-parity.md` for HTTPS-vhost mismatch under Cloudflare proxy and certbot-based recovery.
- See `references/cloudflare-host-mismatch-checklist.md` for public-404/local-OK diagnosis on proxied CDN hosts.
- See `references/agentwa-domain-routing-and-port-isolation.md` for multi-app port ownership checks (AgentWA vs the gateway), systemd coexistence, and DB public-port closure without DB downtime.
- See `references/port-owner-and-db-exposure-recovery.md` for checking real process owner on shared ports, fixing wrong upstream targets, and closing DB public exposure without stopping the DB service.
- See `references/clerk-dev-browser-missing-localhost-proxy-loop.md` for diagnosing Next.js + Clerk 500s after localhost-only hardening (avoid false "service down" conclusions from localhost curl).
- See `references/clerk-live-recovery-after-localhost-hardening.md` for the production recovery sequence (`pk_live/sk_live`, proxy URLs, middleware matcher scoping, and 200/200 verification on `/` + `/sign-in`).
- See `references/next16-clerk-middleware-epotroxy-trap.md` for Next.js 16 + Clerk middleware/proxy rewrite traps that cause `x-middleware-rewrite: https://localhost:<port>/...` and EPROTO 500s.
- See `references/systemd-envfile-runtime-parity.md` for the build-pass/runtime-fail pattern when systemd user services do not load `.env`.
- See `references/postgres-ssh-tunnel-remote-port-discovery.md` for laptop tunnel setup when remote Postgres is not on default 5432 (e.g., 5433) and must be discovered before forwarding.
- See `references/static-frontend-cache-busting-and-same-origin-api-proxy.md` for stale-UI-after-deploy recovery (script cache-busting) and same-origin `/api` proxy pattern when frontend must reliably hit local backend.
- See `references/tanstack-start-vps-serving-pattern.md` for handling TanStack Start `vite preview`/build-entry mismatches and converting ad-hoc static serving into persistent user systemd service.
- See `references/vps-runtime-recovery-matrix.md` for shared-VPS recovery across systemd/PM2/Docker/nginx, including compose revival with pre-existing DB containers and rebuilding a missing gateway container onto an existing compose network.
- See `references/docker-static-bind-mount-403-and-missing-compose-source.md` for recovering static `nginx:alpine` web containers that return 403 because the bind-mounted `web/dist` content is missing, unreadable, or desynced from the surviving container.
- See `references/static-frontend-breadcrumb-recovery.md` for the follow-up case where service is restored with a placeholder page but the original frontend source/build may be gone; covers how to prove prior existence from deploy/session breadcrumbs vs when to declare exact restore impossible.
- See `references/vps-stability-hardening.md` for swap/memory tuning, Docker memory limits, watchdog auto-restart, and weekly cleanup — the full stability playbook for multi-service VPS with 2-4GB RAM.
- See `references/vps-disk-management.md` for disk cleanup reference — what's safe to delete vs what to keep, with typical sizes and exact commands.
- See `references/npm-symlink-recovery-after-cleanup.md` for recovering npm after aggressive `find ... -name node_modules -exec rm -rf` wipes the global `.hermes/node/lib/node_modules/` tree (symptom: broken symlinks in `.local/bin/npm`). Includes safe cleanup patterns and prevention.
- See `references/docker-proxy-ghost-port-cleanup.md` for diagnosing and recovering from docker-proxy processes that survive container removal and block host ports.
- See `references/agentwa-clerk-invalid-host-and-orphaned-process.md` for the "Invalid Host header. Bridge accepts loopback hosts only" recovery pattern — the error appeared to be Clerk but was actually a PM2-orphan Express process holding port 3000. Includes `fuser -k <port>` as the fix and `chattr +i` to lock nginx config from being overwritten by deploy scripts.
- See `references/agentwa-billing-pakasir-integration.md` for Pakasir billing integration: valid payment methods (qris only), direct API vs SDK usage, credits pricing consistency rule (1.000 reply = Rp25.000 everywhere), and the deploy-script nginx config overwrite trap (use `chattr +i` to lock).
- See `references/docker-rust-nginx-deployment-pattern.md` for deploying a Docker Compose stack (Rust gateway + Python ML worker + Postgres + static UI) behind nginx with SSL, covering port isolation, nginx proxy_pass URI semantics, axum root-route fix for `/api/v1`, and sudo workaround via Python subprocess.
- See  for silent ML model failure in security gateways: fail-open timeout + exception swallowing + hardcoded health = zero-alert full bypass.
- See  for the auth-disabled-by-default pattern used by the security gateway's Gateway (Rust) and ML Service (Python FastAPI): `Authorization: Bearer <key>` with env-var keys, per-key rate limiting done, and localhost/internal trust for same-VPS services.
