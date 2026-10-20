# Verifying Interactive UI That SSR Never Renders

Screenshots exist to close a verification gap that `curl` cannot. That gap is almost always
the same: **content behind a tab, a client-side condition, or a closed `<select>`** — none of
which appear in the server's HTML.

## The three-surface rule

A UI change (pruning dropdown options, removing a widget, restricting a list) must be proven
on all three surfaces or not proven at all:

1. **SSR branch** — `curl` the page, grep the served markup. Proves only the branch that
   renders on load.
2. **Client bundle** — grep `build/client/_app/immutable/nodes/` for the option map. This is
   what renders after hydration and what the user clicks.
3. **Behaviour** — drive a real browser: click the tab, open the select, screenshot it.

Surface 3 is the only one that catches a control that renders but holds stale or unexpected
options. A page returning a plausible 11 KB of HTML with zero `<option>` tags is the tell that
the content is behind a tab, not that it is missing.

## Screenshot ≠ assertion — do both

A vision model reading a screenshot **cannot see the contents of a closed `<select>`**; it
reports only the currently-selected value, which is often the unchanged default and therefore
proves nothing about the option set. Always assert the option list programmatically in the same
run, then screenshot for the human-facing record:

```js
const opts = await page.$$eval('select option', els => els.map(e => e.value));
console.log('courier options =', JSON.stringify(opts));
console.log('turnstile elements =', await page.$$eval('.cf-turnstile, iframe[src*="turnstile"]', e => e.length));
```

Print both. The log is the proof; the PNG is the evidence.

## Puppeteer traps that cost a full iteration each

| Symptom | Cause | Fix |
|---|---|---|
| `page.waitForTimeout is not a function` | that is a Playwright API | `const sleep = ms => new Promise(r => setTimeout(r, ms))` |
| `waitForNavigation` times out after a form click | the form uses `use:enhance` — no full navigation happens | `await page.click(sel); await sleep(4000)` |
| `goto` times out on `networkidle0` | analytics/websocket keeps ≥1 connection open forever | `waitUntil: 'domcontentloaded'` + explicit sleep |
| viewport appears ignored | `newContext()` called without `viewport`, or `newPage()` called on a context | `browser.newPage()` then `page.setViewport({width:1440,height:900})` |

Launch with `--no-sandbox --disable-setuid-sandbox --disable-dev-shm-usage` on a VPS/container.

## Dismiss overlays before capturing

A promo/newsletter modal renders over the target element and makes the screenshot unusable —
the DOM assertions still pass, so a careless pass ships an unreadable image.

**Preferred — seed the dismissal flag before the page ever loads.** Dismiss-on-click popups
normally record a timestamp in `localStorage` and reappear after a cooldown (often 24h), so
clicking the close button only helps for that one browser session:

```js
await page.evaluateOnNewDocument(() => {
  try { localStorage.setItem('iki_promo_dismissed', String(Date.now())); } catch {}
});
```

Read the component source first — `grep -rn 'aria-modal\|role="dialog"' src/lib/components/`
finds the popup, and its `shouldShow()` reveals both the key and the TTL. Seeding beats clicking
because it survives every later `goto`, and it does not depend on the button having readable
text (promo close buttons are usually icon-only SVGs carrying only an `aria-label`).

Fallback when the flag is unknown or the popup is server-rendered: click it before capturing,
matching on `aria-label` as well as text.

```js
async function closeModal(page) {
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll('button, [role="dialog"] button')];
    const hit = btns.find(b => /lewati|tutup|close|skip|✕/i.test(b.textContent.trim())
      || /tutup|close/i.test(b.getAttribute('aria-label') || ''));
    hit?.click();
  });
  await sleep(800);
}
```

**Then look at the PNG before reporting.** Vision analysis is the only check that catches an
overlay — every programmatic assertion will pass over a covered element.

## An in-memory rate limiter will block the re-run

Browser verification often needs the same authenticated login several times (one per page under
test). An in-memory limiter — the common pattern for login throttling — has no shared store, so
each attempt consumes a slot and the script eventually screenshots a 429 page instead of the app.
Restarting the scratch container clears the map:

```bash
docker restart <scratch-container>
```

Check the response before assuming the page under test is broken: a login page that suddenly
renders "Terlalu banyak percobaan" is the limiter, not a regression.

## Ordering that avoids the re-run entirely

1. Start the scratch container, seed it.
2. Create the fixture rows (order, user) once via the API.
3. Log in via the browser **once**; reuse the browser session for every page.
4. Dismiss overlays, assert programmatically, screenshot.
5. Restart the container to clear the limiter before any *second* script run.
