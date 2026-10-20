---
name: blog-writing
description: Write, audit, and score the CV builder blog articles.
version: "1.0.0"
author: "Urdemonlord (@Urdemonlord) — the CV builder adaptation; methodology adapted from AgriciDaniel/claude-blog (MIT)"
license: MIT
metadata:
  hermes:
    category: content
    tags: [blog, seo, content, editorial, cv-builder]
    related_skills: [cv-builder-deploy]
---

# Blog Writing Skill

Write, audit, and score the CV builder blog articles. Articles live as typed data in
`apps/web/lib/blog/posts.ts`, never as MDX, so this skill covers both the editorial work
(brief, outline, draft, score) and the repository conventions that stop a post from breaking
the build or shipping a claim nobody can back up.

Two rules override every other consideration. Every number in a post must trace to a real
source, and every product rule a post cites must match `apps/web/lib/cv/analysis/analyze.ts`.
A post that reads well but invents a statistic is worse than no post.

## When to Use

Use when writing a new article, auditing or rewriting a published one, planning a topic
cluster, or checking whether a draft clears the 100-point bar.

Do not use for editing CV content (that is the editor app) or for prose that will not be
published on `cv-builder.meowlabs.id`.

## Prerequisites

- `read_file`, `write_file`, `patch`, `search_files`, `terminal` — native, no setup.
- Python 3.11+ for `scripts/check_posts.py` (this VPS runs 3.12).
- A the CV builder working copy. Default in this session: `/tmp/cv-builder-work`.
- **No external data source is wired in.** You cannot fetch Search Console, ranking, or
  keyword-volume data. Never claim to have measured anything you did not.

## How to Run

1. Read  first. It holds the rules that make a post
   publishable in this repo, and they are not negotiable.
2. Draft the post following `## Procedure`.
3. Validate with `scripts/check_posts.py` before committing.
4. Ship through a PR so CI verifies it (branch protection requires a green `check`).

## Quick Reference

| Task | Where to look |
|---|---|
| Post data shape, slug rules, claim bans |  |
| Structure, headings, sentences, readability | `references/content-rules.md` |
| 100-point scoring rubric and thresholds | `references/quality-scoring.md` |
| AI-slop detection (two-tier reflex check) | `references/ai-slop-detection.md` |
| E-E-A-T, authorship, trust signals | `references/eeat-signals.md` |
| AI-citation readiness (GEO/AEO) | `references/geo-optimization.md` |
| Internal linking, clusters, orphans | `references/internal-linking.md` |
| Source tiering and research quality | `references/research-quality.md` |
| Post templates | `templates/` |
| Deterministic validator | `scripts/check_posts.py` |

## Procedure

### 1. Brief — decide the reader task before the keyword

Name the reader and the job they are trying to finish. "Fresh graduate with no experience
applying to their first job" is a brief. "CV tips" is not.

Pick a template from `templates/`. For the CV builder the useful ones are `how-to-guide.md`,
`listicle.md`, `comparison.md`, and `faq-knowledge.md`.

### 2. Outline — sections that each answer one question

Every H2 should be answerable on its own, because AI answers and featured snippets extract
passages, not pages. State the answer in the first sentence of the section, then support it.

### 3. Draft — write from the product's real rules

Read `apps/web/lib/cv/analysis/analyze.ts` and the relevant part of the app before writing.
When the post says "keep it to 18 bullet points for a US application", that number must be
the number the code uses. A post that contradicts the product is a support burden.

Write each paragraph as a React-renderable plain string. No markdown syntax inside a
paragraph: the renderer emits text, not markdown, so `**bold**` would appear literally.

### 4. Score — run the rubric honestly

Score against `references/quality-scoring.md` (100 points across Content 30, SEO 25,
E-E-A-T 15, Technical 15, AI-citation 15). Mark an item N/A only when the draft truly has
no evidence for it, and say which evidence is missing.

Delivery bar: overall 90+ with zero P0 issues, where the P0 list is fabricated statistics,
broken heading hierarchy, unsourced claims, and missing attribution.

### 5. Validate — run the deterministic check

