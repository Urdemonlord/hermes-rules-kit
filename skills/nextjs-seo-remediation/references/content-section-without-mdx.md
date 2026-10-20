# Adding a content/blog section to Next.js App Router without an MDX toolchain

Use when the site needs articles for SEO and adding `@next/mdx` / `contentlayer` / `gray-matter`
is not justified. The content-as-data approach needs zero new dependencies, and because no markdown
parser ever runs, there is **no HTML-injection surface** — the usual reason a blog becomes the
riskiest page on a site.

## Procedure

### 1. Model the content as typed data

`lib/blog/posts.ts` exports an array of plain objects. Nothing renders from a string that a parser
turned into HTML; every paragraph becomes an ordinary React text node.

```ts
export interface PostSection { heading: string; paragraphs: string[]; bullets?: string[] }
export interface Post {
  slug: string;
  title: string;
  description: string;      // doubles as meta description + list-card copy + JSON-LD
  datePublished: string;    // ISO 8601; feeds datePublished and sitemap lastModified
  keywords: string[];
  sections: PostSection[];
}
export const POSTS: Post[] = [ /* ... */ ];
```

Derive anything that can drift, rather than storing it:

```ts
const WORDS_PER_MINUTE = 200;
export function readingMinutes(post: Post): number {
  const text = [post.title, post.description,
    ...post.sections.flatMap((s) => [s.heading, ...s.paragraphs, ...(s.bullets ?? [])])].join(' ');
  return Math.max(1, Math.round(text.trim().split(/\s+/).filter(Boolean).length / WORDS_PER_MINUTE));
}
export const allPosts = () => [...POSTS].sort((a, b) => b.datePublished.localeCompare(a.datePublished));
export const getPost = (slug: string) => POSTS.find((p) => p.slug === slug);
```

A hand-written `readTime: 5` goes stale the first time an article is edited; a derived one cannot.

### 2. Index route — `app/artikel/page.tsx`

Server component. Map `allPosts()` to cards, render the date with `<time dateTime={post.datePublished}>`,
and emit the `Blog` JSON-LD (see step 4).

### 3. Detail route — `app/artikel/[slug]/page.tsx`

Fully static, no runtime data fetch:

```tsx
type Params = Promise<{ slug: string }>;   // Next 15+ params are async

export function generateStaticParams() {
  return allPosts().map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return pageMetadata({ title: 'Not found', description: '', path: `/artikel/${slug}`, index: false });
  return pageMetadata({ title: post.title, description: post.description, path: `/artikel/${post.slug}` });
}

export default async function PostPage({ params }: { params: Params }) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return notFound();   // `return` matters — see pitfall below
  /* ... */
}
```

### 4. Structured data

`BlogPosting` per article, `Blog` for the index. Both are still supported (unlike `FAQPage`).

```ts
export function postStructuredData({ title, description, slug, datePublished, keywords }) {
  const url = `${SITE_URL}/artikel/${slug}`;
  return {
    '@context': 'https://schema.org', '@type': 'BlogPosting', '@id': `${url}/#post`,
    headline: title, description, url,
    mainEntityOfPage: { '@type': 'WebPage', '@id': url },
    datePublished, dateModified: datePublished, inLanguage: 'id-ID',
    keywords: keywords.join(', '),
    // The author is the product team, not a named person: inventing a byline would be a fake claim.
    author: { '@type': 'Organization', name: 'the CV builder', url: SITE_URL },
    publisher: { '@type': 'Organization', name: 'the CV builder', url: SITE_URL },
  };
}
```

`Blog` takes `blogPost: [{ '@type': 'BlogPosting', headline, url, datePublished }]`.

### 5. Sitemap — add both the index and every post

```ts
export default function sitemap(): MetadataRoute.Sitemap {
  const pages = PUBLIC_PATHS.map((path) => ({
    url: `${SITE_URL}${path === '/' ? '' : path}`,
    changeFrequency: 'monthly' as const,
    priority: path === '/' ? 1 : path === '/templates' ? 0.8 : path === '/artikel' ? 0.7 : 0.3,
  }));
  const posts = allPosts().map((post) => ({
    url: `${SITE_URL}/artikel/${post.slug}`,
    lastModified: post.datePublished,
    changeFrequency: 'yearly' as const,
    priority: 0.6,
  }));
  return [...pages, ...posts];
}
```

Add the index path to the shared `PUBLIC_PATHS` constant so it appears once, not twice.

### 6. Link it from the shared nav and footer

A new section nobody links to is not indexed the way you want. Add it to the header `NAV` array
and the footer `FOOTER_LINKS` array in the same commit.

### 7. RSS feed from the same array

Serve `/feed.xml` from a route handler (`app/feed.xml/route.ts`) so the body is a plain string with
an explicit content type. A static `feed.xml` file would need hand-regenerating on every publish.

Keep the builder a **pure function** in `lib/blog/feed.ts`, not code inlined in the handler. XML
has no forgiving mode: one unescaped `&` in a title makes the whole document unparseable, and feed
readers report that as an *empty feed* rather than an error — a silent failure. Separating the
builder lets the escaping and the date format be asserted without standing up a server.

```ts
export const FEED_PATH = '/feed.xml';

