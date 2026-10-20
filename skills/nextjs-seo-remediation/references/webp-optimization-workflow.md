# WebP Image Optimization Workflow

When an SEO audit flags "images use inefficient format" or "image file sizes are too large", this workflow converts assets and updates all references systematically.

## Measurement & Assessment

**Identify bloat:**
```bash
du -sh public/images/*.{jpg,jpeg,png} | sort -h
```

**Expected reductions by format:**
- PNG logos (flat color, no gradients): 90–97% smaller
- PNG marketing/mascot images: 80–90% smaller
- JPEG photos: 50–65% smaller
- JPEG QR codes / simple graphics: 60–80% smaller

## Conversion Process

**Using Python PIL/Pillow:**
```python
from PIL import Image
import os

images = [
    ("public/images/logo.png", "logo"),
    ("public/images/hero.jpg", "hero"),
]

for src, name in images:
    if not os.path.exists(src):
        continue
    
    img = Image.open(src)
    base_dir = os.path.dirname(src)
    webp_path = os.path.join(base_dir, f"{name}.webp")
    
    # Quality 80 is a good default; adjust per image if needed
    img.save(webp_path, "WEBP", quality=80)
    
    orig_size = os.path.getsize(src)
    webp_size = os.path.getsize(webp_path)
    reduction = (1 - webp_size / orig_size) * 100
    print(f"{name}: {orig_size/1024:.1f}K → {webp_size/1024:.1f}K ({reduction:.1f}% smaller)")
```

**Using ImageMagick (CLI):**
```bash
convert input.png -quality 80 output.webp
```

## Component Reference Updates

**Search for all occurrences:**
```bash
grep -r "meow-logo\.png\|meow-mascot\.png\|favicon\.jpg" components/ app/ --include="*.tsx"
```

**Update each next/image call:**
- Change `src="/path/old.png"` to `src="/path/new.webp"`
- Add or update the `sizes` prop with responsive breakpoints
- Keep `priority` prop for above-fold images (hero, nav logo)
- Add implicit `loading="lazy"` for below-fold images (Next.js default)

**Example before:**
```tsx
<Image
  src="/images/meow-mascot.png"
  alt="Meow Labs Mascot"
  width={400}
  height={400}
  className="..."
  priority
/>
```

**Example after:**
```tsx
<Image
  src="/images/meow-mascot.webp"
  alt="Meow Labs Mascot"
  width={400}
  height={400}
  className="..."
  priority
  sizes="(max-width: 640px) 280px, (max-width: 1024px) 360px, 400px"
/>
```

## Structured Data Updates

If the image appears in JSON-LD (schema.org), update the reference there too:

**Before:**
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "logo": {
    "@type": "ImageObject",
    "url": "https://example.com/images/meow-logo.png",
    "width": "512",
    "height": "512"
  }
}
```

**After:**
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "logo": {
    "@type": "ImageObject",
    "url": "https://example.com/images/meow-logo.webp",
    "width": "512",
    "height": "512"
  }
}
```

## Verification

1. **Build check:**
   ```bash
   npm run build
   ```
   All routes must generate successfully. No image-not-found errors.

2. **Visual check:**
   Start dev server and inspect images in browser DevTools:
   ```bash
   npm run dev
   # Open http://localhost:3000, right-click image → Inspect → Network tab
   # Confirm .webp is being served
   ```

3. **Audit re-check:**
   Run SEO audit 24–48 hours after deployment to allow cache refresh on live site.

## Common Pitfalls

- **Forgetting component updates**: Converting `.png` to `.webp` but leaving `src="/path/old.png"` in code will result in 404 or image-not-found audit failures.
- **Missing responsive sizing**: Adding `sizes` prop is necessary for audit compliance and for Next.js to generate appropriate srcset variants.
- **Hardcoding quality too high**: WebP quality 85+ often shows no visible difference from PNG but adds file size back. Quality 75–80 is the sweet spot for most images.
- **Not updating schema.org**: SEO audits check structured data for broken image URLs. Update JSON-LD references alongside component changes.

## Batch Workflow (Multi-File)

When multiple images need conversion:

1. Create Python script to batch-convert and report reductions
2. Search for all references (grep + IDE find-and-replace)
3. Update components systematically (sort by file, then by import order)
4. Update schema.org references in `app/layout.tsx` and any page-level metadata
5. Commit with detailed message listing each file changed
6. Build verify before pushing
7. Deploy and monitor for image-serving issues in first 24h

## Browser Support

WebP is supported in all modern browsers (Chrome, Firefox, Safari 16+, Edge). No fallback needed for sites targeting modern traffic. For older browser support (unlikely in 2026), Next.js Image component can serve fallbacks via the `unoptimized` prop or dual-format srcset, but this is rarely necessary now.
