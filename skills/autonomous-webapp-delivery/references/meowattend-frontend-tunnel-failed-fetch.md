# MeowAttend frontend tunnel `Failed to fetch` diagnosis

## Symptom
- UI loads from public tunnel URL.
- Login/API action shows: `Login gagal: Failed to fetch`.

## Root cause
Frontend API base was hardcoded to localhost (`http://127.0.0.1:8080/api/v1`).
When opened on a mobile device through tunnel domain, requests target the phone localhost, not VPS backend.

## Fast verification
1. Open DevTools/network (or inspect frontend state/settings).
2. Check request URL for login call.
3. If host is `127.0.0.1` while page host is tunnel/public domain, mismatch confirmed.

## Fix pattern
- Prefer runtime API base selection:
  - If app is served from same origin/proxy path, default to `${window.location.origin}/api/v1`.
  - Else provide explicit Settings field for API base and persist value.
- Support one-click tunnel override via query param and keep naming consistent everywhere:
  - Parser key in code and distributed URL must match exactly (e.g., both `apiBase`).
  - Mismatch (`?api=...` while code reads `apiBase`) silently falls back and reproduces `Failed to fetch`.
- For quick user handoff, share encoded deep-link:
  - `.../app.html?apiBase=https%3A%2F%2F<backend-tunnel>%2Fapi%2Fv1`
- If mobile still fails after code patch, add cache-buster to module entry (`main.js?v=<stamp>`) and ask hard refresh/incognito.
- Add stale-session self-heal: when app host is public (not localhost) and persisted `apiBase` still points to `localhost/127.0.0.1`, automatically replace it with the public-safe default and persist.
- Add inline recovery on login view: show `API Base aktif` + editable API Base field directly on login page (not only in Settings), so users can recover without navigating away.
- Keep manual override for VPS direct mode.
- After fix, re-test login from phone over tunnel.

## Acceptance checks
- Public URL reachable (`200`).
- Login request URL points to reachable backend host (not device localhost).
- Login succeeds with demo credential and returns token.
