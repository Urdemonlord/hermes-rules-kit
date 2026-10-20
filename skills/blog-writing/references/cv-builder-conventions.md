# the CV builder Blog Conventions

The rules that make a post publishable in `Urdemonlord/the CV builder`. These come from the codebase, not
from style preference. When this file and a generic SEO guide disagree, this file wins.

## Where articles live

`apps/web/lib/blog/posts.ts` — typed data, exported as `POSTS: Post[]`.

```ts
export interface PostSection {
  heading: string;
  paragraphs: string[];
  bullets?: string[];
}

export interface Post {
  slug: string;
  title: string;
  description: string;   // meta description + index card + JSON-LD
  datePublished: string; // ISO 8601
  keywords: string[];
  sections: PostSection[];
}
```

**Not MDX, on purpose.** There is no markdown parser in the pipeline, which means there is no
XSS surface: every paragraph becomes plain React text. Two consequences:

- Never put markdown syntax in a paragraph string. `**bold**` renders literally as asterisks.
- Emphasis and links are not available. If a post needs them, that is a change to the renderer
  (`app/artikel/[slug]/page.tsx`), not to the content.

Adding a post requires **no other file change**. The index, the sitemap, the static params, and
the OG image all read from `POSTS`.

## Slug rules

Lowercase, hyphenated, ASCII, no stop-word padding: `^[a-z0-9-]+$`. Describe the reader task, not
the keyword: `cara-membuat-cv-ramah-ats`, not `tips-cv-ats-terbaik-2026`.

Slugs are permanent. A published slug is a URL that may already be indexed and shared; changing
one breaks the link unless a redirect ships with it.

## Description rules

`description` is reused three ways: meta description, the card on `/artikel`, and
`BlogPosting.description` in JSON-LD. Keep it **70–165 characters** — shorter is a wasted
snippet, longer gets truncated in search results. Write a summary of the page, not a teaser.

## Claim rules

This is the rule the product is built on, and it applies to editorial too: **every number must
trace to a real source.** `apps/web/lib/ai/guard.ts` enforces the same idea in the AI feature —
invented numbers become `[X%]`, invented skills get the output rejected.

Never write:

| Banned | Why |
|---|---|
| `95% lolos ATS`, `tingkat kelulusan 90%` | No such data exists. No tool can measure it. |
| `10.000+ pengguna`, `50+ perusahaan` | Unless the number is measured, it is invented. |
| `rating 4.9/5` | the CV builder collects no ratings. |
| `dijamin lolos`, `pasti diterima` | A guarantee nobody can make. |
| `terbaik`, `nomor 1` | Unverifiable superlative. |

Saying the honest opposite is fine and encouraged: *"Tidak ada alat, jasa, atau orang yang bisa
menjamin CV kamu lolos ATS."* A post may mention `tingkat kelulusan` when explaining that it
cannot be measured.

`posts.test.ts` enforces this by matching the **shape** of a claim — a figure next to a promise —
not the presence of a phrase, so honest sentences survive.

## Product rules must match the code

When a post cites a rule the product uses, the number has to be the number in the code. Check it
with `search_files`, never from memory:

| Rule in the post | Source of truth |
|---|---|
| Max 18 bullet points for a US application | `analyze.ts` — `cv.settings.region === 'us'` |
| Max 30 bullet points for A4 | `analyze.ts` |
| No photo for US applications | `analyze.ts` region check |
| Minimum 5 skills mentioned | `analyze.ts` completeness |
| Score weights 25/25/20/15/15 | `analyze.ts` `WEIGHTS` |
| Job Match = matched / total keywords | `lib/cv/analysis/keywords.ts` |
| 163 recognised skill terms, 24 synonym pairs | `lib/cv/analysis/lexicon.ts` `SKILL_TERMS`, `SYNONYMS` |
| Whole-term matching (java ≠ javascript) | `containsTerm()` lookbehind |
| Specific phrase wins (react + react native → one keyword) | `matchKeywords()` filter |

