# Debugging Closeout Example

## Summary
Changed the request validation path so invalid payloads are rejected at the boundary instead of failing deeper in the service layer.

## Files touched
- `src/api/handler.ts`
- `src/validation/request.ts`
- `tests/api/handler.test.ts`

## Verification evidence
- Reproduction before fix: `pnpm test tests/api/handler.test.ts -t rejects_invalid_payload` -> FAIL
- Reproduction after fix: same command -> PASS
- Broader check: `pnpm test tests/api/handler.test.ts` -> PASS

## Risks and unverified items
- Full integration suite not run
- Browser/UI surface not applicable
