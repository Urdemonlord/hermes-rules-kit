# OpenCode API key rotation under PM2 (runtime env parity)

## Symptom
- `.env` already contains new `OPENCODE_API_KEY`, but provider behavior looks like old account/workspace.
- OpenCode usage page for new account shows zero usage, while app still gets old-account errors.

## Root cause pattern
- PM2 process still holds old environment values in `pm2_env`.
- `pm2 restart --update-env` can still reuse stale shell env if `.env` is not exported in the same command context.

## Reliable fix sequence
1. Load `.env` into current shell:
   - `set -a; source /home/user/agentwa/web/.env; set +a`
2. Restart with updated env:
   - `pm2 restart agentwa-web --update-env`
3. Verify runtime key matches file key (masked only):
   - compare key prefix + short sha256 hash from:
     - PM2 runtime: `pm2 jlist` -> `pm2_env.OPENCODE_API_KEY`
     - `.env` line: `OPENCODE_API_KEY=...`
   - pass condition: `same=true`

## Interpretation rule
- If runtime/file fingerprints match but provider returns `429 FreeUsageLimitError` or `401 CreditsError`, key rotation worked; issue is provider rate/billing policy, not stale env.

## Safety
- Never print full key in logs/chat.
- Use masked prefix + short hash only.