**Verify a claim by running the code, not by reading it.** `lib/cv/analysis/*.ts` only imports
types and siblings, so `node --experimental-strip-types` executes it directly after adding `.ts`
to relative imports in a temp copy. When a claim about scoring matters, assert it against the
real functions — reading the regex and reasoning about it is how the `node.js.js` quirk stayed
invisible.

## Known quirk: normalizeText mangles dotted terms

`normalizeText()` turns `node.js` into `node.js.js`, because the `node` synonym fires inside text
that is already correct. The cause is an asymmetric regex in `keywords.ts`: the lookbehind
`(?<![\w.#+/-])` includes a dot but the lookahead `(?![\w#+/-])` does not.

**Functional impact is zero** — a property test over all 163 `SKILL_TERMS` shows every term still
matches and scores 100 when present. It only touches dotted terms (`next.js`, `node.js`, `.net`)
and only makes the internal string ugly. Do not cite it as a bug that affects scores, and do not
fix it in a blog PR: it touches scoring logic and needs its own tests, including the weak
assertion at `analyze.test.ts:80` that currently pins the buggy behaviour via `toContain`.

A post that contradicts the product creates support work and erodes trust in the score.

## Structured data

`lib/seo.ts` owns it. `postStructuredData()` emits `BlogPosting`; `blogStructuredData()` emits
`Blog` for the index. Adding a post changes nothing here.

- `author` is `Organization` (the CV builder), not a person. Inventing a byline is a fabricated credential.
- **`Article`/`BlogPosting` is still supported by Google.** Keep it.
- **`FAQPage` earns nothing** — Google removed FAQ rich results on 7 May 2026. FAQ *content* is
  fine for readers; the markup is dead weight.
- **No `aggregateRating` or `review`.** the CV builder collects no ratings, so the values would be invented.
  `offers` (free, IDR 0) already satisfies Google's requirement for `SoftwareApplication`.

## What is already automated

Do not re-implement these; a new post gets them for free:

| Concern | Handled by |
|---|---|
| `/artikel` index, sorted newest first | `app/artikel/page.tsx` + `allPosts()` |
| Static generation per slug | `generateStaticParams()` |
| 404 for unknown slug | `notFound()` in `app/artikel/[slug]/page.tsx` |
| Sitemap entry with `lastModified` | `app/sitemap.ts` |
| RSS feed at `/feed.xml` | `lib/blog/feed.ts` + `app/feed.xml/route.ts` |
| Feed autodiscovery on every page | `alternates.types` in `app/layout.tsx` |
| OG image with the post title | `app/artikel/[slug]/opengraph-image.tsx` |
| Reading time | `readingMinutes()` — computed, never stored |
| Internal link to `/artikel` | `site-header.tsx`, `sections.tsx` |
| JSON-LD | `lib/seo.ts` |

A new post appears in the feed with no extra work: `buildFeed()` reads `allPosts()`. Do not
hand-edit `/feed.xml` — there is no static file, it is generated.

## Known gaps

- **No author page.** E-E-A-T references ask for one; the CV builder currently attributes to the
  organization, which the rubric accepts ("organization attribution acceptable with clear
  editorial ownership") but does not score as high as a named author with a bio.
- **No `llms.txt`.** Low effort, some GEO benefit.
- **Only 4 articles.** A cluster needs 8–12 before internal linking and topical authority work.
- **No links between posts in the body.** The detail page links to sibling posts and the index,
  but no post body links to another. A markdown link would render literally, so this needs a
  renderer change or a structured `related` field.

## Verification commands

```bash
cd /tmp/cv-builder-work
python3 ~/.hermes/skills/content/blog-writing/scripts/check_posts.py apps/web/lib/blog/posts.ts
npm run test -w @cv-builder/web        # includes posts.test.ts
npm run lint -w @cv-builder/web
npm run type-check -w @cv-builder/web
```

Live check after deploy:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://cv-builder.meowlabs.id/artikel/<slug>
curl -sS https://cv-builder.meowlabs.id/sitemap.xml | grep -c '<loc>'
```
