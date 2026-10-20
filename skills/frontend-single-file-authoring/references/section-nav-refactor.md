# Splitting a one-page frontend into nav-driven sections

Reusable recipe for turning a single scrolling page into `nav → section.page` without breaking it.
Assumes the file is one standalone HTML document with inline `<style>`/`<script>` and ids referenced as
`$('id')` from the script.

## Audit before touching anything

Run this against the *unmodified* file to get the inventory you must preserve.

```python
import re
P = 'public/index.html'
s = open(P, encoding='utf-8').read()

# every id the script reaches for
ids = set(re.findall(r"\$\('([a-zA-Z0-9_-]+)'\)", s))
have = set(re.findall(r'id="([a-zA-Z0-9_-]+)"', s))
print('script refs with no element:', sorted(ids - have) or 'none')

# candidate section boundaries, in document order
print('h2 sections:', re.findall(r'<h2>([^<]+)</h2>', s))
print('tabs/panes :', re.findall(r'data-([a-z])="([a-z]+)"', s), re.findall(r'id="pane-([a-z]+)"', s))
```

A nonempty `script refs with no element` list *before* you start means the file already has dead
references — do not attribute those to your refactor.

## The refactor

1. Insert the nav directly after `</header>`. One button per section, each carrying `data-s="<key>"`.
2. Wrap each existing block in `<section class="page" id="page-<key>">` … `</section>`. **Move, never
   retype** — copy the block verbatim so its ids survive.
3. Add `hidden` to every section except the default one, and have the script set the initial state too,
   so the correct section shows even before any click:
   ```js
   for (const s of document.querySelectorAll('.page')) s.hidden = s.id !== 'page-dash';
   ```
4. Replace the old tab/pane switcher with a nav switcher driven by the button attribute (below).
5. Delete the old strip's markup **and** its handler in the same pass.

```js
$('nav').querySelectorAll('[data-s]').forEach((b) => {
  b.onclick = () => {
    for (const s of document.querySelectorAll('.page')) s.hidden = s.id !== 'page-' + b.dataset.s;
    $('nav').querySelectorAll('[data-s]').forEach((x) =>
      x.setAttribute('aria-selected', String(x === b)));
    if (b.dataset.s === 'settings') loadSettings();   // lazy: only this page needs it
  };
});
```

Only call a loader from the click that needs it, and only if it is **defined**. A call to a function you
plan to write "later in the same pass" is a `ReferenceError` on every click of that section; grep for the
name to confirm it exists before wiring it.

## Post-edit audit

Same script as above, plus:

```python
pages = set(re.findall(r'id="page-([a-z]+)"', s))
navs  = set(re.findall(r'data-s="([a-z]+)"', s))
print('nav targets without a page:', navs - pages)
print('pages without a nav entry:', pages - navs)
print('CJK:', len(re.findall(r'[　-鿿]', s)))
print('// inside <style>:', len(re.findall(r'^\s*//', style_block, re.M)))
```

`nav targets without a page: set()` is the check that matters most — a button wired to a missing id
silently does nothing.

## Sequencing: prove one section before building the rest

Build the first section end to end — markup, CSS, handler, screenshot, DOM probe — then replicate. When
the pattern is right the remaining sections are mechanical, and you get a proven template instead of six
unverified ones. If you build all seven and something is wrong, the screenshot does not tell you which
edit caused it.

## Verification

Follow `website-screenshot-automation` pitfalls 17, 19, 20: probe computed values (`display`,
`scrollWidth - clientWidth`) and assert the rendered payload, not just that a container is visible. For
nav work specifically, assert per section:

- the section you clicked is the only one with `hidden === false`
- its content is non-empty (row counts > 0, or the documented empty-state string)
- zero uncaught page errors across the whole sweep
- a full-page screenshot **per section**, read back with vision — a nav that switches to an empty page
  looks correct in the DOM and obviously wrong in the PNG