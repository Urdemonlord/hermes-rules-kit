---
name: sveltekit-auth-forms-brand
description: Brand-first SvelteKit auth pages (login, register, forgot-password). Input/button/link styling with warm palettes, top-aligned layout, explicit disabled states. Load for any e-commerce auth redesign.
triggers:
  - "auth page design"
  - "login page"
  - "register page"
  - "forgot password"
  - "auth form styling"
  - "form contrast"
  - "disabled button"
---

# SvelteKit Auth Pages — Brand-First Design

Auth pages are trust moments. Generic form UI erodes brand. This skill defines patterns for premium e-commerce (fashion, artisan, luxury) auth experiences.

## Core Pattern: Top-Aligned, Not Centered

**PROBLEM:** Centered layout (`items-center justify-center`) wastes ~50% of mobile viewport above the form. Users must scroll past blank space to interact.

**SOLUTION:** Top-aligned with gentle margin:

```svelte
<main class="min-h-screen flex flex-col px-4 bg-bg">
  <div class="w-full max-w-md mx-auto mt-16 sm:mt-20">
    <!-- Form content -->
  </div>
</main>
```

`mt-16` = 64px (mobile), `sm:mt-20` = 80px (desktop). Form is **immediately visible** on mobile without scroll.

## Brand Identity Layer

Three lines, centered, restrained:

```svelte
<h1 class="font-display text-3xl font-bold text-center mb-1 text-ink">BRAND NAME</h1>
<p class="text-center text-sm text-muted mb-2">Brand tagline or origin</p>
<p class="text-center text-muted mb-8">Page intent (Masuk ke akun / Buat akun baru)</p>
```

**Tagline examples:**
- "Warisan Tenun Jepara untuk Perempuan Modern" (ALAIR Ethnic)
- "Fashion Etnik Premium Indonesia"
- "Keanggunan dalam Setiap Helai"

**Why 3 lines?** The first line is brand name (non-negotiable). The second is *brand story* in one phrase (not a generic tagline like "The future of X"). The third is the page action. This stack occupies ~120px and establishes trust before form interaction begins.

## Input Field Styling (Warm Palette)

Inputs must **stand out** from light `#F5F0E8` backgrounds. Use warm off-white + soft border + focus accent:

```
Background:    #FCFAF6 (slightly warmer than page bg)
Border:        #D8CDBB (warm tan, 2px visual weight)
Focus border:  brand-gold (#C59A58)
Focus ring:    ring-1 ring-[#C59A58]/30 (subtle glow)
```

Full class:
```svelte
<input
  type="email"
  class="w-full px-4 py-3 bg-[#FCFAF6] border border-[#D8CDBB] rounded-lg
  focus:outline-none focus:border-[#C59A58] focus:ring-1 focus:ring-[#C59A58]/30
  transition placeholder:text-muted/50"
  placeholder="user@example.com"
/>
```

**Label spacing:** `mb-1.5` (not `mb-2`). Tighter spacing groups label + input visually.

**Placeholder usage:** Always provide context:
- Email: `placeholder="user@example.com"`
- Password: `placeholder="••••••••"`
- Name: `placeholder="Nama Anda"`

## Button Styling

**Active (normal) state:**
```svelte
<button class="bg-[#C59A58] text-white hover:bg-[#D4A96A] transition">
  Masuk
</button>
```

Hover color: `#D4A96A` (gold + 10% lighter). Smooth color transition.

**Disabled state (loading):**
```svelte
<button disabled={loading}
  class="bg-[#C59A58] text-white hover:bg-[#D4A96A] transition
  disabled:bg-[#DDD3C5] disabled:text-[#8E8478] disabled:cursor-not-allowed">
  {loading ? 'Masuk...' : 'Masuk'}
</button>
```

Disabled colors:
- Background: `#DDD3C5` (light warm gray)
- Text: `#8E8478` (darker brown, still readable)
- Cursor: `not-allowed` (visual signal)

**WHY NOT `opacity-50`?** On light pages, `opacity-50` makes buttons nearly invisible. Explicit color swap is always readable and intentional.

## Link Styling

All secondary actions (auth link switch, forgot password) use brand gold + underline on hover:

```svelte
<!-- Below password field -->
<div class="text-right mt-1.5">
  <a href="/forgot-password" class="text-xs text-[#C59A58] hover:underline font-medium">
    Lupa password?
  </a>
</div>

<!-- Below form -->
<p class="text-center text-sm text-muted mt-6">
  Belum punya akun?
  <a href="/register" class="text-[#C59A58] font-medium hover:underline">
    Daftar
  </a>
</p>
```

**Consistency:** Every auth-related link uses the same treatment (gold + underline). No exceptions.

## Error Display

```svelte
{#if form?.error}
  <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4 text-sm">
    {form.error}
  </div>
{/if}
```

Placed ABOVE the form, inside the max-w-md container. Inline errors (red text below inputs) are acceptable only for field-level validation, not form-level failures.

## Cross-Page Consistency

Login, register, and forgot-password pages must share:

- **Top spacing:** `mt-16 sm:mt-20`
- **Brand tagline:** Identical line 2
- **Input styling:** Identical bg/border/focus across all forms
- **Button styling:** Identical colors and disabled states
- **Link treatment:** Identical gold + underline

This creates a cohesive auth flow where users feel they're navigating a single branded experience, not three separate pages.

## Config Anchor: Location

Check `$lib/config.ts` before shipping. Auth pages often reference brand location in footer or tagline:

```typescript
export const CONTACT = {
  city: 'Jepara',  // NOT 'DKI Jakarta' default
  address: 'Jepara',
  // ...
}
```

**Pitfall:** New projects copy boilerplate config with Jakarta placeholder. Always audit `CONTACT` object — it flows into page footers, brand stories, and shipping logic. Mismatch (e.g., "Warisan Tenun Jepara" + footer "DKI Jakarta") breaks credibility.

## Mobile Collapse

All auth pages are single-column on `< md:` (< 768px):

```svelte
<div class="w-full max-w-md mx-auto">
  <!-- w-full ensures full horizontal breathing room -->
  <!-- max-w-md caps width at 448px on desktop -->
  <!-- mx-auto centers the block -->
</div>
```

Test on actual mobile viewport (375px width). Form should not feel cramped.

## Pitfalls & Preventions

| Pitfall | Prevention |
|---------|-----------|
| Centered layout wastes mobile space | Use `mt-16 sm:mt-20` top-aligned instead |
| Disabled button becomes invisible on light bg | Always set explicit `disabled:bg-[#DDD3C5] disabled:text-[#8E8478]` |
| Generic tagline erodes brand trust | Use origin location or brand heritage (e.g., "Warisan Tenun Jepara") |
| Config city doesn't match brand origin | Audit `$lib/config.ts` CONTACT.city before shipping |
| Input doesn't stand out from page bg | Use `bg-[#FCFAF6]` (warm) + `border-[#D8CDBB]` (visible) combo |
| Links look like plain text | Always use `text-[#C59A58] font-medium hover:underline` consistently |
| Form labels feel disconnected from inputs | Use `mb-1.5` (tighter than `mb-2`) to group visually |

## References

- ALAIR Ethnic v7 auth pages (August 2026): login/register redesign with warm palette, top-aligned layout, brand tagline layer
- the client site auth pages: same pattern applied to heritage craft fashion storefront
