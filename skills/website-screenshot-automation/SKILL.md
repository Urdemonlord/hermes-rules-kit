---
name: website-screenshot-automation
description: "Capture website screenshots with Puppeteer or Playwright (headless Chrome) — setup, scripting patterns, verification. Use when user asks to screenshot a website, take page captures, get full-page screenshots, or capture viewport-specific screenshots of any URL."
tags: [puppeteer, playwright, screenshots, headless-chrome, verification, web-testing]
related_skills: []
---

# Website Screenshot Automation

Capture website screenshots using Puppeteer or Playwright (headless Chrome). Covers setup, scripting patterns, and verification.

## Tool Choice

| | Puppeteer (Node) | Playwright (Python) | Raw CDP (no deps) |
|---|---|---|---|
| Install | `cd /tmp && npm install puppeteer` + `npx puppeteer browsers install chrome` | `pip install playwright && playwright install chromium` | none — needs a Chromium already on disk |
| Pros | Huge ecosystem, inline one-liners via `--input-type=module` | Simpler API, Python's async is cleaner for multi-page loops, browsers often pre-installed in hermes venv | Zero install, and `Network.setExtraHTTPHeaders` gets past `auth_basic` (Chrome rejects creds in URLs since v88) |
| Pitfalls | Postinstall silent failure; `readFileSync` magic-byte trap | Node.js `npx playwright` can have version mismatch with cached browsers (use Python API instead) | Hand-rolled; only worth it when a browser binary already exists |

**Recommendation**: If Python venv is active, use Python Playwright — avoids Node/npm setup. Fall back to Puppeteer when user requests JS. When neither is installed but a cached Chromium exists, use `scripts/cdp-shot.mjs` rather than installing anything.

## Setup — Playwright (Python)

```bash
playwright install chromium  # usually pre-installed in hermes venv
```

## Script Pattern — Playwright (Python)

```python
import asyncio
from playwright.async_api import async_playwright

urls = [
    ('https://example.com', '/tmp/output.png', 'Page Name'),
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={'width': 1440, 'height': 900})
        for url, out, name in urls:
            page = await ctx.new_page()
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)
            await page.screenshot(path=out, full_page=True)
            await page.close()
        await browser.close()

asyncio.run(main())
```

Run with: `/home/user/.hermes/hermes-agent/venv/bin/python script.py`

Note: `networkidle` in Playwright = `networkidle2` equivalent in Puppeteer (allows 2 connections). For strict idle use `wait_until='networkidle'` which waits until ≤0 connections for 500ms.

## Setup — Puppeteer (Node.js)

```bash
cd /tmp && npm install puppeteer
npx puppeteer browsers install chrome  # manual install if postinstall skips
```

Postinstall sometimes fails silently. Always verify chrome binary exists before running.

## Script Pattern — Puppeteer (Node.js)

### Quick inline (no file needed)

For one-off screenshots, skip writing a file — use `--input-type=module`:

```bash
cd /tmp && node --input-type=module -e "
import puppeteer from 'puppeteer';
const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
await page.goto('https://example.com', { waitUntil: 'networkidle0', timeout: 60000 });
await new Promise(r => setTimeout(r, 3000));
await page.screenshot({ path: '/tmp/output.png', fullPage: true });
await browser.close();
"
```

### File-based (multi-page captures)

```javascript
import puppeteer from 'puppeteer';

const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });

// Full-page screenshot
await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });
await new Promise(r => setTimeout(r, 3000)); // settle time
await page.screenshot({ path: '/tmp/output.png', fullPage: true });

// Viewport-only screenshot
await page.screenshot({ path: '/tmp/output.png', fullPage: false });

// Scroll-to-bottom then full-page capture
await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await new Promise(r => setTimeout(r, 1500));
await page.screenshot({ path: '/tmp/output.png', fullPage: true });

await browser.close();
```

