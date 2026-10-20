# TanStack Start on VPS: preview mismatch vs production serving

## Symptom pattern
- `npm run build` succeeds.
- `npm run preview -- --strictPort ...` fails with module-resolution errors, e.g. plugin tries to import:
  - `dist/server/server.js`
- Actual build output contains:
  - `dist/server/index.js`

## Operational rule
Do not infer production outage from `vite preview` failure alone.

Validate in this order:
1. **Current listener ownership**
   - confirm which process owns the app port (`ss -ltnp`).
2. **Local app checks**
   - test loopback endpoint(s) on bound port.
3. **Public route checks**
   - test root + key pages/routes through domain (not health only).
4. **Decide serve mode explicitly**
   - SSR runtime: run the actual built server entrypoint produced by this build.
   - Static runtime: serve `dist/client` behind reverse proxy.
5. **Persist with user systemd service**
   - avoid ad-hoc shell sessions for production continuity.

## Known-good static fallback used in session
- Service command:
  - `/usr/bin/python3 -m http.server 4173 --bind 127.0.0.1 --directory /home/user/meowattend-v2/frontend-vite/dist/client`
- Security posture:
  - bind loopback (`127.0.0.1`) and expose publicly only via Nginx reverse proxy.

## Verification checklist
- `systemctl --user is-enabled <service>` => `enabled`
- `systemctl --user is-active <service>` => `active`
- listener shows loopback bind on target port
- public domain returns expected status on:
  - `/`
  - `/landing.html`
  - `/app.html`
  - `/scan-qr` (or equivalent app-critical route)

## Notes
- `exit 143` on background preview/http-server process usually indicates termination signal, not app logic failure.
- `tcsetattr: Inappropriate ioctl for device` in non-interactive shells is often incidental noise during process teardown.