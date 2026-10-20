# `npm ci` does not run the Prisma postinstall, so the Client is stale and every Prisma type collapses to `any`

## Symptom

After `npm ci` in a repo whose `package.json` has no `postinstall` script,
`npm run check` explodes with errors that read like your own code is broken:

```
src/routes/.../+page.server.ts:82:47
Error: Parameter 'v' implicitly has an 'any' type. (ts)
Error: Cannot find module '@sveltejs/kit' or its corresponding type declarations.
```

They all disappear after one command. The diagnostic tell: **`node_modules` exists
and `npx` works, but the types are gone wholesale** — that is an ungenerated
Prisma Client, not broken code.

## Mechanism

npm 10+ (the `allowScripts` flag) blocks install scripts by default and says so
in the `npm ci` output:

```
npm warn allow-scripts 2 packages have install scripts not yet covered by allowScripts:
npm warn allow-scripts   @prisma/engines@7.9.0 (postinstall: node scripts/postinstall.js)
npm warn allow-scripts   prisma@7.9.0 (preinstall: node scripts/preinstall-entry.js)
```

`@prisma/client` installs but never gets its generated `index.d.ts`. Every
`prisma.model.findMany()` degrades to `any`, and every `.find((v) => ...)`
callback inherits an implicit-any — which is why the errors land in files you
did not touch on that line.

## Fix

Run the generate step yourself; never assume `npm ci` covered it:

```bash
cd <repo> && npx prisma generate
```

In a Dockerfile this is already correct when `npx prisma generate` is an explicit
`RUN` step after `COPY prisma/`.

## Do not "fix" it by annotating TypeScript

The tempting move — adding `: any` across the files the checker flagged — is
strictly worse: it silences the symptom, buries the real types once the Client is
generated, and leaves the codebase worse than before.

## Baseline first: never mistake inherited debt for damage you just caused

Take a baseline by stashing, then compare counts:

```bash
git stash push -u -m "wip"
npm run check 2>&1 | tail -1     # baseline error count
git stash pop
```

One command, two numbers. If a toolchain fix drops the count sharply without
touching a line of code, the cause was the toolchain. Whatever remains is
pre-existing project debt — report it, do not absorb it mid-task.