```bash
python3 ~/.hermes/skills/content/blog-writing/scripts/check_posts.py /tmp/cv-builder-work/apps/web/lib/blog/posts.ts
```

It checks the things a human reviewer misses: slug shape, description length, ISO dates and
ordering, keyword presence, section structure, and the banned-claim patterns.

### 6. Ship — PR, not a direct push

```bash
cd /tmp/cv-builder-work
git fetch origin && git checkout -b feat/blog-<slug> origin/main
git add apps/web/lib/blog/posts.ts
git commit -m "feat(blog): <title>"
git push -u origin feat/blog-<slug>
gh pr create --base main --head feat/blog-<slug>
```

Wait for `check` to go green, then squash-merge. CI is the gate; do not merge red.

## Pitfalls

**Branch from a stale base duplicates code.** If the working copy still holds a commit that
`main` already has as a *squash*, the branch carries both copies and the merge fails with
`TS2451 Cannot redeclare`. Always branch from `origin/main`, never from whatever the working
tree happens to sit on. If it already happened: `git rebase --onto origin/main <old-head>`.

**A test that bans a word bans honest sentences.** A post legitimately says "no one can
guarantee an ATS pass". Match the *shape of a claim* (a figure next to a promise), not the
presence of a phrase:

```ts
expect(text).not.toMatch(/\d+\s*%\s*(pasti\s*)?lolos/);
```

**Verifying rendered HTML: check the raw bytes before reporting a bug.** Next.js emits
`dateTime` (camelCase), and React inserts `<!-- -->` between adjacent text nodes, so
`2<!-- --> menit baca` breaks a naive `\d+ menit baca` regex. Two "missing element" reports
in this project were the regex, not the page.

**`description` is reused three ways** — meta description, index card, and JSON-LD. Keep it
70–165 characters so it is not truncated in search results.

**Do not add `aggregateRating` or `review` to structured data.** the CV builder collects no ratings,
so the numbers would be invented. `offers` (free, IDR 0) already satisfies Google.

**`FAQPage` markup earns nothing.** Google dropped FAQ rich results on 7 May 2026. The FAQ
content can stay for readers; the markup is dead weight.

**`Article`/`BlogPosting` markup is still supported** — unlike FAQ. Keep it.

**A hand-edited XML file would break the feed.** XML has no forgiving mode: one unescaped `&`
in a title makes the whole document unparseable, and readers report an empty feed rather than an
error. `escapeXml()` escapes in a single pass so `&amp;` is never re-escaped into `&amp;amp;`,
and `feed.test.ts` asserts no raw ampersand survives. Never hand-write `/feed.xml` — it is
generated by `buildFeed()`.

## Verification

Before calling a post done:

1. `scripts/check_posts.py` exits 0.
2. Every rule cited in the post matches `analyze.ts` (grep the constant, do not trust memory).
3. No number appears without a source or a user-data origin.
4. `npm run test -w @cv-builder/web` passes, including `posts.test.ts` and `feed.test.ts`.
5. The PR's `check` is green and the deploy is live:
   `curl -sS -o /dev/null -w '%{http_code}' https://cv-builder.meowlabs.id/artikel/<slug>` → 200.
6. The rendered page actually contains the copy: read the live HTML, do not assume.
7. The post appears in the feed: `curl -sS https://cv-builder.meowlabs.id/feed.xml | grep <slug>`.

**Run tests without `node_modules` when the host is small.** `lib/blog/*.ts` has no imports
beyond relative ones, so `node --experimental-strip-types` executes it directly. Node needs
explicit `.ts` extensions on relative imports (a bundler does not), so copy the files to a temp
directory, add the extensions, and import from the copy — the logic under test is unchanged.
This matters on a VPS where `npm install` of a Next.js monorepo risks OOM.

## Attribution

Editorial methodology adapted from [claude-blog](https://github.com/AgriciDaniel/claude-blog)
by AgriciDaniel (MIT). The two-tier AI-slop detection method originates in
[impeccable](https://github.com/pbakaus/impeccable) by Paul Bakaus (Apache-2.0).
See `references/attribution.md` for the full notice.
