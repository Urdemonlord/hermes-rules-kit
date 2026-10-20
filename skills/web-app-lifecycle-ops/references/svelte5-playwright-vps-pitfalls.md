# Svelte 5 Pitfalls & Playwright Testing on VPS

## Svelte 5: `class:` Directive Cannot Live Inside String Class Attribute

**Symptom:** Build fails with `Unexpected token` or `js_parse_error` when using `{class:xxx={...}}` syntax inside a string `class="..."` attribute.

**Wrong (Svelte 5 — BROKEN):**
```svelte
<img class="w-full object-cover transition
    {class:opacity-0={!imgLoaded}}
    {hovered ? 'scale-105' : ''}"
  onload={...} />
```

**Right (Svelte 5 — WORKS):**
```svelte
<img class="w-full object-cover transition {hovered ? 'scale-105' : ''}"
    class:opacity-0={!imgLoaded}
  onload={...} />
```

**Rule:** `class:` is a Svelte directive, NOT a template expression. It must be a separate attribute on the element, never nested inside the string `class` attribute.

---

## Svelte 5: `<a>` Cannot Be Child of `<a>`

**Symptom:** `node_invalid_placement` error — "`<a>` cannot be a child of `<a>`."

**Fix:** Use a SINGLE `<a>` wrapper for the entire card. Do not nest. If you need inner links for different targets, use `<button onclick={...}>` inside the `<a>`, or restructure to avoid nesting.

---

## Playwright Testing: CSRF Blocks `localhost` But Not Domain

When testing a SvelteKit app deployed with `ORIGIN=https://example.com`:
- `curl` POST to `http://127.0.0.1:3301/login` → 403 "Cross-site POST form submissions are forbidden"
- Playwright to `http://127.0.0.1:3301` → same 403 on form submits
- Playwright to `https://example.com` (via nginx) → WORKS

**Fix:** Always test through the real domain when CSRF is active. Use `page.goto("https://example.com")` not `http://127.0.0.1:PORT`.

---

## Playwright: `button[type='submit']` Collision with Footer Forms

When a page has multiple forms (login form + newsletter footer), `page.locator("button[type='submit']")` resolves to 2+ elements. Always scope to the specific form:

```python
form = page.locator("main form").first  # or #login-form
form.locator("button[type='submit']").click()
```

---

## Docker Build: Disk Space

**Symptom:** `no space left on device` during `docker compose up --build`.

**Pre-build cleanup:**
```bash
docker system prune -af    # removes unused images/containers
docker builder prune -af   # removes build cache
df -h /                    # verify > 5GB free before building
```

---

## CSP: Adding Google Fonts to SvelteKit

```typescript
// hooks.server.ts — CSP header
"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
"font-src 'self' https://fonts.gstatic.com",
```

---

## DB Credentials: Seed File ≠ Running DB

The `prisma/seed.ts` may contain different credentials than the actual Docker volume database. Always verify with:

```bash
docker cp container-name:/data/dev.db /tmp/db-check.db
sqlite3 /tmp/db-check.db "SELECT email, role FROM User LIMIT 5;"
```
