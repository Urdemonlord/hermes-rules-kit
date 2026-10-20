# OpenCode model availability vs UI toggle (runtime verification)

When user sees model toggles enabled in OpenCode workspace UI, runtime can still fail.

## Key finding
Enabled toggle != guaranteed usable model at API runtime.

## Fast verification pattern
1. Load `.env` in shell/runtime context.
2. Send a minimal chat completion request per candidate model.
3. Record only non-sensitive diagnostics:
   - model name
   - HTTP status
   - `error.type`
   - `hasAnswer` boolean
4. Decide routing/fallback based on real results, not dashboard toggle state.

## Interpreting common outcomes
- `429 FreeUsageLimitError`: model is reachable but free-tier quota window is exhausted.
- `401 CreditsError`: account/workspace credit/payment requirement blocks inference.
- `401 ModelError` + "not supported": model ID not available on that endpoint/workspace.

## Practical implication for AgentWA
If multiple free models return `429` and paid models return `401 CreditsError`, fallback-heavy replies are expected even with correct API key rotation. Prioritize provider access/quotas or broaden fallback to currently reachable models.
