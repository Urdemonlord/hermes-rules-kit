# SvelteKit 2.x `redirect()` != `Response`

## Symptom

Catch block around `createPayment()` or any async function fails to re-throw `throw redirect(302, location)`:

```ts
try {
  await createPayment(...)
  throw redirect(302, `/order/${orderId}?payment=created`)
} catch (e: any) {
  if (e instanceof Response) throw e       // ← never matches
  console.error('[checkout] payment error:', e)
  throw redirect(302, `/order/${orderId}?payment_error=1`)
}
```

Result: payment succeeded but redirect goes to `?payment_error=1` path. Log shows `Redirect { location: '/order/xxx?payment=created' }`.

## Root cause

SvelteKit 2.x `redirect()` function throws an instance of its own `Redirect` class — **not** `Response`. The `instanceof Response` check always returns `false`.

The thrown object has:
- `status: 302` (numeric)
- `location: '/order/xxx?payment=created'` (string)

## Fix

```ts
} catch (e: any) {
  // SvelteKit redirect() throws Redirect, NOT Response
  // Redirect has {status, location}
  if (e instanceof Response || (e?.status && e?.location)) throw e
  console.error('[checkout] payment error:', e?.message || e)
  throw redirect(302, `/order/${orderId}?payment_error=1`)
}
```

`e?.status` → `302` (truthy)
`e?.location` → `'/order/xxx?payment=created'` (truthy)
→ condition passes → `throw e` re-raises the redirect correctly.

## When this matters

Any time you wrap SvelteKit form action logic in nested try/catch:

- `createPayment()` call in checkout actions
- External API call where success triggers `redirect()`
- Transaction/DB operations where post-success flow uses `redirect()`
- Any `catch` block between `throw redirect()` and SvelteKit's internal handler

## Prevention pattern

```ts
// Generic "re-throw SvelteKit redirects" guard
function isRedirect(e: any): boolean {
  return e instanceof Response || (e?.status && e?.location)
}
```

Use before any catch block that might intercept redirects:

```ts
try { ... } catch (e: any) {
  if (isRedirect(e)) throw e
  // handle real errors
}
```

## Detection

Check server logs for pattern:
```
[component] some error: Redirect { location: '/some/path' }
```

If you see a `Redirect` object logged as an error, the `instanceof Response` check is the root cause.
