# Driving a Real Form Flow Headlessly (CDP, zero dependencies)

For proving a UI feature that only exists after user action — create a record, reveal a
one-time secret, revoke it — not just for rendering a static page. Use a cached Chromium
over raw CDP when no browser package is installed and none should be.

## The trap: you are not driving the production origin

A browser pointed at `http://127.0.0.1:PORT` is a *different request* as far as the app's
guards are concerned, and two of them fire:

- **Origin allowlist (CSRF)** — browsers always send `Origin`, and it will be the loopback
  origin, which is not in the allowlist. A correct **403**.
- **Proxy-injected headers** — a token or identity header that nginx normally adds never
  appears, so a correct **401**.

Both read as "my new code is broken" and neither is. Before writing a single assertion,
confirm which guard you tripped by curl'ing the same origin with an explicit `Origin`:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:PORT/api/thing \
  -H "Origin: https://the-real-host" -H 'x-panel-token: ...' -d '{}'
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:PORT/api/thing -d '{}'
```

If the first is 201 and the second is 403/401, the guard is working and the browser harness
is wrong.

## Fix: a throwaway instance whose own origin is allowlisted

Do not loosen production to make a test pass, and do not skip the feature. Boot the same
code on its own port with its own database, allowlist that port's own origin, and inject the
proxy-supplied header from the client side so the token check itself stays real:

```js
const ORIGIN = `http://127.0.0.1:${APP_PORT}`
spawn('node', ['src/server.js'], {
  env: { ...process.env, PORT: String(APP_PORT), HOST: '127.0.0.1', DB_PATH: DB,
         TRUST_PROXY: '0', ALLOWED_ORIGINS: ORIGIN },
})
await send('Network.setExtraHTTPHeaders', { headers: { 'x-panel-token': TOKEN } })
```

Reachable only because the instance binds `127.0.0.1` on an otherwise idle port. Comment that
in the script — a test that injects a secret header is not a claim about the live app's auth,
and the next reader needs to know the difference.

## Driving the flow

`Runtime.evaluate` with `awaitPromise: true` runs an async IIFE inside the page, so the whole
interaction stays in one round trip. Poll on observable state, never on a tick count:

```js
const result = await evaluate(`(async () => {
  el.value = 'name'; checkbox.checked = true;
  document.getElementById('form').requestSubmit();
  for (let i = 0; i < 60; i++) {
    if (revealedEl.hidden === false && field.value) break;   // state, not a sleep
    await new Promise(r => setTimeout(r, 100));
  }
  return { revealed: !revealedEl.hidden, value: field.value,
           prefixOk: field.value.startsWith('meowpay_'),
           rows: table.rows.length };
})()`)
```

Collect the surface you are about to judge, then screenshot the same run:

```js
const facts = await evaluate(`(() => {
  const e = document.getElementById('knew'), r = e.getBoundingClientRect();
  return { hiddenAttr: e.hidden, display: getComputedStyle(e).display,
           height: Math.round(r.height), value: document.getElementById('kplain').value };
})()`)
```

Assert the *returned values*, not the attributes. The pair that matters:

| Assertion | Proves |
|---|---|
| `hiddenAttr === true && display === 'none'` | the empty state is genuinely invisible, not just attribute-hidden |
| `value.startsWith(prefix) && value.length > 0` | the secret actually reached the user |

Also capture the refusal path — submit the form with every permission unchecked and assert the
message, otherwise a client that swallows errors looks identical to one that works. Then click
the destructive button and assert both the confirmation and that the control is gone.

## Teardown is not optional

An instance booted for a proof keeps running and keeps holding its database after the script
exits. Put the kill in `process.on('exit')` *and* in `finally`, and delete the db files
(`-wal`, `-shm` too). Verify nothing survived:

```bash
ps -eo pid,args | grep 'src/server\.js' | grep -v grep   # expect only the real one
ls /tmp/<prefix>-*.db* 2>/dev/null || echo 'no test dbs'
```

Then confirm the live database was never touched — row counts and any secrets created during
proof must be gone or revoked, checked by query, not assumed.

## Proving a multi-section navigation, not one panel

When a page is split into nav-driven sections, a screenshot of whichever one is open by
default proves nothing. Click every target in one run and assert the *computed* state:

```js
const info = await evaluate(`(() => {
  document.querySelector('[data-s="${s}"]').click();
  const shown = [...document.querySelectorAll('.page')].filter(p => !p.hidden);
  return { count: shown.length,
           vis: shown.map(p => ({ id: p.id, display: getComputedStyle(p).display,
                                  h: Math.round(p.getBoundingClientRect().height) })),
           sel: document.querySelector('[data-s="${s}"]').getAttribute('aria-selected') };
})()`)
```

Non-zero height is the check that separates "the section exists in the DOM" from "the
section renders" — a container with no layout has no rect, and a source-level reading
cannot tell you that. Require exactly one shown section every time; two visible at once
is a handler bug that a per-section check will miss.

Re-read state *after* waiting for that page's own loader — Settings-style pages fetch on
open, so the click-time snapshot catches empty tables. Give the sweep a screenshot per
section, then read back only the two or three that matter in detail: a full seven-image
vision pass costs far more than it returns.

## Assertions that measure the checker

A sweep that demands one uniform property from every section reports failures that are
the checker's assumption, not the markup — see rules 25 and 26 in SKILL.md for the split
(visibility core everywhere, row counts only where a table exists, per-section content
assertions for figures and prose). Two things make a sweep honest:

- Run it against a **copy** of the live database so every table has real rows. Empty
  states render on broken markup.
- Scope the content assertion to the fields that page actually owns. A generic
  "is any value non-empty" check applied to a key table with no such field reads as an
  empty result and gets reported as a defect.

When a failure survives a plausible fix, suspect the assertion before the page. Two of
seven sections failed here that way, and reading it as a layout bug would have sent the
next session to edit correct CSS.