### Key Parameters (Puppeteer)
- `waitUntil: 'networkidle0'` — wait until NO network activity for 500ms (strict, use by default). `'networkidle2'` allows 2 connections — use only for SPAs with persistent WS/SSE.
- `headless: 'new'` — newer Chrome headless, more compatible than `true`.
- `+ 3000ms settle` — production sites need this for fonts, animations, lazy load. 2000ms is often too short.
- `--no-sandbox --disable-setuid-sandbox` — required for root/container environments
- `--disable-dev-shm-usage` — prevents /dev/shm exhaustion on small containers

## Verification

Quick shell check (preferred):
```bash
file /tmp/output.png && ls -lh /tmp/output.png
```
Confirms valid PNG with dimensions and size. `file` parses PNG headers correctly.

Python PIL check for precise dimensions:
```python
from PIL import Image
img = Image.open(path)
print(f'{img.size} {img.mode}')
```

## Pitfalls

1. **Node.js Playwright version mismatch**: `npx playwright` may expect a different browser version than what's cached (e.g., expects 1243 but 1223 is installed). Use Python Playwright API instead — browsers match the pip-installed version.

2. **Buffer magic-byte comparison (Puppeteer)**: `readFileSync().slice(0,4).toString()` does NOT work — it produces mojibake for non-ASCII bytes. Use byte-level comparison: `buf[0] === 0x89 && buf.slice(1,4).toString('ascii') === 'PNG'`.

3. **Postinstall silent failure (Puppeteer)**: `npm install puppeteer` may warn about unapproved scripts and skip browser download. Always run `npx puppeteer browsers install chrome` explicitly.

4. **Empty/incomplete screenshots**: Production sites with fonts, animations, or lazy loading need ≥2000ms settle after networkidle. For heavy JS apps, bump to 3000-5000ms or add `waitForSelector` for specific content.

5. **Large full-page screenshots**: Some pages have large blank gaps between sections (lazy-loaded content, CSS gaps). This is the page's actual layout — not a capture bug.

6. **Product images with `object-contain`**: When verifying e-commerce screenshots, use vision analysis to confirm product images aren't cropped. The source photo may show partial views — that's upstream, not a CSS issue.

7. **A screenshot cannot prove what is inside a closed `<select>`**: vision reports only the selected value, which is often the unchanged default. Assert the option list with `page.$$eval('select option', ...)` in the same run; the log is the proof, the PNG is the record.

8. **A modal renders over the target and every DOM assertion still passes**: dismiss promo/newsletter overlays by clicking a "Lewati"/"Close" button before capturing, and then actually look at the PNG — vision is the only check that catches the overlay.

9. **Repeated browser logins trip an in-memory rate limiter**: a limiter with no shared store resets on container restart, so `docker restart <scratch>` between script runs instead of debugging the "broken" login page.

10. **`waitUntil: 'networkidle0'` times out on SPAs with `use:enhance` form actions**: a client-side form submit produces no navigation, so `Promise.all([waitForNavigation, click])` hangs forever. Use `waitUntil: 'domcontentloaded'` plus an explicit sleep, then assert the post-action state (URL, a toast selector, an auth-gated element) instead of waiting on a navigation event that will never fire.

11. **Selectors must match what is actually rendered, not what the source implies**: matching a tab by its emoji/label text silently misses when the glyph is split across nodes or the label is a child element, so the click reports `false` and the panel never opens. Prefer structural matching (an `onclick` attribute, a role, a state class) or assert the click succeeded before capturing.

12. **Native-resolution rendering beats downscaling for small-size assets**: rendering one large master and resizing it to each target size produces blurred, anti-aliased edges that look muddy at 16–32px. Draw each size at its own native resolution and scale stroke widths proportionally. Zoom with `Image.NEAREST` before judging — LANCZOS preview hides exactly the pixelation you are checking for.

13. **Distinguish a missing asset from a missing link tag before adding files**: when a browser auto-requests a default path and 404s, check whether the HTML declares the resource. A `<link rel="icon">` pointing at real files makes the default-path 404 irrelevant, because browsers stop auto-requesting it. Verify the declared paths return 200 rather than assuming a same-named file is required. Still ship a real asset at the default path when one is trivial to produce, because link tags are per-page markup and anything that does not parse them (scrapers, plain HTTP clients, some crawlers) hits the default path directly.

