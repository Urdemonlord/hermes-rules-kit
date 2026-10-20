# Brand Migration / Rebrand Cleanup — SvelteKit Projects

When forking or cloning a SvelteKit project for a new brand, old references hide in
surprising places. This checklist ensures zero residual old-brand content.

## Full Scan Order (in session-seen failure order)

### 1. `src/lib/config.ts` (CENTRAL — check first)

The config object is the single source for site name, contact info, social links.
Other files reference it.

```
SOCIAL: { instagram, tiktok, whatsapp, shopee, tokopedia, ... }
CONTACT: { email, phone, address, city }
SITE: { name, domain }
```

**Pitfall:** Config may export social keys (e.g. `tokopedia`) that no component
references — or omit keys (e.g. `tiktok`) that the footer/contact page tries to
use. After changing config, grep all files that import `SOCIAL` and verify the
keys they reference still exist.

### 2. `static/robots.txt`

Static files win over `src/routes/robots.txt/+server.ts` in SvelteKit.
If both exist, the static file is what users/Googlebot see.

**Fix:** Pick one source, delete the other. Static is simpler (no server needed).

### 3. `src/routes/sitemap.xml/+server.ts`

Often has a hardcoded `const BASE = 'https://old-domain...'`.

### 4. `src/routes/contact/+page.svelte`

May have hardcoded email, phone, social links. Look for:
- Direct email strings (not from config)
- Social link references (may reference non-existent SOCIAL keys)

### 5. `prisma/seed.ts`

Seed data often contains:
- Old admin email and name
- Old container names in comments (docker exec instructions)
- Old passwords (less critical if not committed, but visible in comments)

### 6. Comments and documentation files

```
grep -rn "old-container\|old-domain\|old-admin" prisma/ src/ scripts/ docs/
```

## Session: the client site → ALAIR Ethnic

Found in brand-site codebase:

| File | Reference | Fix |
|---|---|---|
| `src/lib/config.ts` | `wa.me/628121234567`, `@brand-site` (wrong TikTok) | Updated to correct social URLs |
| `src/lib/components/layout/Footer.svelte` | No TikTok link | Added TikTok to footer |
| `static/robots.txt` | `client-site.meowlabs.id/sitemap.xml` | Updated to brand-site |
| `src/routes/robots.txt/+server.ts` | `client-site.meowlabs.id` | DELETED (static wins) |
| `src/routes/sitemap.xml/+server.ts` | `const BASE = 'https://client-site.meowlabs.id'` | Updated to brand-site |
| `src/routes/contact/+page.svelte` | `user@example.com`, `SOCIAL.tokopedia` (missing) | Use `CONTACT.email`, removed tokopedia |
| `prisma/seed.ts` | `user@example.com`, `Admin the client site`, `iki-tenun-app-1` | Updated all to brand-site |

**Key lesson:** `docker restart` does NOT apply new image — it restarts old
container. Must `docker compose down` + `docker compose up -d` (or
`--force-recreate`) to use newly built image. `docker compose build` + `docker
restart` = old code persists.
