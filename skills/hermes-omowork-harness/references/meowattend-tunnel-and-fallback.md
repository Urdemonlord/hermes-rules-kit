# MeowAttend Tunnel + Fallback Reliability Notes

Use this when doing rapid demo delivery with OmO harness and external tunnel exposure.

## 1) Localhost.run URL can rotate during one long SSH session

Observed behavior:
- A previously working URL can later return `503`.
- The same running SSH tunnel process may emit a newer `*.lhr.life` URL in logs.

Operational rule:
1. Do **not** assume first URL remains valid.
2. Re-read process logs and extract latest tunnel domain.
3. Smoke test latest URL before sharing.

Minimal checks:
- `process poll` for running state.
- `process log` to collect newest emitted domain.
- `curl -w "%{http_code}" https://<domain>/` expecting `200`.

## 2) Tunnel smoke must include key pages, not only root

For frontend revamp tasks, verify all public pages:
- `/`
- `/scan.html`
- `/dashboard.html`

Acceptance:
- HTTP `200` for each page.
- Response body contains expected page markers (brand/title text).

## 3) Pi/free model failure handling under OmO constraints

Observed failure classes:
- timeout (`exit 124`)
- provider quota/rate-limit (`429 free-models-per-day`)

Required behavior:
1. Run at least one concrete `pi` step when user explicitly requests OmO + pi.
2. If `pi` fails, report exact failure reason and evidence.
3. Ask/confirm fallback path (manual patch lane or paid model lane).
4. After approval, proceed immediately and keep verification evidence strict.

## 4) Verification bundle for “ship tonight” runs

Minimum evidence to close mission:
- Backend tests pass (`npm test`).
- Build pass (`npm run build`).
- API smoke pass (health + create session + token + checkin + summary).
- Tunnel smoke pass on active public URL for all key pages.

Do not claim completion if any item above is missing.
