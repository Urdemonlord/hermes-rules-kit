# MeowAttend-v2 full backend-connected delivery smoke (no placeholder/local metadata)

## Context
User requested: frontend must be fully connected to real backend, no local placeholder/metadata, siap demo/prod-like flow.

## Durable implementation pattern
1. Remove frontend local metadata flow (e.g., `localStorage` members) and switch all CRUD to backend endpoints.
2. Add missing backend endpoints before wiring UI:
   - Members: list/create/delete
   - Reports: filtered records + CSV/PDF export
3. Keep frontend API calls same-origin (`/api/v1`) for tunnel/mobile safety.
4. If host lacks native Go (`go: not found`), run backend verification with Docker:
   - `docker run --rm -v <backend>:/app -w /app golang:1.22 go test ./...`
5. After backend changes, restart runtime service/container and probe health.
6. Run end-to-end smoke with authoritative checks:
   - login 200 + token
   - members GET/POST/DELETE 2xx
   - create session + checkin 2xx
   - records filtered 200
   - export CSV 200 with `text/csv`
   - export PDF 200 with `application/pdf` and `%PDF-1.4` signature

## Tunnel/public validation pattern
- Public tunnel links are ephemeral; verify both page and API before handoff:
  - `/app.html` status 200
  - `/landing.html` status 200
  - `/api/v1/auth/login` returns expected status/body shape
- If old tunnel returns 503, rotate tunnel immediately and re-share only verified fresh URL.

## Pitfalls observed
- String escaping in custom PDF generator can break Go compile; inspect exact failing lines and patch escapes explicitly.
- Hermes file/patch tools may resolve stale path after workspace rename/migration; use absolute-path `execute_code` rewrite/read as recovery path.

## Handoff evidence format (ringkas)
- Mention exact flows proven (members/session/checkin/reports/export)
- Mention test command used (Docker Go fallback)
- Mention live URL currently verified and caveat that tunnel is temporary
