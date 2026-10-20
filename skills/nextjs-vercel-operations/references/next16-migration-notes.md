# Next.js 16 migration notes (roblox-top-up-system)

## What changed in this session
- Upgraded `next` from `^15.1.0` to `^16.3.0`.
- Renamed the root routing guard from `middleware.ts` to `proxy.ts`.
- Renamed the exported function from `middleware()` to `proxy()`.
- Migrated linting from `next lint` to ESLint CLI (`eslint .`).
- `npm install` regenerated `package-lock.json`, `next-env.d.ts`, and `tsconfig.json`.

## Verified commands
```bash
npm install next@16.3.0
npm install
npm run build
npm run test
npm run lint   # now uses ESLint CLI, not next lint
```

## Useful codemods
```bash
npx @next/codemod@canary middleware-to-proxy .
npx @next/codemod@canary next-lint-to-eslint-cli .
```

## Pitfalls
- The middleware codemod may not rewrite everything in one pass; if the repo already has `proxy.ts`, confirm there isn't a stale `middleware.ts` left behind.
- Next 16 build output may still label the route guard as `ƒ Proxy (Middleware)` — that is expected.
- `next lint` is no longer the right command after the ESLint CLI migration; a stale script can fail with a misleading path error.
- `next build` may update `tsconfig.json` automatically (for example `jsx: react-jsx`) and may refresh `next-env.d.ts`; keep those generated changes.

## Proof from this repo
- Build passed on Next `16.3.0`.
- Tests passed after the upgrade.
- Lint surfaced existing repo debt (`any`, hook violations, etc.) rather than upgrade breakage.
