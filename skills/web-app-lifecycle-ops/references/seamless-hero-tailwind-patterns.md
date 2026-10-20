# Seamless Hero Section — Tailwind Patterns

Patterns extracted from Kelasin UI iterations.

## Seamless color continuity

**Problem:** A white container between the carousel and text panel created a visible separator even when the intended design was seamless blue-on-blue.

**Fix:**
1. Remove `bg-white` from the inner image container and outer carousel wrapper.
2. Set the section `bg-*` to the same value as the text panel `bg-*`.
3. Leave the image container transparent so PNG transparency reveals the shared background.

```tsx
// ❌ Before: three discrete color zones
<section className="bg-[#0f39bf]">    // dark blue
  <div className="bg-white">             // white — creates a visible card
    <div className="bg-white">           // white image area
      <img className="object-contain bg-white" />
    </div>
    <div className="bg-[#1452ea]">       // medium blue — different from section
      <h1>Headline</h1>
    </div>
  </div>
</section>

// ✅ After: one continuous blue with floating images
<section className="bg-[#1f57ea]">    // same blue as panel below
  <div>                                  // transparent — no bg-*
    <div>                                // transparent
      <img className="object-contain" /> // no bg-* — PNG transparencies show section bg
    </div>
    <div className="bg-[#1f57ea]">       // identical to section bg
      <h1>Headline</h1>
    </div>
  </div>
</section>
```

## Overlay div removal on product card images

**Problem:** Product card thumbnails looked washed out because a semi-transparent overlay sat on top of the image.

**Fix:** Remove the overlay `<div>` entirely. Don't just reduce opacity — the image at full quality with `object-cover` looks cleanest.

```tsx
// ❌ Before
<div className="relative h-[230px]">
  <img className="absolute inset-0 h-full w-full object-cover" />
  <div className="absolute inset-0 bg-[#e9f4ff]/70" />  {/* washes out image */}
  <Badge />
</div>

// ✅ After
<div className="relative h-[230px]">
  <img className="absolute inset-0 h-full w-full object-cover" />
  <Badge />    {/* badge survives — it's a normal positioned overlay, not a wash */}
</div>
```

Also change the card article background from tinted to white:
```tsx
// ❌ Before
className={[isFeatured ? 'bg-[#f3f3f3]' : 'bg-[#e9f4ff]', ...].join(' ')}

// ✅ After
'bg-white',  // card backgrounds are always clean white
```

## Carousel text outside image container

**Problem:** Banner caption text overlapped with artwork text baked into the banner PNG.

**Fix:** Move the heading/CTA `<div>` to *after* the aspect-ratio container closes, not as an `absolute` child inside it.

```tsx
// ❌ Before: text inside the image box
<div style={{ aspectRatio: '16/9' }}>
  <img />
  <div className="absolute bottom-0">   {/* fighting with PNG text */}
    <h1>Temukan Kelas Favoritmu di Sini!</h1>
  </div>
</div>

// ✅ After: text below the image box
<div style={{ aspectRatio: '16/7' }}>
  <img />
</div>
<div>                                     {/* its own layout slot */}
  <h1>Temukan Kelas Favoritmu di Sini!</h1>
  <Link>Telusuri Pelatihanmu!</Link>
</div>
```

## Carousel nav controls — Figma-like positioning

When the reference places nav indicators *vertically* on the right side (not horizontal center):

```tsx
// Dots as vertical stack on the right
<div className="absolute bottom-4 right-16 flex flex-col gap-1.5">
  {slides.map((_, i) => (
    <button className={[
      'w-3 rounded-full transition-all duration-300',
      i === activeSlide
        ? 'h-6 bg-[#1f57ea]'    // taller = active
        : 'h-3 bg-[#7aa7ff]',   // shorter = inactive
    ].join(' ')} />
  ))}
</div>

// Prev button: bottom-left, simple text chevron
<button className="absolute bottom-4 left-4 text-[1.5rem] text-[#505050]">
  <span>{'<'}</span>
</button>

// Next button: bottom-right, circular bordered
<button className="absolute bottom-4 right-4 h-8 w-8 rounded-full border border-[#c9d4ef] bg-white/92 text-[#2d69ef]">
  <span>{'>'}</span>
</button>
```

## Version history

- 2026-06-09: Initial — Kelasin hero seam fix, product card overlay removal, carousel text extraction.
