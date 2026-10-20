# Removing a runtime dependency from the client bundle

A heavy runtime library (a validation schema lib, a date lib) ends up in a route's
**initial** client bundle even though the browser barely uses it. The usual cause is a
shared module that mixes *runtime values* with the library: one `import { someValue }`
from the schema module drags the whole library in, and every client component that
needs a constant now carries it.

## First prove it is in the INITIAL load, and measure it

A dependency in *a* chunk is not the problem; one in the route's initial load is. The
build manifest lists exactly which chunks a route loads up front:

```bash
# which chunks does /editor load immediately?
grep -o '[a-z0-9-]*\.js' .next/app-build-manifest.json   # then read pages['/editor/page']
# is the library in any CLIENT chunk?
grep -rl 'ZodError\|$ZodError' .next/static/chunks/**/*.js
# how big is it, gzipped, as the browser sees it?
python3 -c "import gzip,sys;d=open(sys.argv[1],'rb').read();print(len(d)//1024,'KB raw',len(gzip.compress(d,9))//1024,'KB gzip')" <chunk>.js
```

`import type` costs nothing at runtime (erased at compile). A **runtime value** import
is what pulls the library in. So grep for the value imports, not the type imports.

## Pick the cheaper of two fixes

- **Move the runtime values out** (preferred when the library is genuinely needed at
  runtime somewhere in the client): a dependency-free module holds the constants, the
  id helper, and the default/blank object. Client code imports from there.
- **Rewrite the library's usage** (a smaller API, hand-rolled logic) only if the library
  is *not* needed client-side at all. Bigger change, bigger blast radius.

## Recipe: dep-free module + test-only oracle + parity test

The load-bearing idea is that you do **not** delete the original schema — you demote it
to a **test-only oracle** and prove the replacement is equivalent.

1. **Create a dep-free module** (e.g. `lib/cv/model.ts`): the option-list constants, the
   `newId` helper, the blank/empty object, and the type aliases. Types may be re-exported
   from the schema module with `import type` — erased, so no runtime edge.
2. **Keep the schema module** (e.g. `schema.ts`) with the library, now imported by tests
   only. It defines the shape once; nothing client-side imports it.
3. **Hand-write the coercion** the client actually runs, with one fallback mirroring
   every rule in the schema (each `.catch(...)` becomes an explicit `??`/guard).
4. **Write a parity test** that deep-equals the hand-rolled result against the oracle
   across a table of malformed inputs:
   ```ts
   for (const input of cases) {
     expect(stripIds(coerce(input))).toEqual(stripIds(oracle.parse(input)));
   }
   ```
   This is what keeps the two from drifting; without it the hand-rolled version silently
   diverges on the next schema change.
5. **Repoint every import — including `import type` ones — to the new module**, so the
   rule is single and a future edit cannot accidentally leak the library back in.
6. **Verify the library is gone from the client** and measure the win:
   ```bash
   grep -rl '<LibSymbol>' .next/static/chunks/**/*.js   # expect: no output
   # then recompute the route's initial-load gzip from app-build-manifest
   ```
   Confirm it is still present **server-side** (the API route still needs it) — the goal
   is a client/server split, not removal.

## Pitfalls

**The oracle throws where the hand-rolled version returns blank.** A raw
`schema.parse(null)` / `.parse(42)` / `.parse('nope')` **throws**, but the real client
path runs a sanitizing migration step first, so the hand-rolled version returns a blank
object. Compare on **post-migration shapes** (plain objects), and add a separate test
that the hand-rolled path does not throw on non-object input — that tolerance is exactly
why the coercion exists.

**Both sides generate fresh ids, so they never compare equal.** Strip ids before the
deep-equal and compare id *presence/shape* instead of value.

**Mirror the array semantics exactly.** `.catch([])` on an array drops the **whole
list** when any element fails validation — it does not filter the bad element out. A
hand-rolled `filter(...)` is a behavioural difference, not a cleanup. Test it:
`expect(coerce({ experience: [{ ok: 1 }, 'junk'] }).experience).toEqual([])`.

**A blanket codemod for the import repoint is wrong here.** Run it, then re-check the
schema module is imported only by tests. If a value import slips through, the library
comes straight back into the bundle and the gzip measurement will not move.
