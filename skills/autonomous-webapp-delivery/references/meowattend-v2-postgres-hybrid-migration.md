# MeowAttend-v2 Postgres Hybrid Migration Notes

## Context
- Repo: `/home/user/meowattend-v2`
- Host has no native `go` binary (`go: not found` on host).
- Reliable verification path: Dockerized Go toolchain + absolute-path file ops via `execute_code`.

## What worked reliably
1. Build/test with pinned container:
   - `docker run --rm -v /home/user/meowattend-v2/backend-go:/app -w /app golang:1.22 go build ./...`
   - `docker run --rm -v /home/user/meowattend-v2/backend-go:/app -w /app golang:1.22 go test ./...`
2. Runtime smoke in DB mode:
   - Bring up Postgres container.
   - Start API with `DATABASE_URL`.
   - Probe `/health/ready` until 200.
   - Verify flow with real handler contract:
     - login payload keys: `tenant_slug`, `identifier`, `password`
     - create event payload keys: `name`, `starts_at`, `ends_at`
     - checkin payload key: `event_id` (not `qr_value` in this codebase)

## Pitfalls observed
- Tool path drift can still target stale `/home/user/meowattend` even when active repo is `.../meowattend-v2`.
  - Recovery: use `execute_code` + absolute paths for all read/write/patch/verify.
- `docker run ... golang:1.22 sh -lc 'go run ...'` produced `sh: 1: go: not found` in this environment.
  - Recovery: invoke `go` directly as container command (avoid `sh -lc` wrapper).
- Contract mismatch during smoke tests can look like auth or data bugs.
  - Example: using `email/password` for login returned `UNAUTHORIZED` because handler expects `identifier/password/tenant_slug`.
  - Example: records endpoint returns `data.items`, not `data.records`.

## Verification gate added in practice
- Before runtime smoke, inspect handler request/response shapes from source and align curl payload/JSON path to actual contract.
- For each migrated endpoint slice: run `go test` + DB runtime smoke + document proof in launch checklist/docs.
