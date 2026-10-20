# Systemd EnvironmentFile Runtime Parity (Next.js/Node)

## Scenario
Public endpoint intermittently returns 500 while:
- `npm run build` succeeds
- service appears `active`
- errors may mention unrelated auth/proxy noise

## Root cause pattern
User-level `systemd` service starts app without loading `.env`, so runtime misses critical vars (`DATABASE_URL`, auth keys, base URLs).
Build success is misleading because build step reads `.env`, but runtime process does not.

## Fast diagnosis
1. Confirm service config:
   - `systemctl --user cat <service>`
   - check for `EnvironmentFile=/path/to/.env` or explicit `Environment=` entries
2. Confirm runtime env on live PID:
   - `systemctl --user show <service> -p MainPID --value`
   - inspect `/proc/<pid>/environ` for key presence (mask secret values)
3. Probe public API:
   - unauth endpoints should return `401` JSON, not `500`

## Fix
In unit file:
- keep existing `Environment=HOME=...`
- add `EnvironmentFile=/path/to/.env`

Then:
- `systemctl --user daemon-reload`
- `systemctl --user restart <service>`
- verify PID env + public probes

## Verification checklist
- service: `active`
- runtime env contains `DATABASE_URL` + auth vars
- `GET /` returns 200
- protected API unauth returns 401 JSON (not 500)

## Notes
- If user reports "looks like DB disconnected", check runtime env parity before deeper DB surgery.
- Never print raw secrets in output; only masked/boolean presence evidence.
