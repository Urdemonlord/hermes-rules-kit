# VPS Runtime Recovery Matrix

Use this when a user asks to "nyalakan semua service" or when one public domain is down after a VPS reboot and the host runs multiple supervisors.

## Fast audit order
1. `systemctl --user list-units --type=service --all --no-pager`
2. `pm2 list`
3. `docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'`
4. Inspect nginx upstream targets for the affected domains.
5. Verify direct local listeners before public curl.

Reason: on shared VPS, the missing app may live under a different runtime than the last app you touched.

## Recovery pattern: nginx upstream is dead
Symptom:
- public host returns `502` / provider Host Error
- nginx config points to `127.0.0.1:<port>`
- nothing is listening on that port

Checklist:
1. Read nginx site and note the expected host port.
2. Find the matching project compose/unit/PM2 definition.
3. Confirm whether frontend and backend ports drifted apart after redeploy.
4. Start the missing runtime.
5. Re-test:
   - `curl http://127.0.0.1:<port>`
   - `curl -I https://<domain>`
   - if applicable, `curl -L https://<domain> | head`

## Compose revival with surviving DB container
Common failure on older VPS app stacks:
- database container still healthy
- app containers missing
- `docker-compose up` fails because container name already exists or because compose created a fresh network not attached to the old DB container

Safer recovery:
1. Keep the existing DB container running.
2. Check its current network:
   - `docker inspect -f 'name={{.Name}} networks={{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' <db_container>`
3. If compose created a new network, attach the old DB container to it with the service alias expected by the app, e.g.:
   - `docker network connect --alias postgres <compose_network> <db_container>`
4. Start only the missing app services:
   - `docker-compose up -d --no-deps backend frontend`
5. Verify both app ports and container logs.

This avoids unnecessary DB recreation and preserves existing volume state.

## Host-port intent check for app-control panels
For dashboard-style apps behind nginx:
- preserve the legacy host port used by nginx for the public UI
- move the backend/API to a different host port if needed
- do not reuse the public UI port for the backend just because the compose file says `3000:3000`

Validation pattern:
- local frontend port should return HTML or expected redirect
- local backend port should return health text / JSON API marker
- public domain should align with the frontend port, not merely any healthy port

## Partial compose-source loss with surviving sibling containers
Symptom:
- running containers have compose labels pointing to a project working dir
- expected compose file/repo is missing or incomplete on disk
- one sibling (e.g. ML service) is healthy, but gateway container is gone

Recovery pattern:
1. Clone the repo again into a clean directory.
2. Build only the missing image.
3. Reuse the existing network/sibling containers instead of tearing them down.
4. Run the missing container manually with:
   - the same network as surviving siblings
   - the expected port mapping
   - `--restart unless-stopped`
5. Verify local health and then the public domain.

Example class:
- `security-gateway-ml-service` survived
- `security-gateway-gateway` missing
- nginx `/health` and `/v1` still proxy to `127.0.0.1:8080`
- fix: build gateway image from re-cloned repo and run gateway attached to `security-gateway_default`

## Done criteria
Do not stop at "container is up". Recovery is only complete when all three are true:
1. process/container/unit is running
2. local direct port returns expected service marker
3. public domain returns expected status/body family (`200` or intentional redirect)
