---
name: npm-advisory-cleanup
description: Use when clearing npm audit advisories safely.
---

# Clearing npm advisories safely

## Rule 0: never run `npm audit fix --force` unexamined
The suggested fix is often a **downgrade** (e.g. "install eslint-config-next@14.2.35" to fix a transitive `braces`). Read the whole chain first: `npm audit` prints the dependency path. Only accept a force fix if the target version is a real upgrade of a package you intend to move.

## Rule 1: triage before touching anything
Group advisories by the *upgrade* that closes them, not by package name:

1. `npm audit` and record the baseline count (e.g. "15 (2 critical, ...)").
2. For each advisory, note the top-level dep that pulls it in.
3. Split into: (a) closable by plain `npm audit fix` (non-breaking), (b) needs a major bump, (c) **no fix exists** — verify this with `npm view <pkg> versions` and reading the advisory range; if the advisory covers all versions, stop and document it.

## Rule 2: land non-breaking fixes first, in their own PR
`npm audit fix` (no `--force`) only does semver-compatible bumps. Run it alone, verify, ship. This shrinks the remaining set and keeps later PRs focused.

## Rule 3: check the *minimum runtime* before jumping a major
A major bump that fixes advisories may raise the Node floor past CI. Check before installing:
```
npm view <pkg>@<version> engines
npm view <pkg>@<version> dependencies   # is the vulnerable transitive gone?
```
Pick the **lowest** major that clears the advisory, not the latest. (Real case: vitest 5 cleared a critical but required Node >=22.12 while CI ran Node 20; vitest 4.1.11 cleared the same advisory and supported Node 20.)

## Rule 4: when a bump changes the build tool, expect config breakage
Major bumps can swap the underlying transformer (e.g. Vite 8 replaced esbuild with oxc; vitest 4 dropped its bundled `vite-node`). Symptoms: type errors on config options that no longer exist, or test files failing to parse JSX. Fix by reading the installed types (`grep` the `.d.ts` for the option name) rather than guessing. If a helper binary disappears, re-add it as a standalone dev dependency at a version matching the new toolchain.

## Rule 5: prove visual/CSS changes are neutral with a baseline diff
For a CSS framework major upgrade, save the built CSS **before** migrating (`cp .next/static/css/*.css /tmp/baseline.css`), migrate, rebuild, then diff specific utility rules against the baseline. Watch for: theme variables that were overridden in the old config but silently revert to framework defaults (e.g. `rounded-sm/md/lg` bound to a custom `--radius`); renamed utilities (`outline-none`→`outline-hidden`, `shadow-sm`→`shadow-xs`); and gradient interpolation changes (v4 uses oklab; write a plain `linear-gradient` if the old sRGB output must be preserved).

## Rule 6: verification loop after every bump
`type-check` → unit tests → `lint` → production `build` → E2E. Type-check alone does not prove a runtime SDK upgrade is safe: also grep the installed `.d.ts` to confirm every config field/option you pass still exists.

## Rule 7: know what you cannot fix
Some advisories (notably `braces`, reachable only via lint tooling like `eslint-config-next` → `fast-glob` → `micromatch`) have no patched version. Confirm it is **dev-only** (not in the runtime dependency path), then document it as a known issue with the exact path and why no action is taken. Do not downgrade a framework to silence a dev-only advisory.

## Lockfile conflicts between sibling PRs
Two PRs that both touch `package-lock.json` will conflict on rebase. Do not hand-merge the lockfile: `git reset --hard <new-base>`, re-run the install command, and re-commit. Force-push with an explicit lease (`--force-with-lease=<branch>:<known-remote-sha>`) when the refspec-tracking ref is stale.
