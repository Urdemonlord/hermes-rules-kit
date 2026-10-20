# Docker static bind-mount 403 + missing compose source recovery

Use this when a public domain proxies to an `nginx:alpine` static container and `/` returns `403 Forbidden` after reboot, cleanup, or partial source loss.

## Symptom pattern
- Public domain returns `403` on `/`
- Local upstream port also returns `403`
- `docker logs <container>` shows:
  - `directory index of "/usr/share/nginx/html/" is forbidden`
- `docker inspect <container>` shows a bind mount like:
  - `/home/user/<project>/web/dist -> /usr/share/nginx/html`
- Inside the container, `/usr/share/nginx/html` is empty or missing `index.html`

## Proven diagnosis steps
1. Confirm public vs local parity:
   - `curl -I https://<domain>/`
   - `curl -I http://127.0.0.1:<upstream-port>/`
2. Inspect container logs for directory-index errors.
3. Inspect container config and mounts:
   - `docker inspect -f '{{.Config.Image}} {{json .Mounts}}' <container>`
4. Check the host bind-mount source path actually exists and contains static assets.
5. If the source exists but container still sees empty content, inspect file/dir perms and then recreate the container.

## Recovery pattern
### Case A — source folder exists but content is gone
- Recreate minimal `index.html` or restore real built assets into the bind-mounted host path.
- Fix permissions so container can traverse/read:
  - parent dirs `755`
  - files `644`

### Case B — old compose labels exist but compose source on disk is missing/incomplete
- Do not tear down healthy sibling containers immediately.
- Read compose labels from surviving containers to recover:
  - compose project name
  - previous working dir
  - service role
- Re-clone the repo to a fresh path if needed.
- Rebuild only the missing app image/container.
- Reattach or recreate against the existing compose/docker network.

### Case C — bind source was created after container start and container still sees empty dir
- Recreate the static container explicitly.
- Example pattern:
  - remove stale static container
  - `docker run -d --name <name> --restart unless-stopped --network <net> -p 127.0.0.1:<host-port>:80 -v <host-dist>:/usr/share/nginx/html:ro nginx:alpine`

## Verification
- Inside container:
  - `ls -la /usr/share/nginx/html`
  - `head /usr/share/nginx/html/index.html`
- Local upstream:
  - `curl -I http://127.0.0.1:<port>/` should become `200`
- Public domain:
  - `curl -I https://<domain>/` should become `200`
- Re-check any separate API/health path behind the same domain after container recreation.

## Notes
- A healthy API gateway can coexist with a broken static web root. Verify both independently.
- `403` from static nginx in this pattern is usually missing content, not an auth rule.
- If the quick fix is a placeholder landing page, state clearly that service is restored but the original frontend may still need to be rebuilt/restored.