14. **A scratch container that fails to bind its port leaves another service answering, and your verification silently measures that service**: `docker run -p 127.0.0.1:3303:3000` can fail with `port is already allocated` while the rest of the script keeps running, so a later `curl http://localhost:3303/favicon.ico` returns 200 from whatever already owned the port. Another project's prod container behind an SSH tunnel is the usual culprit. A passing assertion is then a false proof, which is worse than a crash because it survives into the report. Before trusting any result from a scratch container, confirm the bind succeeded:
```bash
docker run -d --name <probe> -p 127.0.0.1:<port>:3000 ... || exit 1   # do not continue past this
docker ps -a --filter name=<probe> --format '{{.Status}}'              # 'Created' but not 'Up' = bind failed
docker ps -a --format '{{.Names}}\t{{.Ports}}' | grep <port>          # who already owns it
ss -tulpen | grep <port>
```
Pick a port you confirmed free rather than a memorable one, and make the launch failure exit non-zero. When a verification result contradicts an earlier run of the same check, suspect the port before the code.

15. **Establish a baseline from the OLD artifact before claiming the NEW one fixed it**: when verifying that a change removed a symptom, probe the pre-change build first (`docker run ... <old-image>`), then the new one. Now-200 proves the new artifact serves the file; only was-404-then-200 proves the change is what fixed it, and it rules out a stale cache or a leftover container answering.

16. **Check for a cached browser before installing one.** Headless Chrome is frequently already on disk from an earlier task even when no browser binary is on `PATH`:

    ```bash
    find ~/.cache/puppeteer -name 'chrome' -type f 2>/dev/null | head -2
    ls /usr/bin | grep -iE 'chrom|firefox' || echo 'none on PATH'
    ```

    If a cache exists, drive it directly (see the CDP section below) instead of running an install that costs disk and time.

    The same applies to a browser **CLI** whose `PATH` entry is a dangling symlink: a package
    installed globally may link its shim into `~/.npm/_npx/<hash>/...`, and clearing that cache
    leaves `command not found` while the real binary still sits in the package. Look before
    reinstalling:

    ```bash
    ls -la $(command -v <cli>)                                  # 'broken symbolic link to ...'
    ls ~/.hermes/node/lib/node_modules/<pkg>/bin/               # platform binaries, run one directly
    ```

    Invoking `.../bin/<pkg>-linux-x64 --help` costs nothing and answers whether the tool is
    actually present. On a small VPS also check free RAM before launching a browser: a headless
    Chromium plus an already-loaded gateway is the usual reason a capture step gets OOM-killed.

17. **A screenshot proves pixels, never semantics — probe the DOM in the same run.** After a UI rewrite the PNG can look clean while a figure renders `Rp 0` because the code reads a field the API never returns. Capture computed values next to the image and assert on both:

    ```js
    const facts = await evaluate(`JSON.stringify({
      received: t('f-received'),
      rows: document.querySelectorAll('#orders tr').length,
      overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      bg: getComputedStyle(document.body).backgroundColor,
    })`)
    ```

    `scrollWidth - clientWidth` is the horizontal-overflow check that matters for a responsive claim, and it is cheaper and more objective than asking vision whether a table looks cramped. Assert it equals 0 on every viewport you claim to support.

18. **Vision analysis reviews what you built; it cannot verify your own field names.** Vision on a mockup answers "does this look like a dashboard", and will confidently narrate numbers and statuses that were never in the DOM. When reading back live data, assert the API shape first — `typeof(created_at)`, whether a `SUM(CASE ...)` returns an amount or a count, whether a timestamp is ISO or epoch ms — then write the render against what you confirmed. Guessing shapes produces UI that looks right and silently displays zeros.

