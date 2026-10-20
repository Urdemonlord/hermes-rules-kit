# Replacing a launcher icon with a real illustration

Use when the user hands over an image (logo/illustration/mockup) and says "pake ini" for the
app icon. The mechanical part is easy; the decisions that decide whether it reads well at
launcher size are the work.

## Measure the artwork before choosing a scale

Adaptive icons reserve the outer ring for the launcher's mask. The guaranteed-visible zone is
the inner **66.7%** (72dp of the 108dp canvas); everything outside can be cropped by a circle,
squircle, squog, teardrop, or the OEM's own shape. Compute where the subject actually sits
rather than assuming it is centred:

```python
px = im.load(); step = 4
# brightness threshold separates a subject from a dark backdrop
mask = px[x, y].sum() > 260          # tune the threshold to the image
bbox = min/max x,y over masked samples, normalised by width/height
```

Two numbers decide the layout: the subject's **bounding box** (does it already overflow the
safe zone?) and its **centroid** (an off-centre subject must be scaled *about its own centre*,
not about the canvas centre, or scaling silently pushes it out of frame).

Render the real sizes before deciding. Launcher icons are seen at 48–96dp surrounded by
dozens of other icons; a design that looks generous at 512px can be illegible at 48dp. A
two-row comparison sheet — variant × {squircle, circle} × {48, 60, 72, 96}px, supersampled
~4x then downscaled — takes one script and settles the question with the user's eyes instead
of an argument. Then ask the user to pick; do not pick a crop and install it unasked.

## The trade-off you must state before installing the art

Fitting the subject to the full safe zone makes the icon's **visual area roughly 44%** of the
canvas (0.667²). Full-bleed artwork fills ~100%. Neighbours are almost all full-bleed, so the
safe-zone icon reads as noticeably smaller in a launcher grid. Say this plainly when
presenting the variants: "B survives every mask, but it will look smaller than the icons
around it." Let the user trade legibility against visual weight — that is a taste call, not
a technical one.

## Ask provenance before bundling third-party art

An icon's legal-safety story is usually written down somewhere: check for a comment in the
existing icon file stating why it is hand-drawn ("no third-party assets"). Replacing it with
an imported image silently voids that guarantee, and the next session reads the stale claim as
fact. Confirm the source before bundling (own work / AI-generated / licensed / unknown), and
if the answer is "unknown", say so rather than proceeding silently on a private app's luck.

**A design spec that forbids what the icon now does becomes a lie the moment it ships.** Grep
the project's canonical design doc for the constraint the new art violates — "no illustration",
"no character's face", "identity comes from typography, not imagery" — and update the spec
*in the same change*. A spec that contradicts the shipped UI is worse than no spec, because
the next session enforces it as a locked decision and reverts good work to satisfy it.

**Expect the forbidden constraint to appear at SEVERAL sites, and scope the amendment rather
than deleting the rule.** One such project asserted "no visual identity" in a boundary section
AND "not an anime illustration" in the placeholder section; correcting only the first leaves the
second as a live contradiction. Sweep for all of them, then write the amendment as a *narrowed*
rule with the reason it narrowed — here, "this applies in-app, where each song already has
artwork; the launcher is the one place a face is the differentiator" — plus an explicit list of
what did NOT change (in-app placeholders, mood browse, the palette). A deletion leaves the next
session free to re-litigate; a scoped amendment with a stated boundary ends the argument.

## Wire it up: density buckets, and the layer split

For a raster illustration, drop `ic_launcher_foreground` as PNGs in `drawable-<density>/` at
the canonical adaptive-icon sizes — mdpi 108, hdpi 162, xhdpi 216, xxhdpi 324, xxxhdpi 432.
Point the existing `<adaptive-icon>` at them; no manifest change is needed when
`minSdk >= 26` and only `mipmap-anydpi-v26/` exists.

Split layers the way the launcher expects:

```xml
<adaptive-icon>
    <background android:drawable="@color/icon_bg" />          <!-- solid, matches the art's edge -->
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
</adaptive-icon>
```

Sample the background colour from the artwork's own edge pixels — a one-to-two pixel pure-black
border (a JPEG artefact or an intentional frame) is **not** the backdrop; sample a band a few
percent in and take the non-black average. Compose the foreground onto that same colour so the
system mask's cut edge has no visible seam.

**There are TWO adaptive-icon files, and editing only one ships two different icons.** A
template project has both `mipmap-anydpi-v26/ic_launcher.xml` and `ic_launcher_round.xml`,
referenced from the manifest as `android:icon` and `android:roundIcon`. Grep for every
reference rather than editing the file you happen to open first:

```bash
grep -rn 'adaptive-icon\|android:roundIcon' app/src/main/res app/src/main/AndroidManifest.xml
```

Change the `<background>` drawable in BOTH. The failure is silent and launcher-dependent —
a device set to round icons keeps the old background forever while the rest of the device sees
the new one, so the mismatch reproduces only on the devices you did not test on.

**Re-read every comment you edited in the icon files.** Icon templates carry explanatory
comments, and they go stale: a header saying "pure vector" is a false claim the moment the
vector is replaced by PNGs, and a `<background>` swap invalidates any comment naming the old
colour. A stale comment is worse than no comment because the next session reads it as a locked
decision.

**Check `<monochrome>` before you touch the icon.** If the project deliberately omits it, the
reason is in the file's comment and it still holds: themed icons (Android 13+) recolour the
launcher icon from the wallpaper, which flattens a multi-colour illustration to a single
system tint. Read the existing file's comment and do not "helpfully" add it back.

## Prove the icon is in the built APK

Vector-only icon changes are caught by the compiler; a raster swap is not. After CI builds the
release artifact, confirm the buckets actually shipped and at the right sizes:

```bash
unzip -l App-release.apk | grep ic_launcher          # all densities present?
aapt2 dump badging App-release.apk | grep -i icon
```

An empty grep means the resource did not get packaged and the launcher will fall back to a
default — a silent failure that no unit test catches. Then confirm the adaptive-icon XML in the
APK still points at the new drawable (`unzip -p App-release.apk res/.../ic_launcher.xml` is
binary; `aapt2 dump xmltree` on it is not).
