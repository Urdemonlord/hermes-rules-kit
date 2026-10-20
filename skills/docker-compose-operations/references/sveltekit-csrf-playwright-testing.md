# Playwright Testing Against SvelteKit in Docker

## The CSRF Problem

SvelteKit's CSRF protection runs on every form-content-type POST. When running Playwright against `127.0.0.1:PORT` but the container's `ORIGIN` points to a production domain, all POSTs are 403'd.

`page.evaluate(fetch())` from within the page context does NOT bypass CSRF — the browser still sends `Origin: http://127.0.0.1:PORT` which doesn't match `ORIGIN`.

## Two Approaches

### Approach A: `page.evaluate(fetch())` — for actions that don't set cookies

Good for: register (you follow redirect yourself), cart add, any action that doesn't require session state.

```python
r = page.evaluate('''async () => {
    const fd = new URLSearchParams({name:'Test', email:'user@example.com', password:'pass123'});
    const resp = await fetch('/register', {
        method: 'POST',
        body: fd,
        headers: { 'x-sveltekit-action': 'true', 'accept': 'application/json' },
        redirect: 'manual'
    });
    const text = await resp.text().catch(() => '');
    let data = null;
    try { data = JSON.parse(text); } catch(e) {}
    return { status: resp.status, data };
}''')
if r.get('data', {}).get('type') == 'redirect':
    page.goto(f'{BASE}{r["data"]["location"]}', wait_until='networkidle')
```

**Limitation**: `fetch()` does NOT persist `Set-Cookie` headers to the browser context. After register via fetch, `page.goto('/cart')` may show the user as not logged in.

### Approach B: `f.submit()` — for actions that set cookies

Good for: register (with auto-login), login, checkout (any flow that creates a session).

```python
# Register — native form submit sets cookies + follows redirect
page.fill('input[name="email"]', 'user@example.com')
page.fill('input[name="password"]', 'pass123')
with page.expect_navigation(wait_until='networkidle', timeout=15000):
    page.evaluate('() => document.querySelector("form").submit()')
# Now page has session cookies — subsequent page loads include auth
```

**Why `page.evaluate()` + `f.submit()` instead of Playwright's `page.click('button[type=submit]')`**: Both work, but `evaluate` + submit is reliable when `use:enhance` intercepts clicks. With `use:enhance`, SvelteKit's JS handles the submit client-side (fetch), so Playwright never sees the actual POST. The `evaluate(f.submit())` call bypasses SvelteKit's JS and does a native browser form POST.

## Key Gotchas

### Named actions require `?/actionName` in URL
```python
# Cart add action is named "add" in cart/+page.server.ts
# Form action: /cart?/add (NOT /cart)
r = page.evaluate('''async () => {
    const fd = new URLSearchParams({productId: 'xxx', quantity: '1', variantId: ''});
    const resp = await fetch('/cart?/add', { ... });
    return await resp.json();
}''')
```

### Extract productId from hidden input (not from URL slug)
```python
# Product URL: /products/puspa-dress (slug)
# But cart add needs DB UUID: cPPGZL0092mIaePWh
real_id = page.eval_on_selector('input[name="productId"]', 'el => el.value')
```

### SvelteKit form action responses (when using `accept: application/json`)
- **Success redirect**: `{ "type": "redirect", "location": "/order/xxx" }`
- **Success data**: `{ "type": "success", "data": {...} }`
- **Validation failure**: `{ "type": "failure", "status": 400, "data": {...} }`
- **Error**: `{ "type": "error", "status": 500 }`

### After POST, page state is stale
The `page.evaluate(fetch())` doesn't update the DOM. Navigate explicitly:
```python
page.goto(f'{BASE}/cart', wait_until='networkidle')
```

### Redirect after form action
For `use:enhance` forms, SvelteKit handles redirects client-side. When using raw `fetch()`, handle manually:
```python
if r.get('data', {}).get('type') == 'redirect':
    page.goto(f'{BASE}{r["data"]["location"]}', wait_until='networkidle')
```

### Login page redirects when already logged in
SvelteKit `load` function in login `+page.server.ts` often has:
```ts
if (locals.user) throw redirect(302, '/')
```
Testing login requires a fresh browser context (separate from the register flow).

### Input selectors may lack `id` attribute
SvelteKit forms often use `name` only:
```python
# NOT: page.fill('#email', ...) — #email may not exist
page.fill('input[name="email"]', TEST_EMAIL)
page.fill('input[name="password"]', TEST_PASS)
```

### Rate limiter (in-memory) blocks rapid retries
Many SvelteKit apps use in-memory rate limiting. Rapid test retries get 403/429.
```bash
# Clear rate limiter by restarting the container
docker restart <container>
sleep 4
# Re-run test
```

