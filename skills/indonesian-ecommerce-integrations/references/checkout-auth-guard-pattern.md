# Checkout Auth Guard Pattern — Prevent Guest Checkout

## The Problem

SvelteKit checkout pages (`/checkout`) must require login. Without explicit guards, guests can:
- Access GET `/checkout` (renders form, shows items)
- Submit POST `/checkout` form actions directly

This bypasses the merchant's checkout flow — guests should see a login redirect, not a checkout form.

## The Fix — Double Guard

Apply auth checks in **two places** to cover both page load AND form submission:

```typescript
// src/routes/checkout/+page.server.ts
import { redirect } from '@sveltejs/kit'
import type { Actions, PageServerLoad } from './$types'

export const load: PageServerLoad = async ({ locals }) => {
  // Guard 1: Prevent guests from viewing checkout page
  if (!locals.user) throw redirect(302, '/login')

  // ... rest of load logic
}

export const actions: Actions = {
  default: async ({ request, locals, url }) => {
    // Guard 2: Prevent guests from POSTing checkout form directly
    if (!locals.user) throw redirect(302, '/login')

    // ... rest of action logic
  }
}
```

## Why Both Guards?

| Vector | Attack | Guard Blocks? |
|--------|--------|---------------|
| Browser GET /checkout | Load form | `load` guard ✓ |
| curl POST /checkout | Form submission | `action` guard ✓ |
| Bypass redirect, POST raw form | Direct submission | `action` guard ✓ |
| Headless API client POST | Automated checkout | `action` guard ✓ |

## Why Guards Are Separate

**Layout-level guards don't protect form actions:**

```typescript
// +layout.server.ts — ONLY protects page loads
export const load: LayoutServerLoad = async ({ locals }) => {
  if (!locals.user) throw redirect(302, '/login')
}

// ❌ Does NOT protect form actions in +page.server.ts
// Form POST to /checkout still executes even if layout load redirected
```

SvelteKit separates page load (`load` function) from form actions (`actions` object). Guards must be explicit in both.

## Verification

```bash
# 1. GET redirect to login
curl -s -o /dev/null -w "GET /checkout => %{http_code}\n" https://example.com/checkout
# → 302

# 2. POST redirect (or 403 if CSRF applies first)
curl -s -o /dev/null -w "POST /checkout => %{http_code}\n" -X POST https://example.com/checkout \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'name=a&phone=b&address=c&city=d&province=e&zip=f'
# → 302 (redirect to login) or 403 (CSRF from curl)
# Both are acceptable — guard fired before CSRF was even checked
```

## Best Practice: Extract Guard Function

For DRY code when multiple routes need the same guard:

```typescript
// src/lib/server/auth.ts
import { error, redirect } from '@sveltejs/kit'

export function requireLogin(user: any) {
  if (!user) throw redirect(302, '/login')
}

export function requireAdmin(user: any) {
  if (!user || user.role !== 'admin') throw error(403, 'Access denied')
}
```

Then use in routes:

```typescript
// src/routes/checkout/+page.server.ts
import { requireLogin } from '$lib/server/auth'

export const load: PageServerLoad = async ({ locals }) => {
  requireLogin(locals.user)  // ← cleaner
  // ...
}

export const actions: Actions = {
  default: async ({ locals }) => {
    requireLogin(locals.user)  // ← reused
    // ...
  }
}
```

## Anti-Pattern: Relying on Client-Side Hide

❌ **WRONG:**
```svelte
{#if !user}
  <p>You must log in to checkout</p>
{:else}
  <form>...</form>
{/if}
```

Attackers can:
1. Inspect HTML/CSS to find form structure
2. POST to `/checkout` action directly, bypassing client-side check
3. Bypass JavaScript entirely

Always guard server-side in `load` and `actions`.

## Related Patterns

- **Admin form actions**: See `references/sveltekit-admin-auth-pitfall.md` — similar guard pattern for `/api/admin/` endpoints
- **Rate limiting**: Add after auth checks to prevent brute-force attacks on checkout (see `references/rate-limiting-sveltekit.md`)
- **CSRF protection**: SvelteKit's built-in CSRF checks fire after guard checks — guard doesn't skip CSRF
