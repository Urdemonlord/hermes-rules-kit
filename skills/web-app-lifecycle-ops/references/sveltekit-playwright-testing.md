# SvelteKit Browser Testing with Playwright

## The ORIGIN / CSRF trap

SvelteKit's adapter-node enforces CSRF by checking the `Origin` header against
the `ORIGIN` environment variable. When testing a deployed container via
`http://127.0.0.1:3301` but the container has `ORIGIN=https://domain.com`, **all
form POSTs return 403 "Cross-site POST form submissions are forbidden"**.

### Symptoms
- Playwright form fills and clicks work, but page stays on same route after submit
- No error message visible on page (SvelteKit `use:enhance` swallows the 403)
- Console shows `Failed to load resource: 403`

### Fix: test via domain
```python
# Wrong — CSRF blocks
BASE = "http://127.0.0.1:3301"

# Right — goes through nginx, Origin header matches
BASE = "https://client-site.meowlabs.id"
```

### Alternative: override ORIGIN in compose.yaml
```yaml
environment:
  - ORIGIN=http://127.0.0.1:3301  # allow local testing
```

## Playwright setup on headless VPS

```bash
uv pip install playwright
python3 -m playwright install chromium   # ~115MB download
```

No Xvfb needed — Playwright's headless mode works without a display server.

## Multiple submit buttons: strict mode pitfall

SvelteKit pages often have multiple `<form>` elements (e.g. login form in main,
newsletter form in footer). Both may have `<button type="submit">`. Playwright's
strict mode will throw `Error: strict mode violation` when `page.locator("button[type='submit']")`
matches 2+ elements.

### Fix: scope to the target form
```python
# Wrong — ambiguous
page.locator("button[type='submit']").click()

# Right — scope to the form you're targeting
login_form = page.locator("main form").first
login_form.locator("button[type='submit']").click()
```

Or use `get_by_role` with name:
```python
page.get_by_role("button", name="Masuk").click()
```

## Debugging SvelteKit auth failures

When login/register succeeds on the server but the browser stays on the same page:

1. **Check CSRF first** — raw fetch will show "Cross-site POST form submissions are forbidden"
2. **Check `use:enhance` errors** — add `page.on("console", ...)` and `page.on("pageerror", ...)` listeners
3. **Inspect network** — `page.on("response", lambda r: print(r.status, r.url))`
4. **Verify password hash** — copy DB from container and test with `compareSync`:

```bash
docker cp container:/data/dev.db /tmp/db-check.db
node -e "
const {compareSync} = require('bcryptjs');
const dbHash = '$(sqlite3 /tmp/db-check.db "SELECT passwordHash FROM User WHERE email=\"user@example.com\";")';
console.log(compareSync('attempted-password', dbHash));
"
```

## SvelteKit `use:enhance` vs Playwright

`use:enhance` submits forms via `fetch()` with JavaScript. Playwright executes
JavaScript, so enhanced forms work normally — BUT the redirect (302) from a
successful action is handled by SvelteKit's client-side router, not by a browser
navigation. Use `page.wait_for_url()` or check `page.url` after a short wait.

```python
form.locator("button[type='submit']").click()
page.wait_for_timeout(3000)
assert "login" not in page.url  # redirected away = success
```

## Common SvelteKit production quirks

### CSP blocks Google Fonts
SvelteKit production CSP set in `hooks.server.ts` typically has `style-src 'self'
'unsafe-inline'` and `font-src 'self'`. External font services
(fonts.googleapis.com, fonts.gstatic.com) get blocked. In headless Playwright
this means custom fonts won't load (fall back to system serif).

Fix in `hooks.server.ts`:
```ts
"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
"font-src 'self' https://fonts.gstatic.com",
```

### Admin dashboard rendering
Some SvelteKit SPAs render the layout shell even when a route/page has no
content. If the admin dashboard shows "404" text but the nav sidebar works,
check if the admin home route (`/admin/+page.svelte`) exists or if it's falling
through to the root `+error.svelte`.
