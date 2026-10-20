# Manual container → Compose adoption checklist

Use when a live DB/service container already exists and you want repo-managed reproducibility without moving data.

## Checklist
- Inspect live container: image, ports, restart policy, env keys, mounts.
- Distinguish:
  - data persistence = existing named volume is correct
  - runtime persistence = restart policy / recreate path is correct
- Prefer adopting the existing named volume as `external: true`.
- Keep secrets in a git-ignored local env file plus a checked-in `.example`.
- If the compose file needs top-level interpolation (e.g. external volume name), pass vars via `docker compose --env-file ...` or a wrapper script. Service `env_file:` is too late for compose-file parsing.
- Recreate from compose only after confirming host-port ownership and no sibling conflict.
- Verify after cutover:
  - container health = `healthy`
  - DB query still works from the app repo/runtime path
  - app health endpoint still returns `200`

## Common trap
A successful one-off DB query does not prove the runtime is durable. You still need a restart-safe owner chain and a documented recreate path.
