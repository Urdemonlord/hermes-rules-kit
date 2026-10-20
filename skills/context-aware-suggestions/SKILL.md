---
name: context-aware-suggestions
description: Use when building suggestion chips from project state.
---

# Context-aware suggestions

Suggestion chips / next-action hints / recommendation lists derived from what the user is
actually working on, instead of a static list picked per category.

The failure this replaces: a hardcoded list per language or per tab, chosen by file
**extension** only and shuffled at render. It cannot tell two projects apart, it suggests
capabilities the project already shipped, and the chips move under the cursor.

## Procedure

1. **Pure module, not component inline.** `lib/suggestions.ts` exporting
   `buildSuggestions(ctx)` and `detectDomains(...)`. Pure = testable with no browser and no
   login, and it stops a large component file from growing further.
2. **Build a haystack:** lowercased file paths + content, plus free-text context
   (project description, last-used prompt). **Cap the scan** — ~400 KB total, ~20 KB per
   file — so a big project stays cheap (80 files / ~2.4 MB measured at ~30 ms).
3. **Detect the domain** (app category) from that haystack, weighting metadata above code
   content (see rules).
4. **Candidate list:** capabilities ordered by relevance *for that domain*, then
   domain-agnostic quality gaps.
5. **Filter:** drop every candidate the project already has.
6. **Return the first N** in a deterministic order.

## Rules (always on)

- **Never shuffle.** `sort(() => 0.5 - Math.random())` reorders the chips on every render —
  they move under the user's cursor while they read. Order deterministically (domain
  relevance first, then the id as a stable tie-break) and the list stays put.
- **Drop what the project already has.** This is the core of "relevant": absence. Detect
  each capability's presence in the content and omit it. Suggesting a feature that already
  shipped reads as not having looked at the project at all.
- **Weight the stated purpose above code content.** The description/prompt names the app's
  type; content carries incidental identifiers. Weighted equally, a variable named
  `catatan` outvotes "aplikasi pengeluaran" and the app is mislabelled — the suggestions are
  then confidently about the wrong product.
- **Compute from the committed value, not the live input.** Deriving from the controlled
  text field recomputes on every keystroke: chips reorder mid-typing *and* it costs
  ~30 ms/char on a large project. Use the last-used / last-committed prompt.
- **Phrase with a domain noun.** "Tambah pencarian **kartu**" beats "Tambah pencarian
  data" — the noun is what makes the chip read as about *this* project.
- **Empty project → empty list.** Return `[]` with no files. Do not fall back to a generic
  static list; that is the behaviour being replaced.
- **Don't put the highest-value capability first for everyone.** A global priority (e.g.
  auth at the top) makes every project's first chip identical — which is the generic
  behaviour again, just reordered. Priority must be per-domain.

## Signal-detection pitfalls (silent misclassification)

- **Word boundaries, or you match substrings.** `order` matches inside `reorder` (an
  unrelated app was labelled e-commerce); `\bdrag\b` misses `dragover` (a present
  capability reported as missing). Use `\b…\b` and enumerate the inflections
  (`drag|dragover|dragstart|draggable`).
- **A ubiquitous token must not own a domain.** `column` matches
  `flex-direction: column` on virtually every page, so plain landing pages were classified
  as kanban boards and told to "add drag & drop cards". Give each domain its own
  vocabulary (`kanban|board|backlog|swimlane`), never a token the target language emits
  everywhere.
- **In-memory containers are not persistence.** `list.append()` / `arr.push()` are not
  storage; matching them suppressed a genuinely needed "save your data" suggestion. Match
  real storage APIs (`sqlite|postgres|prisma|firestore|localStorage|shared_preferences|
  json.dump|open(...,'w')`).
- **A generic word in markup is not a signal.** `<script>` appears in every HTML page — do
  not key a data/script domain off the bare word `script`.
- **Test with realistic markup, not clean snippets.** Every bug above was found by feeding
  a fixture that looked like real output (a `<style>` block with `flex-direction: column`, a
  `dragover` listener, a pandas script) — not by re-reading the regexes.

## Verify

No test runner in the repo is **not** a reason to skip tests. Compile the single module and
drive it from a node harness:

```bash
npx tsc lib/suggestions.ts --outDir /tmp/sugg-test --module commonjs --target es2020 \
  --moduleResolution node --skipLibCheck --esModuleInterop
# the `Cannot find module '@/types'` error is expected and harmless when the import is
# type-only — JS is still emitted. Then: node /tmp/sugg-test/run.js
```

Assertions that actually caught the bugs:
- a project that **has** a capability is never suggested it (the whole point)
- same input → same output across N calls (determinism / no shuffle)
- domain classification on fixtures with realistic markup
- empty input → empty output
- runtime bound on a large fixture (e.g. 80 files) so the haystack cap is real

Then prove the old path is gone from the shipped bundle, not merely shadowed:
`grep -c '<old chip text>' <built chunk>` must be **0**, and the new template string must be
present. Caveat: a `Math.random()` hit in a bundle may be your own doc comment or a library —
read the surrounding context before calling it a leftover shuffle.

See `references/signal-catalog.md` for the capability detectors and domain vocabularies.
