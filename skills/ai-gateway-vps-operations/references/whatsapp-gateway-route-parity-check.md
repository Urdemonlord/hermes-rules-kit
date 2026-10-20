# WhatsApp gateway route-parity check (VenusConnect fork)

Use this when integrating app wrappers with `/home/user/whatsapp-api`-style gateways.

## Why
In this incident, `/openapi.json` advertised routes like:
- `POST /api/session`
- `GET /api/session/{id}`

But live server routes were:
- `POST /api/session/create`
- `GET /api/session/:sessionId/status`
- `GET /api/session/:sessionId/qr`
- `POST /api/session/:sessionId/send`

Root cause: docs/spec drift from runtime route registration.

## Fast verification sequence
1. Check process + script path:
   - `pm2 describe whatsapp-api`
2. Inspect live runtime source (built dist):
   - `dist/routes/sessionRoutes.js`
   - confirm actual registered paths.
3. Probe real endpoints with expected auth header:
   - `curl -H 'x-api-key: ...' http://127.0.0.1:3000/api/session/create`
   - `curl -H 'x-api-key: ...' http://127.0.0.1:3000/api/session/<id>/status`
4. Only after local success, test public domain parity (same method/path).

## Domain routing pitfall
`GET /api/health` returning OK is insufficient proof. Also test a write route (`POST`) on the same domain. If health succeeds but app API routes return framework 404 pages, domain is likely mapped to another app/proxy target.
