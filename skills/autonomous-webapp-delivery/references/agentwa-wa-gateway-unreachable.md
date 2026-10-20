# AgentWA: WA Gateway Missing / `gateway_unreachable` Diagnosis

## Root Cause
`WHATSAPP_GATEWAY_URL=http://127.0.0.1:3100` in `.env` points to a service that is NOT a WhatsApp gateway.
Port 3100 on the AgentWA VPS runs **platform-suite-backend** (confirmed via `docker ps` and `curl` health).
No baileys-based WhatsApp gateway service is deployed on this server.

## How to Diagnose
```bash
# 1. Check what's actually running on the configured gateway port
curl -s http://127.0.0.1:3100/
# platform-suite-backend responds with "platform-suite Backend API is online"

# 2. Check Docker containers for WA-related services
docker ps --format "{{.Names}}\t{{.Image}}\t{{.Ports}}" | grep -i wa

# 3. Check env
grep WHATSAPP ~/agentwa/web/.env
```

## The Problem
The `whatsappGateway.ts` calls (createSession, getSessionQr, getSessionStatus, sendMessage) all fail silently with 400/error when the gateway doesn't recognize the route.

## The Fix Applied
1. **API routes** — catch fetch network errors and return `gateway_unreachable` (503) with a clear message instead of opaque 400.
2. **WA hook** — added `waError` state; set it when API returns `gateway_unreachable` error code.
3. **Overview panel** — show a red notice banner when `waError === 'gateway_unreachable'`.
4. **Graceful degradation** — Init QR, Status, Test Send buttons remain enabled but show the error state inline.

## Error Detection Pattern
```typescript
function isGatewayError(error: unknown): boolean {
  if (error instanceof TypeError && error.message.includes('fetch')) return true;
  if (error instanceof Error && (
    error.message.includes('ECONNREFUSED') ||
    error.message.includes('ENOTFOUND') ||
    error.message.includes('NetworkError') ||
    error.message.includes('Failed to fetch')
  )) return true;
  return false;
}
```

## Files Changed
- `src/app/api/agents/[id]/wa/qr/route.ts` — added `isGatewayError` + 503 response
- `src/app/api/agents/[id]/wa/session/init/route.ts` — same
- `src/app/api/agents/[id]/wa/status/route.ts` — same
- `src/app/api/agents/[id]/wa/test-send/route.ts` — same
- `src/app/dashboard/_hooks/use-dashboard-wa.ts` — added `waError` state + `setWaError` on failure
- `src/app/dashboard/_hooks/use-dashboard-workspace.ts` — exposed `waError`
- `src/app/dashboard/_components/overview-panel.tsx` — show warning banner when `waError === 'gateway_unreachable'`

## To Actually Fix (not just detect)
Deploy a baileys-based WhatsApp gateway service. Options:
1. **Self-hosted baileys gateway** — run as separate Docker container, separate from platform-suite-backend
2. **Use a hosted WA gateway API** (e.g., Waha, Chat-API, WonderPush) and update `WHATSAPP_GATEWAY_URL` + `WHATSAPP_GATEWAY_API_KEY` env vars
3. **Build and deploy the missing gateway** from existing codebase (check if `~/agentwa/web/src/lib/whatsappGateway.ts` consumer-side matches any gateway service in the monorepo)

Until then: UI shows `gateway_unreachable` notice instead of silent failure.
