# MeowAttend-v2: Placeholder Removal + Backend Sync + Workspace Isolation

## Why this matters
When users report "masih placeholder/demo" or "data workspace harus beda", visual cleanup alone is insufficient. Must prove runtime data isolation and real backend sync.

## Durable implementation pattern
1. Replace hardcoded auth placeholders/demo creds in frontend login UI with neutral Indonesian labels.
2. Remove mock/localStorage-first API logic for core auth/member/session paths.
3. Route frontend API calls via same-origin (`/api/v1/...`) and proxy upstream to backend service.
4. Bump cache-buster on served HTML/JS so users get the patched bundle immediately.

## Verification protocol (minimum)
1. **Bundle marker check**
   - Verify public HTML references new JS version token (e.g., `?v=20260524b`).
2. **Real login check**
   - Perform browser login against backend API path (not mock route), confirm dashboard state updates.
3. **Workspace isolation check**
   - Create/register a second tenant/workspace.
   - Query same endpoint for old vs new tenant (example: active session/events).
   - Evidence should show different results when underlying tenant data differs.
4. **Git completion**
   - Commit and push the exact frontend files changed for placeholder removal and API sync.

## Evidence shape to report
- Commit SHA
- Public asset version marker present
- Login success path confirmed
- Endpoint comparison across 2 tenant slugs (e.g., new=0, old=1)

## Pitfalls
- Declaring success after only static smoke (`curl /app.html`) without API proof.
- Forgetting cache-bust update; user still sees old placeholder UI.
- Validating tenant isolation with global/non-tenant endpoint by mistake.
