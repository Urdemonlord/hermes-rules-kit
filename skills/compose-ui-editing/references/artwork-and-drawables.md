# Artwork and Drawable Resources

Depth for regenerating raster assets and swapping drawables in a Compose app.

## Density buckets

| Bucket | Multiplier | Launcher foreground (108dp) | In-app tile (48dp) |
|---|---|---|---|
| `mdpi` | 1x | 108 px | 48 px |
| `hdpi` | 1.5x | 162 px | 72 px |
| `xhdpi` | 2x | 216 px | 96 px |
| `xxhdpi` | 3x | 324 px | 144 px |
| `xxxhdpi` | 4x | 432 px | 192 px |

One source image, square, exported at every bucket. Never hand-scale one bucket and
copy it to the others — resampling artifacts differ per density and the bug only
shows on one device class.

## Adaptive icon safe zone

Android guarantees only the centre **66.7%** of the canvas survives every OEM mask.
Full-bleed artwork therefore has its edges eaten by circle and squircle masks.

```
108dp canvas
┌───────────────────┐
│  ░░░░░░░░░░░░░░░  │  16.7% mask allowance on each side
│  ┌─────────────┐  │
│  │ ▓ safe zone │  │  72dp — subject must live here
│  │ ▓ 66.7%    ▓  │
│  └─────────────┘  │
│  ░░░░░░░░░░░░░░░  │
└───────────────────┘
```

Layer an opaque background colour behind the foreground so the safe zone is not a
hole: `<background android:drawable="@color/icon_background"/>`. The background is a
resource, not a runtime theme — `res/values/colors.xml` cannot follow a runtime theme,
so leave it static and say so in a comment.

**`<monochrome>` is a separate layer, not a fallback.** Android 13+ renders it as a
flat tinted silhouette for themed icons. Adding it discards the artwork's colour. Omit
it unless a themed-icon variant is genuinely wanted.

## Crop for an in-app tile

No mask crops an in-app tile, so the tight launcher framing is wrong there. Crop
closer to the subject so it reads at 48dp, and leave margin so the tile's own gradient
still shows around it.

Parameters to tune, as fractions of the source:

| Parameter | Launcher | Tile |
|---|---|---|
| subject scale | ~0.66 (safe zone) | ~0.85 (tighter) |
| vertical centre | subject-centred | nudged up, so a crop does not clip the crown |
| rendered fraction of the tile | fills the safe zone | ~0.55 of the tile box |

A diagonal or off-centre crop reads as an accident, not a composition. Render two or
three candidates and compare them at final size before choosing.

## Mask-compositing preview

The only reliable check is to composite the real masks over the foreground and look:

```python
from PIL import Image, ImageDraw

CANVAS = 432          # xxxhdpi foreground
fg = Image.open("ic_launcher_foreground.png").convert("RGBA")
preview = Image.new("RGBA", (CANVAS * 3, CANVAS), (20, 16, 20, 255))  # icon background

masks = [
    ("circle",     ImageDraw.Draw(preview).ellipse,   (0, 0, CANVAS, CANVAS)),
    ("squircle",   round_rect,                        (0, 0, CANVAS, CANVAS)),
    ("rounded",    round_rect,                        (0, 0, CANVAS, CANVAS)),
]
for i, (_, draw, box) in enumerate(masks):
    x = i * CANVAS
    preview.paste(fg, (x, 0), fg)
    # mask by punching the outside transparent, then composite the background back
    ...
```

Preview at the sizes that matter too: a 108px launcher-grid thumbnail reads differently
from a 432px app-drawer icon, and in-app 48dp is smaller again.

## Vector → raster migration checklist

1. Export the PNGs at every bucket into the matching `drawable-<bucket>/` directory.
2. Delete the old XML drawable in the same commit. Leaving both means a stale
   reference still compiles and ships the wrong asset.
3. Swap `Icon(painter, tint)` → `Image(painter)` at every call site. `Icon`'s
   `ColorFilter` destroys the raster's colour.
4. Grep the spec and docs for the old asset name and the old description; rewrite
   what is now false, and turn absolute prohibitions into named exceptions.
5. Verify the resources actually landed in the built artifact. R8 obfuscates resource
   names, so `unzip -l app.apk | grep ic_launcher` finds nothing and its empty output
   reads as "the asset is missing" when it is present:

   ```bash
   aapt2 dump resources app-release.apk | grep -A2 drawable/ic_launcher
   ```

   Match on the resource path, or on expected byte sizes, not the filename.

## Exporting the tile background

The illustration usually has its own opaque background. Compose it onto the exact
colour the tile gradient resolves to, so the asset's edge is invisible:

```python
BG = (20, 16, 20)   # same value as the icon background resource
```

Getting this wrong leaves a visible seam on one density only — check the largest
bucket first, it shows it most clearly.
