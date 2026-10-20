# Verification Gates Patterns

Use this reference when users provide mandatory quality gates before pushing code.

## Pattern: Explicit Gate Contract
If user states a fixed command list (example from real workflow):
1. `npm run test:unit`
2. `npm run build`
3. `npm run test:golden`
4. `npm run test:golden:gate`

Then:
- Run exactly in that order.
- Treat any failure as a hard stop for commit/push.
- After all pass, complete `git add`, `git commit`, and `git push` in the same cycle.

## Reporting Format
Keep concise:
- Gate results: each command + PASS/FAIL
- Shipping status: commit hash + branch + push target

## Common Non-Blocking Warnings
If command exits 0, warnings can be documented as non-blocking (example: Vite close timeout warning), but do not label as failed unless exit code is non-zero.
