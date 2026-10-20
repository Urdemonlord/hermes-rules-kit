# SaaS Billing + Quota Rollout (AgentWA)

## Context
When transitioning from single-tenant-ish app logic to SaaS plans, quota enforcement must happen in the runtime path that actually sends outbound messages (not only in dashboard/API display).

## Implemented pattern
1. Add billing schema first:
   - `plan_limits`
   - `subscriptions`
   - `usage_counters_daily`
   - `usage_counters_monthly`
   - `billing_events`
2. Seed `plan_limits` for free/starter/growth/pro.
3. Add helper library (`src/lib/billing.ts`) that:
   - resolves `owner_user_id` from `agents`
   - resolves active subscription (`trial|active|grace`) with `free` fallback
   - loads plan limits (`monthly_ai_replies`, `burst_per_minute`)
   - checks monthly usage and burst usage
   - increments daily/monthly usage counters
4. Enforce quota inside WhatsApp webhook outbound loop before sending reply.
5. If blocked, write outbound message log with status `blocked_quota` (for operator traceability), skip send.
6. Only increment usage counters **after** successful outbound send.
7. Add owner-guarded usage endpoint for operator visibility:
   - `GET /api/agents/[id]/billing/usage`
   - returns plan + monthly/burst used/remaining + canSendNow + blockedReason.
8. Add observability endpoint for billing telemetry:
   - `GET /api/agents/[id]/billing/observability`
   - returns `dailyUsage` (last 14 days) + recent `billing_events`.
9. Log billing events from webhook runtime:
   - `quota.blocked` when outbound send is blocked by limit
   - `quota.reply_sent` after successful send + counter increment
10. For burst limiter, count only outbound rows with `status='sent'` to avoid false throttling from `blocked_quota` logs.
11. Keep billing observability UI in its own dashboard section (separate from "Test Send") so operators can read quota state without scrolling through messaging controls.
12. Add compact daily usage bars (14 days) + latest event list in dashboard for quick operator triage (`quota.blocked` vs `quota.reply_sent`).

## Why this matters
- Prevents quota bypass through direct webhook traffic.
- Keeps billing usage aligned to actual delivered replies.
- Preserves forensic visibility for blocked sends.

## Verification checklist
- `npm run build`
- restart process manager (`pm2 restart ... --update-env`)
- verify app online
- DB sanity:
  - plan rows seeded
  - usage rows upsert on successful replies
  - blocked sends logged as `blocked_quota`

## Pitfalls
- Counting usage before send causes overbilling on gateway failures.
- Enforcing quota only in dashboard/API route is insufficient; webhook path can still send.
- Missing owner resolution (`owner_user_id`) breaks per-tenant accounting.