19. **Assert the value the user receives, not the flag on the container.** `!el.hidden` proves a panel is visible, not that it contains anything — a container shown with an empty field inside reads as working to every automated check and as broken to the user. Assert the payload itself (`value.length`, `value.startsWith(prefix)`, `rows.length`) and pair it with `getComputedStyle(el).display`, because visibility and rendered visibility are different properties. A one-time secret, a generated token, or a copied value is only proven by the string that landed.

20. **Two DOM rules that survive code review and break only on screen.** A `display: flex` / `grid` / any explicit `display` on a container **overrides `[hidden]`**, because the attribute is just a UA-stylesheet default — so set `display` only under `.thing:not([hidden])`. And assigning `textContent` on `<input>` or `<textarea>` creates a text *node* and leaves the value empty; only `.value` writes a form control. Both produce a screenshot that is obviously wrong while every assertion passes.

21. **A browser at loopback is not a browser on the production origin.** The browser sends `Origin: http://127.0.0.1:PORT`, which an allowlist rejects with a correct **403**, and headers that a proxy normally injects are absent, which is a correct **401**. Both look like your new code is broken. Confirm with curl using the real origin before touching anything, then run the flow against a throwaway instance on its own port with its own origin allowlisted, injecting the proxy-supplied header client-side so the token check itself stays exercised. See `references/headless-ui-flow-verification.md`.

22. **A client helper that special-cases one status code hands every other error to the caller as if it were data.** `if (r.status === 401) throw ...; return r.json()` lets a 403 reach a success handler, which then renders from `undefined` — producing "key for undefined" while the guard is doing its job. Throw on every non-2xx using the server's own message, and assert the refusal message in the proof so a correct refusal cannot be mistaken for a broken flow.

23. **Assert cross-layer reachability before calling a feature done, and again before shipping UI for it.** An endpoint plus a passing suite proves nothing about whether anyone can *use* it: grep the presentation layer for the route to confirm something renders it, and grep the server layer for the handler to confirm anything calls it. Zero UI references means the capability is reachable only by hand-typed request (so a UI tab for it is the highest-value next task); zero server references means the module shipped but no route ever exposed it. Either finding means "done" was wrong, and a suite that imports the module directly stays green through both — which is why this is a grep across layers, not a test.

24. **Prove the first slice of a structural UI change, then replicate.** Splitting a page into nav-driven sections, or adding a tab to an existing panel, is several coupled edits (markup wrap, control removal, handler rewrite, CSS, a new loader). Build one end to end — render, screenshot, DOM probe, zero page errors — then do the rest. Six unbuilt-at-once sections give a screenshot that cannot tell you which edit broke what, and one unproven handler is a `ReferenceError` the DOM probe catches only if you look for it.

25. **A per-page assertion that assumes every page has the same shape tests your assumption, not the page.** A sweep that requires a non-empty `<tbody>` fails on a figure-only dashboard and a prose-only docs page — both of which rendered correctly — and the instinct is to “fix” the page. Make the structural assertion conditional on what the page owns (`hasTable ? rows.some(n => n > 0) : true`) and assert each page's own content separately: its computed values, its form presence, its code-block length. Assert placeholder state too, or a page of pure `-` characters passes.

26. **Prove against a copy of the live database, not the live one and not an empty one.** An empty-state table renders on almost any markup, so an all-empty run proves only that the page loads. Copy the DB (and its `-wal`/`-shm` siblings) to a scratch path, boot the throwaway instance against the copy, and let the real rows exercise the renderers. The copy keeps the live DB unopened, and the row counts you read back are the evidence.

27. **Nested quoting breaks `terminal()` called from `execute_code`.** An outer `r"""…"""` payload containing an inner `"""` or a `python -c "…"` block raises `SyntaxError: unterminated triple-quoted string literal` before the command runs. Write the script to a file with `write_file` and run the file — it beats a third attempt at the escaping, and a throwaway `/tmp` script is trivially reusable for the next check.

28. **A verbose wrapper can swallow the call's own result — re-read the authoritative state.** A pre-commit hook or test runner printing a screenful of output buries the invoking command's stdout, so a command that succeeded reads as silent and gets reported as a failure. Never conclude from a wrapper's noise: re-check in a separate call (`git log --oneline -1`, `git status --porcelain`, an HTTP status) before stating what happened. Being wrong about a success and a failure in the same direction is the cost of skipping that read.