const XML_ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' };
// ONE pass. Sequential replaces turn `&amp;` into `&amp;amp;`, which renders literally.
export const escapeXml = (v: string) => v.replace(/[&<>"']/g, (c) => XML_ESCAPES[c]);

// RSS requires RFC 822, not the ISO 8601 used in the sitemap. Fall back to the epoch rather
// than emitting "Invalid Date", which corrupts the document.
export function rssDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? new Date(0).toUTCString() : d.toUTCString();
}

export function buildFeed(posts: Post[] = allPosts()): string {
  const feedUrl = `${SITE_URL}${FEED_PATH}`;
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    '  <channel>',
    `    <title>Site · Articles</title>`,
    `    <link>${escapeXml(SITE_URL)}</link>`,
    `    <description>${escapeXml(SITE_DESCRIPTION)}</description>`,
    '    <language>id-ID</language>',
    // Readers use this to find the canonical feed URL.
    `    <atom:link href="${escapeXml(feedUrl)}" rel="self" type="application/rss+xml"/>`,
    ...posts.map((p) => [
      '    <item>',
      `      <title>${escapeXml(p.title)}</title>`,
      `      <link>${escapeXml(`${SITE_URL}/artikel/${p.slug}`)}</link>`,
      `      <guid isPermaLink="true">${escapeXml(`${SITE_URL}/artikel/${p.slug}`)}</guid>`,
      `      <description>${escapeXml(p.description)}</description>`,
      `      <pubDate>${rssDate(p.datePublished)}</pubDate>`,
      ...p.keywords.map((k) => `      <category>${escapeXml(k)}</category>`),
      '    </item>',
    ].join('\n')),
    '  </channel>',
    '</rss>', ''].join('\n');
}
```

```ts
// app/feed.xml/route.ts
export const dynamic = 'force-static';
export function GET() {
  return new Response(buildFeed(), {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600, stale-while-revalidate=86400',
    },
  });
}
```

The keywords are already on each post, so `<category>` costs nothing. Omit `lastBuildDate`
entirely when the list is empty rather than emitting an empty element.

The feed needs no sitemap entry (a sitemap lists HTML pages) and no `robots.txt` change unless a
disallow rule happens to cover it. Discovery is the `alternates.types` link — see 6c in SKILL.md for
why declaring it only in the layout does not work.

## Pitfalls

- **`if (!post) notFound();` does not narrow the type.** TypeScript still reports `'post' is
  possibly 'undefined'` on every later use, because `notFound()` is typed to return `never` but a
  bare call does not terminate control flow as far as the checker is concerned. Write
  `if (!post) return notFound();` so narrowing applies. The same applies to any guard whose
  function is typed `never`.
- **Write content that agrees with the product.** If the app enforces rules (a bullet-count cap, a
  paper-size rule, a minimum number of skills), the article quoting those numbers must match the
  code — otherwise the blog and the feature contradict each other, and the blog is the version
  users will quote back. Check the rule constants against the prose before publishing.
- **Keep the claim-shape guard, not a banned-word list.** A test that forbids the vocabulary of a
  claim goes red on prose that *refutes* that claim ("no one can guarantee a pass rate"). Assert the
  pattern only a real claim matches — a figure adjacent to the promise. See
  `test-proof-discipline` rule 32.
- **Verify the rendered output, not just the build.** After deploy, fetch a post and confirm the
  headings, the `<time>` element, and the reading time actually render, then confirm the JSON-LD
  parses. A successful build only proves the file compiled.
- **Do not put a post's title in a `<title>`-only surface.** The detail page needs its own
  `generateMetadata`; inheriting the layout default makes every article share one title.
- **A `200` on a generated route is not proof the feature is discoverable.** A feed, sitemap, or
  OG endpoint can answer correctly while nothing in the served HTML points at it. Verify the
  discovery surface in the real HTML (`grep` the `<link rel="alternate">`), not the endpoint.
- **Assert no raw ampersand survives the escaping**, and parse the result with a real XML parser
  rather than a regex. A regex you wrote cannot tell "valid XML" from "XML I happen to match".

  ```ts
  const raw = feed.match(/&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-f]+);)/gi);
  expect(raw).toBeNull();
  ```

  ```bash
  node --experimental-strip-types -e "import('./lib/blog/feed.ts').then(m=>process.stdout.write(m.buildFeed()))" > /tmp/f.xml
  python3 -c "import xml.etree.ElementTree as E; r=E.parse('/tmp/f.xml').getroot(); print(r.tag, len(r.findall('channel/item')))"
  ```
