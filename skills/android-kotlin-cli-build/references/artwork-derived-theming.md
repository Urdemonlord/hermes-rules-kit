# Artwork-derived theming (color taken from the playing track's cover art)

Deriving UI colors from a song's artwork (the Apple-Music behavior) in a Compose app. Covers the
scope decision, the palette rules, the Coil/bitmap crash, and how to verify without a device.

## 1. Scope first: "theme" usually means one screen, not the whole app

Before planning a "theme change", measure how the app actually reads color:

```bash
grep -rn 'MaterialTheme.colorScheme' app/src/main/kotlin/ | wc -l
grep -rc '<YourColors>\.' app/src/main/kotlin --include=*.kt | grep -v ':0$' | sort -t: -k2 -rn
```

If screens read a hardcoded palette object directly (hundreds of call sites across dozens of files)
rather than `MaterialTheme.colorScheme`, then "make the whole theme artwork-derived" is a repo-wide
refactor with a large regression surface — and it will collide with a design spec that locks the
palette (dark-only, dynamic color off).

The user's wording is usually narrower than the feature name: "colors from the track that is
playing" is a **Now Playing layer**, not a global theme. Read the design spec before planning — it
often already authorizes the narrow slice ("gradient from artwork to background", "gradients only
from artwork", "placeholder may use the dominant color"). Implement the slice the spec and the
user's words both point at, and get the spec amended first if the standing rule is broader.

## 1b. "Remove the dynamic theme" is ambiguous — identify the target before deleting anything

"Dynamic color" / "dynamic theme" names at least three unrelated things, and the user's phrase
does not distinguish them. Deleting the wrong one removes a feature instead of a config toggle:

| What it could mean | How to identify it | Cost to remove |
|---|---|---|
| Material You dynamic color | `dynamicDarkColorScheme` / `dynamicLightColorScheme` in the theme file | Usually nothing — often already absent |
| Artwork-derived theming | A Settings toggle, a palette module, an extractor, a stored preference | A user-visible FEATURE — do not delete on a vague request |
| Themed (monochrome) launcher icon | `<monochrome>` inside `mipmap-anydpi-v26/ic_launcher*.xml` | One line, two files |

**Check whether Material You exists at all before offering to remove it.** A dark-only app that locks
its palette has usually never wired it up, and saying "removed" for something that was never there is
a false claim. Confirm from the code AND the whole history — a symbol can be absent from the working
tree yet present in an older commit:

```bash
grep -rn 'dynamicDarkColorScheme\|dynamicLightColorScheme' app/src
git log -S dynamicDarkColorScheme --oneline --all   # empty = never existed, so nothing to remove
```

When it is genuinely absent, say so plainly and name the thing that IS still following the system,
rather than deleting something adjacent to look responsive. **In a Compose app with a locked palette
the last remaining system-following element is usually the themed launcher icon**: `<monochrome>` in
the adaptive-icon XML makes Android 13+ recolor the icon from the user's wallpaper, so the brand
colour disappears and every app on that launcher turns the same grey. Removing that element is the
whole fix:

```xml
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/<brand_surface>" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <!-- no <monochrome>: keeps the brand colour under "Themed icons" -->
</adaptive-icon>
```

**Verify the removal inside the built APK, not in the source** — the icon XML is compiled to binary
and a stale resource would not show up in a source grep:

```bash
python3 - <<'PY'
import zipfile
z = zipfile.ZipFile("app-release.apk")
hit = [n for n in z.namelist() if "ic_launcher" in n and b"monochrome" in z.read(n)]
print("still themed:", hit or "none")
PY
```

Note the side effect in the changelog and in the report: on devices with "Themed icons" enabled the
icon no longer follows the wallpaper. That is the intended outcome, not a regression, and the user
should hear it as such.

## 2. Keep the color RULES pure and unit-tested; only extraction touches Android

Store colors as ARGB `Int`, not `android.graphics.Color` or Compose `Color`. The selection rules
(thresholds, quantization, darkening) are numeric, so as `Int` they run in a plain JVM unit test —
no device, no Robolectric. Convert to `Color` at the call site.

Palette rules that matter:

- **Threshold out greys.** Cover art is mostly grey/black/white. Taking the most frequent color with
  no filter yields a muddy grey background that erases the track's character. Require a minimum HSV
  saturation for the accent, and a luminance band (too dark is invisible on a dark theme, too bright
glares).
- **Compute relative luminance the WCAG way (gamma-decode first), or every threshold on top of it
  is meaningless.** `0.2126*R + 0.7152*G + 0.0722*B` over sRGB values in 0..1 is *luma on
  gamma-encoded values*, NOT WCAG relative luminance — it over-reads mid/dark colours badly
  (`rgb(200,40,40)` comes out 0.29 instead of 0.14). Linearise each channel first
  (`c <= 0.03928 ? c/12.92 : ((c+0.055)/1.055)^2.4`). A wrong metric does not fail loudly; it just
  makes every threshold built on it arbitrary — here it pushed the "too dark" cut so high that most
  artwork was darkened until its colour was gone. **When you fix the metric, re-derive the
  thresholds**: the old numbers were tuned against the wrong curve, so a vivid blue
  (`rgb(40,40,200)`, true luminance 0.06) is thrown out by an accent floor of 0.20 that looked
  reasonable on the wrong scale. Then re-check the borderline colours in your own tests —
  `rgb(80,255,80)` is 0.738, not "just above 0.80".
- **Quantize before counting.** A smooth gradient splits one color into hundreds of near-identical
  buckets, each too rare to win, so the winner becomes pixel noise. Bucket each channel to ~3 bits
  (8 levels), count buckets, then average the ORIGINAL channel values of each bucket's members so the
  output is a real color rather than the bucket center.
- **Darken multiplicatively, with a step cap.** To build a background under light text, multiply the
  channels toward black (keeps the hue — red stays dark red instead of fading to grey) and cap the
  loop (`repeat(32)`); an unbounded loop here hangs the UI on every track change.
- **"No usable color" is a legitimate result, not an error.** B/W covers, failed loads, and blank
  URLs all return null; the caller falls back to the app's own palette, which is the correct outcome.

## 3. The bitmap trap: `allowHardware(false)` or `getPixels()` crashes on device

`Bitmap.getPixels()` throws `IllegalArgumentException` on a bitmap whose config is
`Bitmap.Config.HARDWARE`, and Coil decodes to HARDWARE by default on API 26+. So reading pixels from
any Coil-loaded image crashes on the device — and **no unit test catches it**, because the crash
needs a real hardware bitmap.

```kotlin
ImageRequest.Builder(context)
    .data(url)
    .allowHardware(false)   // REQUIRED before any getPixels() / copyPixelsToBuffer()
    .size(48)               // downscale at DECODE time; 48px is plenty for a dominant color
    .build()
```

Other cheap wins: read all pixels in ONE `getPixels(...)` call (per-pixel `getPixel` is thousands of
JNI calls and reads as a stutter), and `recycle()` the bitmap you own after reading it.

Use the app's singleton loader (`context.imageLoader`, configured via `ImageLoaderFactory` on the
`Application`) so an image already displayed is not fetched twice — it comes from the memory/disk
cache. Do not build a second `ImageLoader` per screen.

