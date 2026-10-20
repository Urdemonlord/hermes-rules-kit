# Port Owner + DB Exposure Recovery (multi-app VPS)

Use when domain is up but serving wrong app, or when DB public port must be closed without downtime intent.

## A) Confirm who owns app port
1. Check listener
   `ss -ltnp | grep :<APP_PORT>`
2. Extract PID owner
   `ps -fp <PID>`
3. Verify process cwd and command
   `readlink -f /proc/<PID>/cwd`
   `tr '\0' ' ' < /proc/<PID>/cmdline`

Decision:
- If PID/cwd points to wrong project/service, disable that service first, then start intended app service.

## B) Fix Nginx upstream mismatch (502)
1. Check configured upstream in vhost:
   `grep -n 'proxy_pass' /etc/nginx/sites-enabled/<domain>`
2. Validate target app locally:
   `curl -i http://127.0.0.1:<actual_app_port>/api/health`
3. Update `proxy_pass` to actual app port, then:
   `nginx -t && systemctl reload nginx`
4. Verify both:
   - origin direct with host resolve
   - public domain through CDN/proxy

## C) Close public Postgres exposure WITHOUT stopping DB container
If container maps `0.0.0.0:5433->5432` and you need private-only access:
1. Capture existing container config (`docker inspect <name>`)
2. Recreate with loopback bind:
   `docker rm -f <name>`
   `docker run -d --name <name> ... -p 127.0.0.1:5433:5432 ...`
3. Verify:
   `ss -ltnp | grep 5433` should show `127.0.0.1:5433`

Notes:
- Publishing port on `0.0.0.0` is exposure; binding to `127.0.0.1` keeps service reachable locally by apps on same host.
- For migration from laptop, open temporary path via SSH tunnel/VPN or short maintenance window + strict source allowlist.
