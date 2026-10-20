# Refactor branch recovery (storefront, Aug 2026)

Session: `chore/codebase-cleanup-and-refactor` arrived with 27 TS errors across 10 files. Full fix + cleanup review + 2 commits. Reusable playbook below.

## Gate: tsc is the real check, build is not
`next.config.mjs` has `typescript: { ignoreBuildErrors: true }` → `npm run build` passes even with TS errors. Real gate:
```bash
npx tsc --noEmit 2>&1 | grep -v 'node_modules' | grep 'error TS'
```
The `-v node_modules` filter is mandatory — Next 16 d.ts files spew noise (`RuleSetUseItem`, `PromiseWithResolvers`, `esModuleInterop` errors from `@types/react`). All app-level errors must be 0.

## Error clusters → root causes (what each fix looked like)
| Cluster | Root cause | Fix |
|---|---|---|
| 4-arg logger call | `logOrderEvent` accepted 3 args, callers passed 4 (metadata) | optional `metadata` param + INSERT column |
| `expectedRobuxAfterFee` / `expectedGamepassPrice` undefined | props declared in type but never destructured, or dropped from type | add to type + destructure + pass at all callers |
| hoisting | `useEffect` referenced `fetchOrders` before `useCallback` decl | move declaration above effect |
| missing helper/type | `calculateStats`, `OrderRow` called but never defined | define |
| missing import | `NextRequest` used in signature, never imported | import |

Pattern: props-vs-destructure mismatch = check 3 places (type, destructure, every caller). Refs left behind after removals (`selectedOrder` state) — TS catches when JSX still uses them; if TS passes, deletion was safe.

## Cleanup-review checklist (diff-level)
- `git diff --stat | sort -t'|' -k2 -rn` → biggest files first (lockfile noise excluded).
- **Half-removed feature = dead no-op setters**: `const [, setImageFile] = useState<File|null>(null)` — state dropped, setter kept. Callers still call `setImagePreview(...)` → silently no-op. Fix = remove ALL of it (state, setters, calls, `isUploading`, button label ternary).
- **Dead config after feature removal**: hero-banner lost quick-select buttons but `quickAmounts: number[]` stayed in type + all 3 slide objects. Fix = remove field everywhere.
- **`catch (err: any)` → `catch {}`**: safe ONLY in non-fatal paths (cache, notify, webhook fire-and-forget). When typing to `unknown`, must `instanceof Error` check before `.message`.
- **Route disabled for platform reasons must match UI**: upload route returns 400 "not supported on Vercel" (read-only FS) → admin UI still had upload button/state. Either remove UI flow or wire external storage; half-state = bug.
- **Removed import still used?** `orders/create` dropped `NextResponse` but file used `secureJsonResponse` helpers — verify with `grep -c` before trusting.

## Middleware restore (Next 16)
`mv proxy.ts middleware.ts` + rename export `proxy` → `middleware`, then verify:
```bash
git diff --no-index <(git show HEAD:middleware.ts) middleware.ts  # expect: IDENTICAL
```
Build output labels it `ƒ Proxy (Middleware)` either way — not a signal. Function name IS the signal.

## Tool pitfall: batch patch context collision
Patching same file twice in one batch: 2nd patch's `old_string` matched SHIFTED context and deleted `handleOpenDelete` body (the 1st patch had removed preceding comment lines, making context ambiguous). Restored by re-patching. Lesson:
- After each patch batch to the same file, `grep -n 'function ' file` to confirm all function bodies intact.
- If a patch touches lines adjacent to another patch's region, re-read the file first.
- Never let `old_string` span a function boundary unless you verify the full function is inside the replacement.