## 4. Caches: two traps

**Absent is not null.** A cache that stores a nullable result must use `containsKey`, not
`cache[key]?.let { return it }` — the latter cannot distinguish "not computed yet" from "computed,
no color", so a B/W cover is recomputed on every play, which is exactly what the cache was for. If
its comment claims it handles this, check that the code does.

```kotlin
synchronized(cache) { if (cache.containsKey(url)) return cache[url] }
```

**"Pick the max" over a `HashMap` is non-deterministic on ties.** `HashMap` iteration order is not
guaranteed, so when two buckets have equal counts the winner can differ between runs and the
background flickers when a track is replayed. Tie-break on a stable key (the smallest bucket id),
never on iteration order.

Bound the cache (LRU, e.g. 64 entries) — a session plays hundreds of tracks. Prefer **manual LRU
eviction** over subclassing `LinkedHashMap` with an overridden `removeEldestEntry`: that override's
parameter is Java's `Map.Entry` (a platform type) and its exact shape is easy to get wrong in a way
you cannot confirm without compiling. A plain `LinkedHashMap(accessOrder = true)` you mutate yourself
(on hit: remove then re-insert to move the entry to the back; when over capacity: drop the first key)
is obviously correct on inspection and needs no override.

## 5. Verifying without a device

- **Port the pure rules to Python and run the cases there** before compiling. When you cannot run
  the Kotlin test yet, this is the cheapest way to catch an arithmetic mistake in thresholds or
  darkening.
- **Confirm the API you need lives in the artifact you actually depend on.** An extension such as
  `context.imageLoader` lives in `coil`, not `coil-compose`; `coil-compose` pulls `coil`
  transitively. Confirm from the POM and the bytecode rather than guessing:

```bash
curl -s https://repo1.maven.org/maven2/io/coil-kt/coil-compose/2.7.0/coil-compose-2.7.0.pom \
  | tr -d ' ' | grep -A2 '<artifactId>'
curl -s -o /tmp/coil.aar https://repo1.maven.org/maven2/io/coil-kt/coil/2.7.0/coil-2.7.0.aar
unzip -oq /tmp/coil.aar -d /tmp/coil
javap -p -classpath /tmp/coil/classes.jar 'coil.-SingletonExtensions'   # quote the $-name
```

androidx artifacts (`androidx.core:core-ktx`, `androidx.core:core`) are on Google's Maven
(`https://dl.google.com/dl/android/maven2/...`), not Maven Central — a Central 404 is not "missing".
`androidx.core.graphics.drawable.toBitmap` (a `Drawable` extension) lives in
`androidx.core:core-ktx`'s `DrawableKt`.

- **Confirm the packing convention of the `Color(Int)` you construct.** A palette kept as ARGB `Int`
  is converted at the call site; if the constructor expected plain RGB the colours would be visibly
  wrong but the code still compiles. Check `ColorKt.Color(int)` in the `ui-graphics` bytecode (the
  int is packed as ARGB, alpha in the high byte) rather than assuming.
