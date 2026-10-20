# SvelteKit Centralized Site Config Pattern

## Problem
Hardcoded social media URLs, phone numbers, email addresses, and addresses scattered across 7+ files (Footer, Contact, About, layout components, etc.). When these change, every file must be found and updated individually — error-prone and time-consuming.

## Solution
Single configuration file (`$lib/config.ts`) with all business-specific constants. Imported everywhere via SvelteKit's path alias.

## Implementation

### 1. Config file (`src/lib/config.ts`)
```typescript
export const SITE = {
  name: 'the client site',
  tagline: 'Tenun Ikat Premium dari Jepara',
  domain: 'example.com',
} as const

export const CONTACT = {
  address: 'Pecangaan, Kab. Jepara',
  city: 'Jawa Tengah',
  zip: '59462',
  phone: '+62 812-2515-8035',
  phoneRaw: '6281225158035',
  email: 'user@example.com',
} as const

export const SOCIAL = {
  instagram: 'https://www.instagram.com/client-site/',
  tokopedia: 'https://www.tokopedia.com/seller',
  shopee: 'https://s.shopee.co.id/xxx',
  tiktok: 'https://vt.tiktok.com/xxx/',
  whatsapp: `https://wa.me/${CONTACT.phoneRaw}`,
  googleMaps: 'https://maps.app.goo.gl/xxx',
  googleMapsEmbed: 'https://www.google.com/maps?q=...',
} as const

export const BRAND = {
  instagramFollowers: '161K+',
  tokopediaRating: '4.9★',
  est: 2020,
} as const
```

### 2. Usage in components
```svelte
<script lang="ts">
  import { CONTACT, SOCIAL, SITE } from '$lib/config'
</script>

<!-- Old: hardcoded -->
<a href="https://www.instagram.com/iki.tenun/">Instagram</a>
<span>Pecangaan, Kab. Jepara</span>

<!-- New: config-driven -->
<a href={SOCIAL.instagram}>Instagram</a>
<span>{CONTACT.address}</span>
```

## Benefits
- **Single source of truth**: update once → reflected everywhere
- **Type-safe**: `as const` gives autocomplete in editors
- **Build-time**: no runtime cost — SvelteKit resolves imports at compile time
- **Documentation**: the config file serves as documentation of all business info

## When to Use
- Any storefront/franchise/business website with repeated contact/social info
- Multi-page sites where the same phone/WA number appears in 5+ places
- Projects that may change social media handles or business addresses
