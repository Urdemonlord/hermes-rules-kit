# Next.js/Vercel Passive Triage Notes

Use these notes when assessing public Next.js sites hosted on Vercel.

## Common fingerprints
- `server: Vercel`
- `x-powered-by: Next.js`
- `/_next/static/...` assets and `__next_f`/RSC payloads in HTML
- `sitemap.xml` often reveals real route slugs even when pages are not linked in navigation
- `robots.txt` may list disallowed admin/profile/dashboard paths

## Important interpretation pitfall
- A request to a sensitive-looking path such as `/admin`, `/profil`, or `/vendor/dashboard` can return **HTTP 200** while still rendering the public homepage shell.
- Do **not** treat 200 as proof the panel is exposed.
- Verify by checking:
  - `<title>`
  - `meta name="robots"`
  - visible `<h1>` or route-specific labels
  - presence of route-specific auth/admin elements
  - whether the HTML differs materially from the homepage

## Good follow-up probes
- Compare page title/content for the candidate route against `/`
- Check `robots.txt` and `sitemap.xml` for route discovery only
- Look for route-specific assets or API calls in the HTML/RSC payload
- Confirm with authenticated or source-assisted inspection only if ownership is established

## Session example
- `vertesen.id` returned `server: Vercel`, `x-powered-by: Next.js`, `robots.txt` with `Disallow: /admin`, `/profil`, `/vendor/dashboard`, and `sitemap.xml` exposing many vendor slugs.
- `/admin`, `/profil`, and `/vendor/dashboard` all returned 200 but rendered the same public homepage shell, so status code alone was insufficient to judge exposure.