29. **In anything meant to be imported, read configuration at call time.** A module-level `const KEY = process.env.X || ''` evaluates at import, so a consumer that sets the variable afterwards sends no credential and gets an unexplainable 401 — while running the file directly still works, so it ships green. Use `key()`/`host()` accessors. A comment claiming the code reads per call is not evidence that it does.

30. **A token vision names is a lead, not a verdict — grep the file to settle it.** Vision is a noisy witness whose errors run both ways: it invents tokens that were never in the DOM, and it faithfully reports stray strings that really are in the file. A word it flagged in a code comment turned out to be genuinely present, and a character sweep scoped to non-ASCII had no reason to catch ASCII junk. So before writing the cleanup patch — and before telling the user the file is clean — confirm the string with `grep` on the source, and widen the sweep past whatever range you happened to be auditing.

31. **A test that boots a service must refuse to write to a non-scratch database.** A relative configured path means "whatever the process's working directory is", which for a service started from its project root is the **live** database, so a fixture row ships to production while every assertion passes. Resolve the path to an absolute one at entry and exit non-zero unless it lives under a scratch directory, and carry a per-run token in the filename. When checking for leftovers, query the live table by fixture *name* — an all-revoked or zero-count report reads clean while the row is still sitting there.

32. **Don't nest a heredoc inside a Python string inside `terminal()` — write the file.** `bash <<'EOF'` embedded in a Python string embedded in an `r\"\"\"…\"\"\"` payload fails to quote four different ways, and each failure looks like the code under test misbehaving. Same for `python3 -c` with non-ASCII inline. Write the helper to `.sh` or `.py` and run it by path; the throwaway script is reusable next time anyway.

33. **The installed `pixelshot` CLI renders to TILES — learn its output shape before re-running it.** `~/.local/bin/pixelshot --output <dir> <url>` writes `<dir>/<host>_<page>.tiles/tile_0000.jpg` plus `tiles.json`; the positional argument is the INPUT, so passing an output filename fails with `Failed to render <name>: [Errno 2] No such file or directory` (exit 2) **after** the tiles were written — that error reads like a broken renderer and is not. Flags worth knowing: `--viewport-width` (default 875), `--tile-height` (default 8192), `--quality`, `--workers`, `--backend cdp|playwright`, `--wait-network-idle` for pages that fetch after load. Copy `tile_0000.jpg` out and point vision at it; use the CDP/Puppeteer recipes above when you need DOM assertions beside the image.

See `references/interactive-ui-verification.md` for the three-surface rule

`scripts/cdp-shot.mjs` is a dependency-free screenshotter: point it at a URL, get a PNG per viewport plus a DOM probe and any uncaught page errors. Set `CHROME`, `PROBE`, `VIEWPORTS` (`name:w:h:scale` comma-separated), and `AUTH_CMD` (shell command printing the basic-auth password).

`scripts/nav-sweep.mjs` proves every section of a nav-driven page at once: boots a throwaway instance against a copy of the live database, clicks each nav target, asserts computed visibility and row content per section, reports console exceptions, and writes one screenshot per section. Configure via `CHROME`, `APP_CMD`, `ENV_JSON`, `ORIGIN`, `HDR_JSON`, `NAV_ATTR`, `PAGE_CLASS`, `LIVE_DB`, `OUT`. Exits non-zero on any failing section, so it can gate a commit.

See `references/interactive-ui-verification.md` for the three-surface rule (SSR / client bundle / browser behaviour), the Puppeteer trap table, and a reusable assertion-plus-screenshot script.

`references/headless-ui-flow-verification.md` covers proving a feature that only appears after a user action — submit a form, reveal a one-time secret, revoke it — including the throwaway-instance setup for an origin-allowlisted CSRF guard and proxy-injected auth headers, the teardown check that proves no test server or database survived, and the computed-state recipe for sweeping every section of a nav-driven page.
