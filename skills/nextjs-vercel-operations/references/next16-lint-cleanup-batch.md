# Next 16 migration + safe lint-cleanup batch pattern

Use this when upgrading a Vercel-hosted Next.js app and then burning down legacy lint debt without changing behavior.

## What worked in this session
1. Confirm the target version and engine before upgrading:
   - `npm view next version`
   - `npm view next@<version> engines`
2. Upgrade with `npm install next@<version>` and run a normal `npm install` if lockfile deps are missing.
3. Run the codemod for middleware migration:
   - `npx @next/codemod@canary middleware-to-proxy .`
4. Verify the migration actually landed:
   - `git status --short`
   - check for `proxy.ts` and the expected file removals/modifications
5. Re-run `npm run build` and `npm run test` immediately after the upgrade/migration.

## Safe lint-cleanup batch pattern
1. Run a strict scan that temporarily promotes the noisy rules you want to burn down:
   - `npx eslint . -f json --rule '@typescript-eslint/no-unused-vars:error' --rule 'react-hooks/exhaustive-deps:error'`
2. Rank files by count, then clean the lowest-risk files first:
   - unused imports
   - unused locals/state setters
   - `catch (error)` blocks where the error is never read
3. Prefer behavior-preserving edits:
   - remove dead imports/state only after confirming no callsites
   - convert internal navigation to `Link` rather than raw anchors
   - narrow `unknown` only when the message is actually used
4. Treat hook dependency warnings as behavior-sensitive; patch the smallest semantic-preserving change or defer if the fix would change timing.
5. After each batch, rerun `lint -> build -> test` before touching the next group.

## Pitfalls
- A green `next build` does **not** mean lint is clean; build can pass while warnings remain.
- Codemod output may be subtle; always verify with `git status` and file reads, not just console logs.
- Don't bulk-delete imports from a partial file read. Re-read the full file or use compiler/lint output to confirm usage.
- Keep the scope narrow: fix warning clusters in one batch, verify, then continue.

## Notes
- This pattern pairs well with `references/next16-migration-notes.md`.
- Use `references/lint-safe-cleanup-batch.md` for a shorter generic version of the same idea if you need a lighter checklist.