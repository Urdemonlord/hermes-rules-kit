# Social card (og:image) verification for Next.js App Router

Use when a site's link previews are missing images, or after adding `opengraph-image.tsx` to a
sub-route. The failure is invisible in the build and in a normal page fetch — it only shows up when
a link is unfurled by WhatsApp, LinkedIn, Slack, or X.

## Why sub-routes lose their image

`app/opengraph-image.tsx` is a **route-segment** convention. It applies to that segment only;
Next.js does not cascade it into children. A site with a working homepage card and no card on
`/blog`, `/blog/[slug]`, `/templates` is the normal outcome of adding one file at the root, not a
configuration mistake.

## The tell: card type without an image

The metadata emitter and the image route are separate code paths, so they can disagree:

```
twitter:card   → summary_large_image     ← present
og:image       → (absent)
twitter:image  → (absent)
```

Always check `og:image` and `twitter:image` **per route**. A present `twitter:card` proves nothing
about the image.

## Probe

```bash
UA='Mozilla/5.0 (compatible; Twitterbot/1.0)'
for p in "" "blog" "blog/my-post" "templates"; do
  html=$(curl -sS --max-time 20 -A "$UA" "https://example.com/$p")
  og=$(printf '%s' "$html" | grep -o 'property="og:image" content="[^"]*"' | head -1)
  tw=$(printf '%s' "$html" | grep -o 'name="twitter:image" content="[^"]*"' | head -1)
  printf '/%-28s og=%s | tw=%s\n' "$p" "${og:-MISSING}" "${tw:-MISSING}"
  # absolute URL required: a relative og:image is ignored by most crawlers
  case "$og" in *'http'*) ;; "") ;; *) echo '  WARN: og:image is not absolute' ;; esac
done
```

## Verify the images are real and distinct

A 200 with `image/png` and a valid PNG header is not proof the right image rendered — a fallback
placeholder passes every one of those checks.

```bash
for s in post-a post-b post-c; do
  curl -sS "https://example.com/blog/$s/opengraph-image" -o "og-$s.png" \
    -w '%{http_code} %{content_type} %{size_download}\n'
done
md5sum og-*.png          # distinct hashes => per-page content, not one cached fallback
file og-*.png            # 'PNG image data, 1200 x 630' => correct canvas
```

Then **look at one image**. Checks that confirm file type, dimensions, and a distinct hash still
cannot see clipped or overlapping text, which is the most common defect when the title is injected
into a fixed canvas.

## Per-segment image with the page's own title

```tsx
// app/blog/[slug]/opengraph-image.tsx
type Params = Promise<{ slug: string }>;   // Next 15+ params are async

export const alt = 'Article';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default async function OpengraphImage({ params }: { params: Params }) {
  const { slug } = await params;
  const title = getPost(slug)?.title ?? 'Article';
  // Shrink for long headlines or they overflow the canvas.
  const fontSize = title.length > 68 ? 54 : title.length > 44 ? 62 : 70;
  return new ImageResponse(
    (<div style={{ /* flex column, padding, dark gradient */ }}>{title}</div>),
    size,
  );
}
```

Counts and labels in these images should be read from the same constants the pages use
(`allPosts().length`, `TEMPLATE_IDS.length`) rather than typed in, so an image cannot go stale
against the page it advertises.

## Pitfall: `generateImageMetadata` + `{ params }` is silently wrong

`generateImageMetadata` switches the default export's argument from `{ params }` to `{ id }`.
Combining them leaves `params.slug` undefined, so every page renders the placeholder title — and
**the build succeeds**, so CI cannot catch it. Only a per-route image inspection reveals it.

Use one form or the other:
- single image needing route params → `alt` / `size` / `contentType` + default export `{ params }`
- multiple named images in one segment → `generateImageMetadata` returning `[{ id, alt, size, contentType }]`
  and a default export reading `{ id }`

## Localised date rendering

When the page renders a date through `toLocaleDateString`, the card and the page can disagree if
only one sets a locale. Keep the formatting helper shared so the card, the article, and the
`<time dateTime=...>` attribute all describe the same instant.
