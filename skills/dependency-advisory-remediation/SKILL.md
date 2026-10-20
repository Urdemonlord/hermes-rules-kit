---
name: dependency-advisory-remediation
description: Close npm audit advisories by minimal dep upgrades.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    category: software-development
    tags: [dependencies, security, npm, audit, upgrades, breaking-changes]
    related_skills: [github-pr-workflow, nextjs-vercel-operations]
---

# Dependency Advisory Remediation

Close `npm audit` advisories in a JS/TS project by upgrading the smallest set of
dependencies, in the smallest version jumps, and verify nothing else broke.

## When to use

Use when the user asks to fix advisories, "tutup audit", upgrade a vulnerable
dependency, or clear `npm audit` output. Also when a toolchain upgrade (Vite, Next,
Vitest, Tailwind) is forced by an advisory.

## Procedure

### 1. Group the advisories by the package you must actually upgrade

`npm audit` lists one entry per vulnerable **transitive** package, but the thing you
change is the **top-level** package that pulls it. Read the `node_modules/<pkg>` parent
chain and group. A single top-level bump often closes several advisories at once.

```bash
npm audit                     # full report
npm audit --json              # machine-readable; group by `via`/`effects`
npm ls <pkg>                  # who pulls it, and which copy
```

Classify each group by its fix path, because that decides the order you do them in:

| Fix path | Meaning | Do it |
|---|---|---|
| `npm audit fix` | non-breaking, semver-compatible | first, always |
| `--force` → "will install X@N, breaking change" | needs a major bump | separately, one per PR |

### 2. Land the non-breaking fixes first, alone

```bash
npm audit fix
```

Commit just the lockfile change as its own PR. It is the cheap win and it shrinks the
surface for the hard upgrades. Do not bundle it with a major upgrade — one PR per
root cause keeps review and rollback trivial.

### 3. For each breaking group, find the MINIMAL fixed version

Do **not** jump to the newest major. The advisory names a vulnerable **range**; the fix
often lands in a minor/patch of the *current* major.

```bash
npm view <pkg> versions --json | python3 -c "import json,sys;print([v for v in json.load(sys.stdin) if v.startswith('<major>.')])"
```

Example shape: an advisory covering `2.1.0 - 4.1.10` is closed by `4.1.11`, so a bump
within major 4 fixes it — the next major (5) is not required. Choosing the minimal
version avoids dragging in the next major's own breaking changes and Node requirement.

### 4. Check `engines.node` BEFORE upgrading

A newer major can force a Node bump the CI does not have.

```bash
npm view <pkg>@<version> engines
npm view <pkg>@<version> dependencies      # did a bundled tool disappear?
```

Compare against the CI's Node (read `.github/workflows/*.yml` → `node-version`). If the
minimal-fixed version fits the existing Node, prefer it over the newest major that
does not — you avoid a second migration.

The same check applies in reverse when you **add** a dependency: the floor can be raised by a
package you never named, and the direct dependency's own `engines` field will not tell you.
Read the floor off the **installed lockfile**, not the manifest:

```bash
node -e "const l=require('./package-lock.json');for(const [k,v] of Object.entries(l.packages))if(v.engines?.node)console.log(k,v.version,v.engines.node)"
```

Any entry demanding a higher Node than `package.json`'s `engines.node` (or the CI's
`node-version`) is a silent runtime floor: it builds, type-checks and tests fine on the dev
machine and fails on the oldest runtime you claim to support. Raise the declared floor in the
same commit — or pin a version of the transitive package that still supports it — and update
the README's stated Node requirement to match. Grep the whole lockfile rather than checking the
packages you know about; the offending one is usually two levels down.

### 5. Install, then fix the tool's own breaking changes

```bash
npm install -D <pkg>@<fixed-version> -w <workspace>
```

Then run the gates and fix what breaks. Breaking changes that show up as test/type
errors are expected — resolve them in the config, never by weakening tests. See
`references/toolchain-breaking-migrations.md` for the recipe (how to find the correct
new config option by grepping the installed `.d.ts`) and worked cases.

### 6. Verify — full gate set, not just tests

```bash
npm run type-check && npm test && npm run lint && npm run build
```

Then run any **scripts that consume the upgraded tool** — an upgrade that drops or
renames a bundled binary passes every gate above and still breaks a `scripts/`
command. Run them explicitly.

### 7. Ship one PR per root cause

