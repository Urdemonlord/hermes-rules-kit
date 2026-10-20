# Debugging Closeout Example

## Summary
Changed the request validation path so invalid payloads are rejected at the boundary instead of failing deeper in the service layer.

## changed
- `src/api/handler.ts` — validate payload at the boundary
- `src/validation/request.ts` — single validation entrypoint
- `tests/api/handler.test.ts` — regression test for invalid payload

## verified
- Reproduction before fix: `pnpm test tests/api/handler.test.ts -t rejects_invalid_payload` -> FAIL
- Reproduction after fix: same command -> PASS
- Broader check: `pnpm test tests/api/handler.test.ts` -> PASS

## unverified
- Full integration suite not run
- Browser/UI surface not applicable

## blocked
- Integration suite needs a database container that was not running in this session.

## assumption
- Rejecting at the boundary does not change valid-payload behavior; covered by the existing happy-path test.

## Files touched
- `src/api/handler.ts`
- `src/validation/request.ts`
- `tests/api/handler.test.ts`
