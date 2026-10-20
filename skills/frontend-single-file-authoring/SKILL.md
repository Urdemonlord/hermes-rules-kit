---
name: frontend-single-file-authoring
description: Use when authoring a large standalone frontend file.
---

# Frontend Single-File Authoring

A standalone HTML file — one document with inline `<style>` and `<script>` — is the normal shape for
dashboards, admin panels, landing pages, and prototypes. It is also the shape most likely to corrupt
silently when authored in one shot, because a single 25-30KB payload through a tool call can come back
with dropped or substituted characters that still *look* like valid markup.

The rule: **never trust a large single-call write without a parse gate.**

## When this applies

Single-file HTML with inline CSS and JS: dashboards, admin panels, prototypes, and rewrites of any of
them. Not applicable to multi-file project codebases.

## Procedure

1. **Inspect before authoring.** Read the existing file if there is one. A rewrite is not a redesign —
   inventory the element IDs, CSS classes, and `data-*` hooks the existing script depends on. Any
   rename in markup must be renamed in script in the same pass, or the screen silently dies.
2. **Back up.** `cp public/index.html public/index.html.bak-<reason>` before replacing. Keep the backup
   until the user has seen the result.
3. **Author in chunks, not one call.** Split into `1-head.html` (doctype through `<style>`), `2-body.js`
   (the script), and any markup chunk. Each chunk stays a few KB. Concatenate into the final file.
   Large single-call writes of dense markup/JS are the failure mode this skill exists to prevent.
4. **Parse-gate each chunk before concatenating.** Copy to `.mjs` and run `node --check`. A chunk that
   fails here costs seconds; the same failure found after concatenating and deploying costs a restart.
5. **Concatenate, then re-extract and re-check.** The concatenated file is what ships, so it is what gets
   verified: pull the `<script>` body back out to a temp `.mjs` and `node --check` again.
6. **Visual proof at two viewports.** Desktop (~1440px) and mobile (~390px). Screenshot alone is not
   enough — also probe the DOM: row counts, status-label presence, `document.documentElement.scrollWidth`
   vs `clientWidth` for horizontal overflow, page-error and console-error listeners. `horizOverflow: 0`
   is the claim that matters on mobile; a screenshot can look fine while a table still forces a scroll.
7. **Report each layout problem with its cause**, not just its existence.

## Restructuring an existing single file into sections

Splitting one long scrolling page into nav-driven sections is an *incremental* edit, not a rewrite: wrap
existing markup in `<section class="page" id="page-x">` and the content survives untouched. Never retype
the blocks you are only moving — a retyped block loses its ids and the script that fills it.

1. **Prove each section already has content before it becomes a nav entry.** A nav item leading to an
   empty page is worse than no nav item: it advertises a capability that does not exist. If a section needs
   content it does not have, either render data the app already fetches but never displays, or do not add
   the entry yet.
2. **Drive the switch from the button's own attribute, not a hardcoded id list.** `for (const s of
   document.querySelectorAll('.page')) s.hidden = s.id !== 'page-' + b.dataset.s` makes a nav entry with
   no page show nothing instead of leaving a stale section on screen. The same rule applies to any
   tab/pane/disclosure switch you rewrite.
3. **Removing a control orphans its handler.** Delete the tab strip and `$('itabs').querySelectorAll(...)`
   still runs at load and dies on a null deref, taking the rest of the script with it. Audit every
   `$('id')` reference against the ids that survive.
4. **Gate on exit codes, and re-verify the markup after the last edit.** See
   `references/section-nav-refactor.md` for the audit script (id ↔ nav-target coverage, dangling `$()`
   refs, non-ASCII slips) and the prove-one-before-the-rest sequencing rule.

## Pitfalls

- **Unbalanced backticks read as balanced.** A missing closing backtick in a template literal makes
  every later line part of one string, so the file still looks correct when read. Count backticks per
  line and print the odd-count lines instead of eyeballing the source — the corruption is not where it
  looks. `?:` inside a template makes naive counts misleading; count per line, not per file.
- **`const` helpers used above their declaration look like TDZ bugs but are not.** A `const arrow`
  referenced by a function defined earlier is fine as long as the call happens after the script finishes
  evaluating. Do not restructure working code to "fix" this; confirm the call site is runtime, not
  module-init time, and move on.
- **Inline `<script>` cannot be checked via process substitution.** `node --check <(...)` fails on the
  shell side. Extract the script body to a real temp file first, then check.
- **Operator-supplied values rendered into `innerHTML` are an XSS surface.** Customer names, references,
  webhook URLs — escape them at the render site even though they arrive from your own API. Any value a
  human typed needs `esc()` before it reaches markup.
- **One parser for every timestamp.** A codebase may hand back both ISO strings and epoch milliseconds
  depending on the query path. A single `whenTs()` helper that accepts either shape stops `new
  Date(iso)` from rendering `Invalid Date` on one row type and a correct date on another.
- **Never cache a live payment code in `localStorage`.** A QR payload is a payable instrument; an
  in-memory `Map` for the session is correct, durable storage is not.
- **A `//` comment inside `<style>` is not a comment.** The CSS parser treats `// Same shape as…` as a
  bogus selector and discards rules until it recovers, so every declaration after it silently vanishes.
  Use `/* */` even in a file whose script block is full of `//`.
- **A hand-rolled tag-balance counter reports valid nesting as a mismatch.** Counting `s.count('<div')`
  also matches `<divider>`, and a naive stack flags `<section class="page"><section class="figs">…</section>
  </section>` as wrong because it resyncs after the inner close. Use a real parser, or let the browser
  tell you: the DOM probe after load reports whether the tree is what you intended, and that is the
  surface users actually see.
- **Check for stray non-ASCII in every string you author.** A CJK glyph inside Indonesian prose ships
  looking like text. Sweep for `[　-鿿]` over the finished file before the screenshot step.

## Verifying a redesign

A redesign is presentation only — keep every API route, payload shape, and status string identical, so
the change needs no service restart and no data migration. Prove the claims separately:

- `changed` — file rewritten, backup retained.
- `verified` — parse-gate passed, both viewports screenshotted, DOM probe reported, zero page errors.
- `unverified` — call out anything the probe did not actually check, by name. A probe that measured
  overflow did not verify responsive column collapse; say so rather than letting "mobile OK" stand.

## Related

- `website-screenshot-automation` — capture and DOM-probe mechanics, including the zero-dependency
  raw-CDP script when no browser automation package is installed.
- `design-taste-frontend` / `antislop-ui` — aesthetic direction and the anti-tell checklist. Their
  landing-page sections do not govern a dense ops dashboard; take the color, type, and hierarchy rules
  and skip the marketing-hero sections.