Branch, commit, push, open PR, wait for green, squash-merge. Rebase onto `origin/main`
if a sibling dependency PR merged first (both touch `package-lock.json`).

When the rebase conflicts **only in `package-lock.json`**, do not hand-merge the lock:
abort, hard-reset onto the new `origin/main`, and re-run the install so npm regenerates
the lock against the current tree.

```bash
git rebase --abort
git reset --hard origin/main
git checkout <your-branch> && git reset --hard origin/main   # re-point the branch
npm install -w <workspace> <pkg>@<range>                     # regenerate the lock cleanly
git add -A && git commit -m "…"                              # recommit on the new base
git push --force-with-lease
```

The branch was already pushed, so the re-push needs `--force-with-lease` (safe on a
feature branch, never on `main`).

## Pitfalls

**`npm install` rewrites the lockfile beyond your change.** It can prune entries
unrelated to your bump (an old nested `postcss` copy, a dedupe). Inspect
`git diff --stat package-lock.json` before committing; if the churn is not part of the
upgrade, revert the file (`git checkout -- package-lock.json`) so the PR stays scoped.

**A test that fails locally may be an occupied port, not your change.** Before blaming
the upgrade, check what owns the port: `ss -ltnp | grep <port>`. A Docker container or
another project's server on the test port makes the harness reuse a foreign server and
assert against the wrong app. Prove it by re-running on a free port; make the port
overridable via an env var (`Number(process.env.E2E_PORT ?? 3200)`) so it cannot
recur. CI runners are clean, so a local-only failure with a busy port is not a CI risk.

**A downgraded test toolchain must not weaken tests.** When a config option disappears
(esbuild→oxc, a renamed loader), the fix is the equivalent new option — never deleting
the JSX/transform config or skipping the failing suite.

**`git push --force-with-lease` can reject with `stale info` on a branch you just
fetched** when no remote-tracking ref was created. Fetch the explicit refspec, then pin
the lease to the value you just read (safe on a feature branch, never on `main`).
Recipe is in `nextjs-vercel-operations`.

**Do not report an advisory count from memory.** Re-run `npm audit` after each merge —
the number and the remaining groups change as siblings land.

**Some advisories have no fix and must be documented, not forced.** When the advisory
covers *every* published version of a package (`npm view <pkg> versions` shows the fix
range spanning all of them), no bump closes it. Trace the parent chain to see how it is
reached — if the only path is a **dev-only** tool (a linter, an ESLint plugin) and not
runtime code, leave it and note it as a known dev-only issue. Do NOT accept the
`--force` suggestion when it proposes a **downgrade** of a core framework (e.g. Next) to
satisfy a lint-time transitive dep; that trades a real runtime version for a cosmetic
zero.

**The vulnerability may sit behind a dependency's own major bump.** A transitive
package can vanish entirely one major up (a new `gaxios` major dropping `uuid`). Before
assuming a config migration is needed, read the dependency's changelog for the exact
breaking-change scope — a major version often breaks only an API surface the project
does not use (e.g. "breaking changes are only in Interactions; `GenerateContent` is
unaffected"). Verify by grepping the installed `.d.ts` for each config field the code
actually passes.

**Measure a dependency's bundle cost before refactoring to shrink it.** The plan.md-style
estimate ("zod adds ~17 kB") is a guess. Get the real number two ways: bundle the import
with a throwaway probe and gzip it (`npx esbuild probe.ts --bundle --minify --format=esm
--outfile=/tmp/p.js` then compare `gzip -9` sizes of the current vs candidate import),
and confirm the chunk is actually in the target route's *initial* load by grepping the
build manifest (`grep -o '<chunkid>' .next/app-build-manifest.json`). A dependency that
is only reachable from an `import type` costs nothing at runtime; one pulled in by a
runtime value call (e.g. a helper that runs `schema.parse`) lands in the client bundle.
Decide with the measured number, and prefer moving the runtime value out of the
schema module over rewriting the whole schema to a smaller API. The full recipe —
dep-free module, test-only oracle, parity test, and the array/`null` pitfalls that break
the equivalence — is in `references/client-bundle-dependency-removal.md`.

## Verification checklist

1. `npm audit` shows the target advisories gone (quote the before/after count).
2. `type-check`, `test`, `lint`, `build` all pass.
3. Scripts that consume the upgraded tool still run.
4. `package-lock.json` diff contains only the intended bump.
5. Each breaking upgrade is its own PR, CI green before merge.
