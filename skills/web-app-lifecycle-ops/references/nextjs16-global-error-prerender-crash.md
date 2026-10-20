# Next.js 16 `_global-error` Prerender Crash (useContext null)

## Problem

`next build` fails with:

```
Error occurred prerendering page "/_global-error".
TypeError: Cannot read properties of null (reading 'useContext')
Export encountered an error on /_global-error/page: /_global-error
```

**Only happens in `next build`, not `next dev`.** Pre-existing — verified by stashing all local changes and rebuilding.

## Root Cause

Next.js 16.0.2+ bug (confirmed in 16.2.4). During static generation, Next.js synthesises an internal `/_global-error` page that wraps the root layout. When the root layout contains client components using React hooks (`useContext`, `useState`, `useCallback`), React 19's SSR dispatcher is null in this synthetic context, crashing with "Cannot read properties of null (reading 'useContext')".

Framework issue: https://github.com/vercel/next.js/issues/86178

## Workaround

Add to `next.config.mjs`:

```js
experimental: {
  prerenderEarlyExit: false,
}
```

Next.js defaults to `prerenderEarlyExit: true` — on any static-gen failure, it exits immediately. Disabling it makes the build continue past the `_global-error` error and complete successfully. The error is still logged but does not block the build.

## What DIDN'T Work

| Approach | Result |
|---|---|
| Custom `app/global-error.tsx` (`"use client"`) | Still crashes — Next.js ignores it for internal synthesis |
| Custom `app/not-found.tsx` | Helps other prerender issues, not `_global-error` |
| `export const dynamic = "force-dynamic"` on layout + global-error | Not respected for synthetic internal route |
| `next/dynamic(..., { ssr: false })` on layout | Banned in Next.js 16 Server Components |
| Mounted guard (`useState` + `!mounted` return) on `AuthProvider` | Still crashes — `useContext` fails before guard runs |
| `"use client"` global-error without any imports | Still crashes — the synthetic wrapper is the problem |

## Verification

After applying `prerenderEarlyExit: false`:

```bash
npm run build
# ... "Export encountered errors on 1 path: /_global-error/page: /_global-error"
echo $?  # 0 — build succeeds
ls -d .next  # exists, ~130MB+
```

All actual app routes build and deploy normally. The `_global-error` error at static-gen time only affects the synthetic error handler page, not real routes.