### Hidden fields need explicit setting for forms with autocomplete
Checkout forms often have hidden `province` fields set by city autocomplete dropdown. If you don't trigger the autocomplete, the hidden field stays empty and server validation fails.
```python
page.evaluate('''() => {
    document.querySelector('input[name="province"]').value = 'DKI Jakarta';
}''')
```

## Full test flow template (hybrid approach)

```python
import os, json
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
from datetime import datetime

BASE = 'http://127.0.0.1:3301'
SCREENSHOTS = '/tmp/test-ss'
TEST_EMAIL = f'test_{datetime.now().timestamp():.0f}@test.local'
TEST_PASS = 'testpass123'
TEST_NAME = 'Test Buyer'

os.makedirs(SCREENSHOTS, exist_ok=True)
ss_count = [0]
def ss(page, name):
    ss_count[0] += 1
    p = f'{SCREENSHOTS}/{ss_count[0]:02d}-{name}.png'
    page.screenshot(path=p, full_page=True)
    print(f'  📸 {p}')

def action_fetch(page, url, data):
    """Submit SvelteKit action from page context."""
    fd = json.dumps(data)
    return page.evaluate(f'''async () => {{
        const fd = new URLSearchParams({fd});
        const r = await fetch('{url}', {{
            method:'POST', body:fd,
            headers:{{'x-sveltekit-action':'true','accept':'application/json'}},
        }});
        const t = await r.text().catch(()=>'');
        let d = null;
        try{{d=JSON.parse(t);}}catch(e){{}}
        return {{status:r.status, data:d}};
    }}''')

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
        page = ctx.new_page()

        # ── REGISTER (native submit — sets cookies) ──
        page.goto(f'{BASE}/register', wait_until='networkidle')
        page.fill('input[name="name"]', TEST_NAME)
        page.fill('input[name="email"]', TEST_EMAIL)
        page.fill('input[name="password"]', TEST_PASS)
        with page.expect_navigation(wait_until='networkidle', timeout=15000):
            page.evaluate('() => document.querySelector("form").submit()')
        print(f'  Register -> {page.url}')

        # ── PRODUCTS ──
        page.goto(f'{BASE}/products', wait_until='networkidle')
        links = page.eval_on_selector_all('a[href^="/products/"]',
            'els => els.map(l => l.href).filter(h => !h.endsWith("/products"))')
        page.goto(links[0], wait_until='networkidle')

        # ── ADD TO CART (fetch — no cookie needed) ──
        real_id = page.eval_on_selector('input[name="productId"]', 'el => el.value')
        r = action_fetch(page, '/cart?/add', {'productId': real_id, 'quantity': '1', 'variantId': ''})
        print(f'  Cart add: {r["data"].get("type")}')

        # ── CHECKOUT (native submit — needs redirect + payment) ──
        page.goto(f'{BASE}/checkout', wait_until='networkidle')
        page.fill('input[name="name"]', TEST_NAME)
        page.fill('input[name="phone"]', '081234567890')
        page.fill('textarea[name="address"]', 'Jl. Test No. 1')
        page.fill('input[name="zip"]', '10110')
        # Set hidden fields
        page.evaluate('''() => {
            document.querySelector('input[name="province"]').value = 'DKI Jakarta';
            document.querySelector('input[name="shipping_cost"]').value = '15000';
        }''')
        with page.expect_navigation(wait_until='networkidle', timeout=20000):
            page.evaluate('() => document.querySelector("form").submit()')
        print(f'  Checkout -> {page.url}')

        # ── LOGIN (fresh context — separate session) ──
        ctx2 = browser.new_context(viewport={'width': 1280, 'height': 900})
        pg2 = ctx2.new_page()
        pg2.goto(f'{BASE}/login', wait_until='networkidle')
        pg2.fill('input[name="email"]', TEST_EMAIL)
        pg2.fill('input[name="password"]', TEST_PASS)
        with pg2.expect_navigation(wait_until='networkidle', timeout=15000):
            pg2.evaluate('() => document.querySelector("form").submit()')
        print(f'  Login -> {pg2.url}')
        ctx2.close()

        browser.close()

if __name__ == '__main__':
    main()
```

## ORIGIN env var: runtime vs build-time

| Change type | Requires rebuild? | Command |
|-------------|-------------------|---------|
| `ORIGIN` env var | No | `docker restart <container>` |
| `trustedOrigins` in svelte.config.js | Yes | `docker compose build --no-cache && docker compose up -d --build` |
| Source code changes | Yes | `docker compose build && docker compose up -d --build` |
| In-container `sed` patch to built JS | No | `docker restart <container>` |
