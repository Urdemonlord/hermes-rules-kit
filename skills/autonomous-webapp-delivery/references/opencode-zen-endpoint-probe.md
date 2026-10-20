# OpenCode Zen endpoint probe for Qwen3.6 Plus

## Why this exists
When WA RAG output degrades and provider config is uncertain, resolve endpoint/auth ambiguity from upstream docs/source first, then verify with a live call before asking user for more input.

## Verified discovery path
1. Clone upstream OpenCode repo and inspect docs content (not only rendered site):
   - `packages/web/src/content/docs/zen.mdx`
2. Confirm endpoint row for Qwen model:
   - Model: `qwen3.6-plus`
   - Endpoint: `https://opencode.ai/zen/v1/chat/completions`
   - Auth: `Authorization: Bearer <OPENCODE_API_KEY>`
3. Apply env + restart runtime (`pm2 restart ... --update-env`).
4. Run live probe to classify failure type.

## Interpreting probe results
- `401` with cookie/auth header wording (eg "No cookie auth credentials found", "Missing Authentication header"):
  - Usually wrong endpoint family or wrong auth header usage.
- `401` with `CreditsError` + message about payment method:
  - Endpoint and auth are accepted; account billing/credits are missing.
- `404`/route not found:
  - Wrong path.

## Session-specific evidence snapshot
Live probe after setting endpoint to `/zen/v1/chat/completions` returned:
- HTTP `401`
- Body: `CreditsError` with billing/payment method message

Conclusion: config path/auth is correct; remaining blocker is account billing, not endpoint discovery.
