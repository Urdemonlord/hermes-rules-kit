# Compose motion + the design-spec contract

Depth for adding or changing motion in a Compose app whose `docs/design-spec.md` is the canonical
source of visual truth ("perubahan visual harus lewat sini dulu"). Two halves: how to satisfy a
numeric design rule so CI enforces it, and the artwork-crossfade recipe as a worked example.

## The spec is canonical, so the change includes updating it

When the user asks for motion that the design-spec does not describe, the work is not done at the
code — the spec is the source of truth and it is now behind. Two checks before calling it finished:

- **Grep the spec for the contract first; a no-result is a finding, not a green light.**
  `grep -in 'crossfade\|ganti lagu' docs/design-spec.md` returning nothing means the contract you
  are about to implement is undocumented, so add it (a row in the motion table plus a short
  implementation note stating that the millisecond figure is a target routed through the shared
  motion object, not a literal). A spec that only describes the old behaviour will contradict the
  new code on the next read.
- **Update any comment or doc that asserted the feature was absent.** A settings screen often
  carries a note like "deliberately no settings for things that do not work yet (audio quality, …)";
  the moment the feature lands, that sentence is false and actively misleads the next reader into
  thinking the row was never built. Grep the screen and the spec for the feature name and fix every
  statement that says it does not exist — a stale denial is worse than no comment.

## Durations in the spec are TARGETS, not literals

A design table like "Play button 150ms / Mini player slide 200ms / Crossfade artwork 150ms" reads
like a list of magic numbers to paste into each `animationSpec`. Pasting them produces a codebase
with one `tween(150)` here and one spring there — each locally defensible, collectively two
different rhythms, which is exactly what the spec's "calm, immersive, cinematic" rule forbids.

The binding rules are the ones stated as PROHIBITIONS, not the millisecond figures:

- "no bouncing spring" → `dampingRatio = 1.0` (critically damped). Hard floor `0.8`.
- "animations must not be flashy" → small travel distances, short durations.

So the pattern is: **one shared motion object owns the tempo; every call site names a slot in it.**
The spec's millisecond figures become the *target the slot approximates*, and the comment on the
object says so. If a slot needs a different value later, one file changes.

## Enforce the numeric rule with a unit test, not a convention

Any design rule that reduces to a number is testable, and a rule enforced only by convention gets
violated by the next well-meaning "make it feel more alive" edit — a changed `dampingRatio` looks
innocent in a diff and is only observable on a device.

```kotlin
@Test fun `no spring bounces`() {
    springSpecs().forEach { spec ->
        assertTrue("dampingRatio ${spec.dampingRatio} < 0.8 — spec violated",
                   spec.dampingRatio >= MIN_DAMPING)
    }
}
```

Two design decisions this test forces, both good:

- **Expose the specs so they can be read.** A `private` spec constant is untestable; the motion
  object needs accessors (`fastSpatialSpec()`, `defaultEffectsSpec()`, plus a named one per
  contract) even if production code only uses some of them.
- **Give each contract its OWN named function rather than reusing a generic slot.** A crossfade
  that calls `defaultEffectsSpec()` has no name a test or a reviewer can point at. A named
  `artworkCrossfadeSpec()` can be asserted, and its KDoc carries the reason it exists. If the
  artwork tempo later needs to diverge from the tab-switch tempo, only that function changes.

**Pick the right slot kind: spatial (spring) vs effects (tween).** Position/size changes want the
spring (that is what makes motion feel responsive). Pure alpha/opacity changes want a `tween` —
springing an alpha adds cost with nothing visible. Crossfades are effects.

## Artwork crossfade on track change

**`AsyncImage.crossfade(true)` is NOT this feature.** That flag crossfades the *image load*
(placeholder → decoded bitmap) inside one composable. "Crossfade artwork when the track changes" is
a different thing: fading the old track's artwork out while the new one fades in. The existing flag
can be present and the feature still absent — check for a `Crossfade`/`AnimatedContent` keyed on
the song, not for `.crossfade(`.

```kotlin
Crossfade(
    targetState = song?.artworkUrl ?: song?.id,   // artwork identity: same cover => no fade
    animationSpec = BlossomMotion.artworkCrossfadeSpec(),
    label = "artwork",
) { key ->
    CoverImageBox(song = if (key == null) null else song, /* … */)
}
```

Decisions that matter:

- **Key on the ARTWORK IDENTITY, not the song ID.** The crossfade exists to soften a change of
  *image*; two tracks from the same album share a cover, so keying on the song id makes the artwork
  blink through an identical picture on every track change. Key on the artwork URL (fall back to
  `song?.id` only when there is no artwork): the transition then fires exactly when the picture
  actually changes. A useful side effect — in a list where each row already has a stable `key=`, the
  rebind does not re-run the transition at all, so a long list costs nothing.
- **Do not key on the `SongEntity` object.** Re-emitting an equal-but-new instance restarts the
  crossfade for no reason. This is the weaker half of the point above; the artwork key already
  subsumes it.
- **Put the `Crossfade` INSIDE the outer container, not around it.** In Now Playing the artwork
  sits in a `Box` that applies `.blur(80.dp)`. Wrapping the blur *outside* the crossfade renders
  two blurred layers during the transition — double GPU cost on a weak device, and the blur is the
  expensive part. Keep the blurred container single and crossfade its contents.
- **`Crossfade`'s `animationSpec` parameter is `FiniteAnimationSpec<Float>`** — pass the effects
  slot directly; do not hand it a spatial spring.

Verify the signature from bytecode before writing (the overload with `animationSpec` is the one to
use, and there are three overloads):

```bash
curl -sL -o /tmp/anim.aar https://dl.google.com/dl/android/maven2/androidx/compose/animation/animation-android/<VER>/animation-android-<VER>.aar
unzip -o -q /tmp/anim.aar classes.jar -d /tmp/anim && (cd /tmp/anim && unzip -o -q classes.jar -d cls)
javap -classpath /tmp/anim/cls androidx.compose.animation.CrossfadeKt | grep -i crossfade
# -> Crossfade(T, Modifier, FiniteAnimationSpec<Float>, String, Function3, ...)
```

**Do not turn the crossfade on for every row in a long list.** A `LazyColumn` of 500 songs would
run a crossfade per visible row on each rebind. Crossfade is for the single large artwork surface
(Now Playing) and the mini player — places where one artwork is the focus.
