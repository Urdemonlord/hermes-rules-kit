# Dependency reconnaissance before installing a Node service

Run this before writing `package.json` for a new service. It takes a couple of
minutes and catches the traps that otherwise surface as a build failure after the
whole module is written.

## The recipe

```bash
# 1. What does "latest" actually point at? (not always a stable release)
npm view <pkg> dist-tags --json          # -> {"latest":"...", "next":"...", "rc":"..."}

# 2. Is the version you want real, and what are the neighbours?
npm view <pkg> versions --json | python3 -c \
  "import sys,json; v=json.load(sys.stdin); print([x for x in v if x.startswith('6.') and '-' not in x][-3:])"

# 3. Module system — ESM-only packages break a CommonJS host
type=$(npm view <pkg> type) ; echo "type=$type"
npm view <pkg> exports --json            # look for a "require" entry

# 4. Peer ranges — does this actually work with the framework version you pinned?
npm view <pkg> peerDependencies --json

# 5. Can the platform do it without a dependency at all?
node -e "const c=require('node:crypto');console.log(typeof c.scryptSync)"
```

## Trap 1 — `latest` can be a release candidate

A bare `npm install prisma` resolved to `8.0.0-rc.17`. An RC in a production service
is an unbounded risk. Always read `dist-tags` and pick the newest **non-prerelease**
version of the major line you intend to use (here `6.19.3`), not `latest`.

## Trap 2 — ESM-only packages fail inside a CommonJS app

`uuid@14` declares `"type": "module"` with no `require` export. NestJS compiles to
CommonJS, so importing it is a runtime `ERR_REQUIRE_ESM` — often only at the first
request, not at build. Either pin the last dual-format version (`uuid@11` ships both
`dist/cjs` and `dist/esm`) or drop the dependency.

**Prefer dropping it.** A UUID can come from the platform:

```ts
import { randomUUID } from "node:crypto";
```

Fewer dependencies is one fewer thing that can break the build.

**Check the framework itself, not just leaf packages.** A major version of the web
framework can go ESM-only while its own tooling lags: NestJS 12 declares
`"type": "module"`, and Jest 30 cannot load it (`Must use import to load ES Module`).
The service still *runs* on Node 22, which has `require(esm)` — so the build and a
manual `curl` both look fine and only the test runner breaks, which is worse than a
clean failure. Run the `type` check on `@nestjs/core` (or your framework) before
pinning the major, and pin the last CommonJS major (`11.x`) when the surrounding
tooling has not caught up. Remember the test harness is a dependency too: an e2e
suite needs `@nestjs/testing` in `devDependencies`, and its absence is a
`Cannot find module` at test time, not at install time.

## Trap 3 — "latest" of a compiler is ahead of the ecosystem

`typescript` latest was `7.0.2` while `ts-jest@29` declares `typescript >=4.3 <7`.
Installing the newest compiler would fail peer resolution. Pin the newest version the
peer range actually admits (`5.9.3`), and read `peerDependencies` rather than trusting
the package name.

## Trap 4 — native-build dependencies on a small shared host

`bcrypt` and `argon2` need a compiler and enough RAM to build; on a 3.7 GB box shared
with other services this is how you OOM. Check the platform first — `node:crypto`
ships `scrypt` and `pbkdf2`, both adequate KDFs:

```bash
node -e "const c=require('node:crypto');const h=c.scryptSync('pw',c.randomBytes(16),64,{N:16384,r:8,p:1});console.log('scrypt OK',h.length)"
```

If the platform has it, use it and remove the dependency.

## Trap 5 — a transitive dependency can outrank your direct pin

Gradle/Maven raise this for JVM projects, but it bites npm too: a package's own
dependency can pull a newer version of a shared library than the one you pinned. When
a build demands a higher runtime/API version than expected, read the **POM or
`dependencies` of your direct dependency**, not just the direct version you chose.

```bash
npm view <your-dep> dependencies --json
```

## Trap 6 — the package lives on JSR, not npm

A package documented on a JSR page (`jsr.io/@scope/name`) is often absent from
npm, and the two registries fail differently:

```
npm i @scope/name                      -> 404 Not Found      (it is not on npm)
npm i --registry https://npm.jsr.io    -> 403 Forbidden      (or a policy 403)
curl https://jsr.io/@scope/name/meta.json -> 403 Forbidden   (CDN blocks this IP)
```

A 403 from a CDN or edge is **not** proof the package is unavailable — it is proof
this host was refused. Do not conclude "the library is gone" or fall back to
hand-rolling it. Go to the source:

```bash
gh search repos <keyword> --limit 20      # JSR packages usually have a GitHub origin
gh search repos <exact-name> --limit 5
```

Clone the origin and install from it (`npm i file:/path/to/clone`, or
`"dep": "github:owner/repo"`), or use `npx jsr add @scope/name` where a JSR CLI
exists. Read `jsr.json` / `deno.json` for the declared version and exports.

**Verify the real exports before writing an adapter.** A JSR package's entry is
usually `mod.ts` (TypeScript, Deno-flavoured) and may ship no compiled npm build —
check `package.json` for a `main`/`exports`/`files` and for a build step before
assuming `import('@scope/name')` resolves:

```bash
node -e "import('<pkg>').then(m=>console.log(Object.keys(m)))"
```

Adapting a package against guessed signatures from hosted docs yields code that
imports cleanly and fails at first call. Keep every vendor package behind one
adapter module so an unverifiable signature is a one-file fix, and say plainly in
the summary which parts were checked against source and which were assumed.

## Record the outcome

Write the pinned versions and the reason for each non-obvious choice into the repo's
build notes. A future session that sees `"typescript": "5.9.3"` next to a `7.0.2`
on the registry will otherwise "helpfully" upgrade it and break the build.
