---
name: compose-theme-and-palette
description: "Theme a Compose app: light/dark modes, accents, contrast."
version: 1.0.0
author: Hermes Agent
license: CC0-1.0
metadata:
  hermes:
    tags: [android, jetpack-compose, theming, color, contrast, accessibility]
---

# Compose Theme & Palette

Use when adding a theme mode (light/dark/system), an accent palette, or dynamic color to a
Jetpack Compose app — and when **recoloring an app to a palette it never had** (black/blue/white,
brand refresh) even though no new mode is being added.

## 0. Triage first: every app has THREE colour populations, and each takes a different move

Count them before planning. Starting with whichever population you happened to grep first is what
makes a recolor look like a rewrite:

| Population | How to find it | The move |
|---|---|---|
| Material scheme (`MaterialTheme.colorScheme.*`) | `grep -rc 'colorScheme\.' app/src/main` | Edit the scheme **at its definition**. Hundreds of call sites follow; nothing else changes. |
| Static token object (`AppColors.*`, `SearchColors`, `LabColors`, `StatsInk`) | `grep -rn 'object [A-Za-z]*Colors' app/src/main` — then section 1 | CompositionLocal (section 2) **only when both modes ship**; if the app pins one mode, retint the plain `val`s in place (section 3c) |
| Hardcoded literals in per-screen "design kits" | `grep -rnE 'Color\(0xFF[0-9A-Fa-f]{6}\)' app/src/main` | Mechanical retint by measured role (section 3b) |
| Hardcoded dark **surface** constants (glass chrome, sheet, row, placeholder) | `grep -rnE '^val [A-Za-z]*(Surface|Chrome|Glass|Scrim|Bone|Highlight)[A-Za-z]* = Color' app/src/main` | Fan the definition out to a mode-aware token — section 0b |

Real numbers from one app: 455 `colorScheme.*` usages, plus a 272-literal neutral ramp spread across
per-screen kits (`SearchDesign`, `AudioLabKit`, `OnboardingDesign`, `SettingsGroup`, …). Recoloring
the scheme alone left all of that chrome grey, which reads as "the accent changed", not "this app has
a new palette". Budget for the second population or the result looks half-done.

Section 2 is only for apps whose tokens are a **static object of hardcoded `val`s** rather than a
`ColorScheme`.

## 0b. The white text is usually not the bug — the surface under it is

A dark-only app is not "a light palette that was never finished"; it is a light palette plus a set of
**hardcoded dark surfaces** that everything white sits on. Counting `Color.White` finds 650 uses
across 127 files and reads as a rewrite. Find the surface *definitions* instead — a two-line `val`
can carry 60+ call sites:

```bash
grep -rnE '^val [A-Za-z]*(Surface|Chrome|Glass|Scrim|Bone|Highlight)[A-Za-z]* = Color' app/src/main
grep -rn 'MenuRowSurface' app/src/main | wc -l    # fanout of one definition
```

Then sort every white/black literal by **what it sits on**:

- over artwork, cover images, video frames, vinyl → leave it (correct in both modes);
- over one of those surface tokens → becomes correct for free once the token is mode-aware;
- over the page or a card → replace with `MaterialTheme.colorScheme.onSurface` / `onBackground`.

Making the surface tokens mode-aware first shrinks the audit from "127 files" to "the handful of
places that paint their own background". Full migration order and the token shape:
`references/dark-only-to-light.md`.

**Count before offering scope options.** A scope question asked before the three populations are
measured produces a wrong option list; the counts routinely move the answer from "audit 60 files"
to "change 4 definitions".

## 1. Measure before choosing an approach: count the NON-composable call sites

A static token object used in hundreds of places looks like a rewrite. It usually is not. The
number that decides feasibility is **how many usages sit outside `@Composable`** — those are the
only ones you must hand-fix.

```bash
grep -ro 'AppColors\.[A-Za-z]*' app/src/main | wc -l          # total usages
grep -rl 'AppColors\.' app/src/main | wc -l                  # files touched
grep -rn 'MaterialTheme.colorScheme' app/src/main | wc -l     # is a real scheme used at all?
```

Real numbers from one app: **364 usages across 31 files**, `MaterialTheme.colorScheme` used
**twice**. It looked impossible and was actually a 4-function job. Get these numbers first and
report them; they change the plan from "rewrite the UI layer" to "make the token object aware of
theme".

## 2. Make the token object theme-aware — do NOT touch call sites

Keep the exact same property names and shape, but back them with a `CompositionLocal`. Every
existing `AppColors.Primary` keeps compiling.

```kotlin
val LocalAppColors = staticCompositionLocalOf { DarkAppColors }

object AppColors {
    val Primary: Color
        @Composable @ReadOnlyComposable get() = LocalAppColors.current.Primary
    // ...one getter per token
}
```

Provide it in the theme: `CompositionLocalProvider(LocalAppColors provides palette) { ... }`,
where `palette` is chosen from the resolved theme mode.

Why this shape: rewriting hundreds of call sites is not realistic, and a mechanical sed across 31
files risks silent visual regressions. Changing the object itself changes zero call sites.

**Consequence to document in the code:** every usage must now be inside a `@Composable`. That is
the trade, and it is what step 3 pays for.

## 3. Hand-fix only the non-composable usages (four recurring categories)

| Category | Symptom | Fix |
|---|---|---|
| Helper called inside a non-composable lambda | `fn()` marked `@Composable` but invoked from `.map {}` / `forEachIndexed {}` | Hoist the palette read to composable scope; change the helper to `fn(colors, index)` and pass it in |
| Draw lambdas | `Modifier.drawBehind {}`, `Canvas`, `DrawScope` — **not a composable context** | Read colors *before* the lambda, pass as parameters |
| File-scope `val`s built from tokens | `private val X = AppColors.A` at top level | Convert to a `@Composable @ReadOnlyComposable` getter, or read inside the composable |
| Brush/placeholder helpers | returns a color or `Brush` built from tokens | Mark `@Composable @ReadOnlyComposable` |

Search for these deliberately; do not wait for the compiler to find them all:

```bash
grep -rn 'AppColors\.' app/src/main | grep -v '@Composable'   # then eyeball each hit
```

## 3b. Retint the hardcoded per-screen ramp — by measured role, not by grep taste

The third population is per-screen kits full of `Color(0xFF2C2C2E)`. Hand-editing them is a day of
work, and a botched sweep is invisible in review. Two rules make it mechanical:

- **Near-neutral is the safe set.** A literal whose `max(R,G,B) - min(R,G,B) <= 14` is chrome:
surfaces, scrims, placeholders, muted text. Anything more saturated carries meaning — error red,
swipe-action green, log-level yellow — and retinting it destroys information the user relies on.
- **Tint by hue, keep the lightness.** Convert to HLS, force the hue to the palette's accent hue,
set saturation by lightness band, keep L. Lightness is what the layout hierarchy and the contrast
ratios ride on, so preserving it keeps every screen's ladder intact while the cast changes. Let
saturation fall as lightness rises, or light chrome turns into coloured candy.

```bash
python3 scripts/retint-neutral-ramp.py --root app/src/main/kotlin \
  --hue 220 --dry-run          # review the count, then re-run without --dry-run
```

**Exclude files that simulate a physical object**, or they stop looking like the object: vinyl
platters, turntable metal, silver ID-card gradients, recap "paper", third-party brand art. Name the
exclusions on the command line, and list them in the closeout with the reason — that list is the
difference between a deliberate palette and an unfinished sweep.

**Also exclude white text and black scrims drawn over artwork** (cover images, video frames, vinyl).
The artwork is the background in both modes, so `Brush.verticalGradient(Color.Black…)` plus a
`Color.White` label stays legible; retinting it fades the label into a pale cover.

In a media player the artwork exclusion is most of the tree, and it is faster to triage by
**directory** than by reading each hit. `ui/player` (minus its sheet files), `recap`, `onboarding`,
`customize`, `launch` all paint over covers, vinyl, or a full-bleed gradient — they keep white in
both modes. The real queue is `ui/screens`, the `ui/component` kits, and the sheet families. Count
the literals per directory first (`grep -rc … | awk` over the path prefix) so the plan starts from
the audit queue, not the total.

**A full palette swap is a role-for-role replacement, not a hue retint.** When the user replaces
one complete palette with another (ink, panel, line families all change at once), update the token
objects FIRST, then map every old hex to its new counterpart and `sed` it across the tree — the
token-first order means the sweep cannot miss a definition the tokens already renamed. Verify with
`grep -c` on every old hex AND every old token name (both must read zero), then re-grep for
comments naming the old colours ("soft blue", "slate"): stale comments outlive the code that
justified them and mislead the next reader. Keep saturated role colours (error red, queue green,
brand marks) out of the sweep by listing them first — they are meaning, not chrome.

## 3c. Once the surface token flips, the ink inside it is the next break — centralise it in one object

Mode-aware surfaces are step one, and they make the *next* failure worse rather than better: a
sheet that was dark glass and is now white keeps its `Color.White` labels, so it goes from
merely off-brand to unreadable. Order the work surfaces-first and expect an ink pass immediately
after, per sheet family.

Put the ink in **one** object next to the surface tokens, not a private constant per screen:

```kotlin
object AppInk {
    val Primary = Color(0xFF0A1424)   // brand foreground
    val Muted = Color(0xFF5B6B82)     // brand muted-foreground
    val Divider = Color(0xFF0A1424).copy(alpha = 0.08f)
    val Chip = Color(0xFF0A1424)      // filled circle
    val OnChip = Color(0xFFFFFFFF)    // icon inside it
}
```

Every sheet kit then maps its local names onto it (`private val SheetInk = AppInk.Primary`), so the
next mode change is one file. Sweep the whole family at once — sheet kits share shapes, and fixing
one file while its sibling keeps white text leaves two sheets that disagree.

**Inverted pairs must be inverted, not swapped.** A filled circle carrying an icon is `Chip` +
`OnChip`, and replacing only the visible `Color.White` with the page ink yields ink-on-ink: the
chip disappears and the icon with it. Grep the pair together (`.background(Color.White…)`
immediately followed by `tint = Color.Black…`) and flip both sides.

**Not every token needs a `CompositionLocal`.** When the app ships a single mode, the lazy correct
move is a plain `val` with a comment naming the ceiling — required, not optional, when the colour is
a default parameter of a **non-composable** class or function (`class Highlight(private val color:
Color = HighlightColor)`), where a composable getter cannot be read. Write the comment as "if this
app ever ships two modes, this value has to become mode-aware", so the next session does not
discover it by rendering.

Then two cheap checks: the script prints before/after contrast for samples it retinted, and
`git diff --stat` should land near +250/−250 lines across ~50 files for ~200 literals. Numbers far
outside that mean the matcher caught hex inside strings or comments, not colours.

## 4. Design the light scheme as its own ladder — never invert the dark one

On light there are two valid page models, and they order the card opposite ways:

- **White page, tinted cards:** cards are *darker* than the page (`#FFFFFF` page, `#F2F2F7` card).
- **Tinted page, white cards:** cards are *lighter* than the page (`#E8F3FE` page, `#FFFFFF` card, azure
  accent) — the composition most designer mockups use. It reads airy, not broken, because the white
  card is the brightest surface and the page tint is shallow.

When the brief is "make <colour> dominant, not just the navbar", it is asking for the second model,
not a new `primary`. Ship the page tint plus white cards plus accent links/buttons; recolouring only
the nav leaves the app reading white and the user repeats the request.

What must hold in both: a perceptible luminance step between page and card, and the
pressed/selected/container ladder still stepping **darker** than the page so a selected row never
vanishes into it. Inverting token values still produces invisible cards.

Decide the light surface/elevated/border ladder explicitly rather than deriving it by negating
luminance, and pin the page model in the theme comment. A palette test asserting "card darker than
page" only holds for the first model; when switching to the tinted-page model, rewrite the
invariant to "card lighter than page, containers darker than page" rather than deleting the test.

## 4b. Hoist the schemes to top-level vals so the test reads the REAL palette

A palette built inside a `@Composable` cannot be asserted on: a test would have to copy the values,
and the copy keeps passing after the real one changes. Extract both schemes to file scope:

```kotlin
val DarkPalette: ColorScheme = darkColorScheme(primary = AppColors.Blue, /* ... */)
val LightPalette: ColorScheme = lightColorScheme(primary = AppColors.BlueDeep, /* ... */)

@Composable
fun AppTheme(darkTheme: Boolean = ForceDarkTheme, content: @Composable () -> Unit) {
    val baseColorScheme = if (darkTheme) DarkPalette else LightPalette
    // ...
}
```

`darkColorScheme(...)` / `lightColorScheme(...)` are plain functions, so calling them at file scope
is fine. The contrast test then imports `DarkPalette`/`LightPalette` and asserts on the values the
app really renders — which is also the only thing that catches a mis-wired field (`onSurface`
pointed at the card-text token), the failure no amount of call-site reading reveals.

## 4c. Flip the static surfaces the composition cannot reach

A dark-only app pins black where no `ColorScheme` reaches: the splash theme
(`windowSplashScreenBackground`) and `windowBackground`. Leaving them makes every cold start flash
the old mode before the new UI appears — the first thing the user sees, and easy to miss because no
screenshot of a running app shows it.

When the app becomes single-mode, set those to the new page colour in **both** `values/` and
`values-night/` (there is no second mode left to serve) and say so in the commit. Values that feed
launcher icons, widget chrome and static XML stay pinned — those are identity, not theme.

## 4d. Some screens paint their own root background — the scheme cannot reach those either

A screen that draws its own page colour keeps the old mode no matter what the `ColorScheme` says,
and it is invisible in a diff that only touches the theme: the whole screen stays black under a
light palette. Find them by the assignment, not by the visual result:

```bash
grep -rnE 'val backgroundColor = Color\.(Black|White)|\.background\(Color\.(Black|White)\)' app/src/main
```

Repoint the screen roots at `MaterialTheme.colorScheme.background` (and pass the same value to any
blur/foundation colour that fills behind the glass). Then triage what is left by role: a root that
is genuinely a full-bleed artwork or overlay surface — player, recap story, onboarding art,
photo cropper, webview capture — keeps its own colour on purpose; say so rather than "fixing" it.

## 4e. After the first visual round, enumerate — do not wait for the next screenshot

One screenshot per round finds one screen at a time, and the user will rightly push back with "check
everything, there must be more still dark". Enumerate the whole surface in one pass and report it as
a table of *converted* / *page chrome still to do* / *deliberately dark*:

```bash
# every screen that paints its own root
for f in $(find app/src/main/kotlin -path '*/ui/*' -name '*.kt'); do
  n=$(grep -cE 'background\(Color\.(Black|White)\)|drawRect\(Color\.Black\)|val pageColor.*=.*Color\.Black' "$f")
  [ "$n" -gt 0 ] && echo "$n $f"
done
# every named kit, plus colour returned from a function rather than a val
grep -rn --include=*.kt -E 'object [A-Za-z]+Colors|fun [a-z][A-Za-z]*\(.*\): Color' app/src/main \
  | grep -v '/test/'
```

Classify each hit — player, recap, onboarding, cropper, webview capture and artwork-fed headers keep
their own colour on purpose; everything else is queue. That table is what the next session needs, and
it is cheaper than another round of "open this screen and send a picture".

## 4f. Triage a mismatch screenshot overlays-first, then ink, then tokens

A light-mode screenshot usually shows three different bugs at once, and only one of them is a
token. Trace each visible defect to its declaration before proposing colour edits:

1. **Page-level scrims and gradients.** A fallback of the form `detailAccent ?: Color.Black` — nav
   scrim, top-bar scrim, mini-player fade — paints black over a white page whenever the page has no
   accent. Everything under it looks wrong: body text unreadable, white pill floating on black,
   content that seems clipped by the nav. Fall the fallback back to
   `MaterialTheme.colorScheme.background`: identical in dark mode, correct in light.
2. **Ink that is white because artwork sits behind it.** Brand mark, page title over a hero, play
   pill. It is only correct while artwork is present; an empty/quiet hero has none, so white on
   white. Make the tint depend on whether the hero has media (hoist a `heroHasArtwork` state out of
   the carousel), and use `onBackground` for the scrolled top bar once the hero is gone.
3. **Only then** per-element tokens and scheme fields.

Do not repaint text that sits under a scrim: the text colour is usually already correct, and
changing it hides the scrim bug for one screen while leaving the others broken.

Report the result as a numbered list, one defect per line: symptom → exact `file:line` cause →
consequence on screen → fix. Close with a priority line (which one or two fixes remove most of the
visible damage) and an explicit note on items that are content/design rather than theme (duplicate
section labels), and on anything the screenshot cannot prove.

## 5. Validate contrast in EVERY mode, before shipping

- Test each accent against **its actual background in both modes**, not just the default mode.
  Real failure: two accents passed in dark mode and failed AA in light (4.22 and 3.30).
- Fix a failing contrast by **lowering the color's lightness**, never by lowering the threshold.
- **Test the button pair separately.** If buttons use `containerColor = Primary` +
  `contentColor = Background`, then in light mode both of those are dark — "Primary vs background"
  and "content-on-Primary" are two different checks and both must pass.
- **One accent tone cannot pass both of those checks, so ship two.** An accent light enough to read
  as text on black is too light to be a container full of dark text; an accent dark enough for a
  button is too dark to read on black. Give each mode its own tone (lighter on dark, deeper on
  light) instead of sliding one tone until both are equally mediocre.
- Keep a floor for decorative gradients too (e.g. a bloom gradient must stay at least ~1.3x apart
  from its neighbour or it is invisible).

Write these as **unit tests over the palette**, not as manual eyeballing.

## 5b. A designer-supplied palette is a hypothesis, not a spec to ship blind

When the user hands over tokens as hex values, check every **text pair against the surface it will
actually sit on** before writing code, and report the numbers in the reply. Real numbers from one
such palet: the brand primary `#3478F6` gave **4.07** with white button text, and the secondary
slate `#66758F` gave **4.45** on the near-white page — both under AA's 4.5 — while every other pair
passed at 15+. Two of eight tokens failing is the normal rate, not a bad palette.

Neither silently "fix" their hex nor silently ship the failure:

- Keep the spec value in the palette object under a name that admits what it is (`SpecBlue`,
  `SpecSlate`) with a comment carrying the failing ratio and the surface.
- Render the nearest value that passes: darken the primary until white-on-primary clears 4.5, and
  darken the secondary until it clears on **every** surface it lands on — the tinted panels and
  selected states, not just white. Hue stays recognizable; the step is small enough that nobody sees
  it beside the spec.
- **A token can pass on the page and still fail on the panel.** The page→panel luminance gap is
  small, so a muted text color at 4.7 on white can drop to ~4.2 on a `#F2F2F7`-class panel and fail
  AA exactly where the app puts metadata-on-tinted-card. Compute the token against the *darkest*
  surface it lands on (the panel, not the page) and pick the smallest darkening that clears there —
  then re-verify it still reads beside the spec hex on white. When a contrast test asserts
  `onSurfaceVariant` on `surfaceVariant`, that pairing is the one that catches this.
- When the source is a **screenshot** rather than hex tokens, extract the spec first: ask for per-role
  hexes (accent, secondary text, page background, panel, line) with a pointed question, and expect
  the extracted secondary/accent values to fail AA on extraction — they are design intent, and the
  spec/render split above is what ships. The hero photo and any artwork are not palette inputs;
  monochrome UIs read as nearly grayscale once the photo is excluded.
- Assert **both** in the palette test: the rendered field equals the AA-passing value, and the spec
  constant still equals the designer's hex. That keeps the intent in the repo and the deviation
documented, instead of quietly re-tuned and later "corrected" back to the failing value.
- Report the deltas with the exact ratios, plus a one-line "revert if you want the exact hex". The
  palette is the user's call; AA is the constraint you are enforcing on their behalf.

A palette also usually omits border, placeholder and pressed colours. Derive them from the page and
panel luminosity, and say in the report that they were derived — otherwise the next reader assumes
they came from the design. A pastel brand tone that measures ~2.1 against white is decoration only:
allowed as a background carrying dark text (8+), never as text, an icon, or a hairline.

## 6. Prove the test can fail before trusting it

A contrast test that has never failed is not a guard. After adding it:

1. Temporarily revert the fix (restore the failing value).
2. Run the test; confirm it fails **on exactly the right assertion** (`EXIT=1`, named test).
3. Restore the fix; confirm green again.

Do the same for any "the default must not change" test.

## 7. Keep the default experience byte-identical

Make the default accent reuse the **exact existing values** so a user who touches nothing sees no
visual change at all. Lock that with a test that asserts the default equals the legacy constants.
This is what makes a theming change safe to ship to existing users.

## 8. Persist theme preferences as strings, not enum ordinals

Storing `enum.ordinal` breaks silently when the enum's order or contents change in a later release.
Store the enum **name** and parse defensively with a fallback to the default.

## 9. Gate platform-dependent features on real capability

Dynamic color (Material You) needs Android 12+ (`Build.VERSION.SDK_INT >= Build.VERSION_CODES.S`).
Check it and **disable the control with a visible reason** rather than letting the switch no-op
silently.

## 10. System bars follow the theme from inside the composition

Do not pin system-bar icon appearance once in `onCreate`. Set it in a `SideEffect` inside the
composition where the resolved theme is known — otherwise light mode renders light-on-light
invisible status-bar icons.

## Pitfalls

- **A static token object cannot be themed.** Multi-mode is impossible until the object itself reads
  from a `CompositionLocal`. Any plan that starts by editing call sites is the wrong plan.
- **`drawBehind` / `drawWithCache` / `DrawScope` / `Canvas` lambdas are not composable contexts.**
  Reading a token inside them will not compile; hoist the read above the `Modifier` chain
  (`val pageTint = MaterialTheme.colorScheme.background`) and capture it in the lambda. Both the
  `drawWithCache {}` block and its `onDrawBehind {}` are non-composable — the error points at the
  `MaterialTheme` read, not at the modifier.
- **`.map {}` / `forEachIndexed {}` lambdas are not composable.** A `@Composable` helper cannot be
  called from them — pass the palette in as a parameter.
- **Inverting the dark ladder for light mode makes cards invisible.** Design the light ladder
  separately.
- **Contrast checked in one mode only** passes dark and ships broken light.
- **A tinted page invalidates foreground tokens that passed on white.** Error red `#DC2626` reads
  4.83 on white and drops to 4.30 on `#E8F3FE`; a light error tone, placeholder or muted label picked
  against white can fail the moment the page gains a tint. Recompute every foreground pair against
  the new page (and the panel), not only the accent, and darken the error token if its own test pair
  now fails.
- **`res/values/colors.xml` cannot follow a runtime theme.** It feeds resources resolved outside the
  composition (launcher icons, widget chrome, static XML), so leave those values and add a comment
  saying so. Exception: once the app is single-mode, `windowBackground` and the splash background are
  no longer "runtime" — flip them by hand (section 4c) or every cold start flashes the old mode.
- **Aksen yang tersimpan di preferensi tidak ikut berubah oleh kode.** Default aksen sering
  disimpan sebagai `Int` (`selectedThemeColor`); pemasangan yang sudah ada memegang nilai lamanya,
  jadi recoloring hanya sepenuhnya terlihat di pemasangan baru — dan bahkan "warna default" di
  source bukan yang mereka pakai. Sebutkan itu di laporan sebagai batas bukti, jangan klaim
  paletnya berlaku untuk semua user.
- **Audit default/seed colours OUTSIDE the theme file after a palette swap.** A `DefaultThemeColor`-style constant — the seed for artwork-derived accents, player slider tones, seek-bar fills, or the theme-colour preference default — often still points at the old accent after the token object is rewritten. The swap looks complete while the player UI keeps the old colour, and no contrast test over the scheme can see it. After the sweep, grep the old accent hex outside the theme file (`grep -rn '0xFF4D8DFF' app/src/main --include='*.kt' | grep -v 'ui/theme/'`) and repoint every default/seed at the new palette.
- **Identity/decoration colors are not accent colors.** A signature brand tone (a specific blossom
  pink, etc.) belongs to the fixed identity, not the user-selectable accent list — keep it out of
  the palette and assert it in a test.
- **Decorative elements and player controls keep their own roles.** An accent change should not
  recolor the playback controls or the brand mark.
- **"Match this brand's colours" is ambiguous — settle the MODE before proposing tones.** A brand
  stylesheet ships both `:root` (light) and `.dark` tokens, and the user may mean either. Offering
  accent variants for the wrong mode wastes the whole round trip: ask which mode first, then tones.
- **A vague "some themes don't match" report is a request for evidence, not an edit.** "Tema" can
  mean the app's light/dark mode, an accent/seed colour, a player style, or a preset list that does
  not exist. Enumerate what actually ships first (`grep` the palette object, `DefaultThemeColor`-style
  seeds, and any preset list) and name the modes back to the user in one message; then ask for the
  screen name, a screenshot, and the expected reference. Editing hex before those three are known
  changes a palette nobody complained about and leaves the real screen untouched. If the app has no
  preset-theme picker, say so — it reframes the report as a per-screen colour bug.
- **A `@Composable` getter cannot be read from a non-composable context**, and the compiler finds
  only some of them. Sweep deliberately after converting: file-scope `private val X = Token`, default
  parameters of plain functions, and every `drawBehind` / `Canvas` / `graphicsLayer` lambda.
- **A default parameter is a non-composable context too.** `fun label(color: Color =
  MaterialTheme.colorScheme.onSurface)` fails when `label` is not `@Composable` — the default is
  evaluated at every call site, including the plain ones. Give it a literal or a palette constant as
  the default and let composable callers pass the themed value; do not mark the helper `@Composable`
  to make the default legal, because that breaks its callers next.
- **Selected/unselected state pairs invert on both sides, and both branches must survive.**
  `if (selected) Color.White else Surface` plus `if (selected) Color.Black else Ink` is a chip that
  goes white-on-white the moment the page turns light: flip the fill to the ink token *and* the label
  to the on-ink token. Rewriting only the label leaves `if (on) Color.White` with no `else`, which is
  a compile error (`'if' must have both main and 'else' branches when used as an expression`) far
  from where you were looking. Treat chips, segmented-control thumbs, toggle dots and "picked"
  buttons as one family and invert them together.
- **A sweep that introduces a new symbol needs the import check.** Replacing `Color.White` with
  `KitColors.Primary` compiles only in files that import it (or share its package). After the batch,
  run `grep -L 'KitColors' $(git diff --name-only -- '*.kt')` and fix the misses in the same commit —
  otherwise CI returns one `Unresolved reference` per file and costs a whole round trip.
- **A new palette token must be unique across the WHOLE token object, not just its section.** Palette
  objects usually carry a dark and a light section; adding `Blue` to the light half when the dark half
  already has `Blue` compiles to `Conflicting declarations` plus a cascade of misleading errors far away
  (overload-resolution ambiguity in unrelated files, type-inference failure in an activity). Read the
  FIRST compiler error, not the last — the cascade points everywhere except the duplicate. Grep the
  object for the name before adding it.
- **Sweep one colour expression at a time; never re-type the block around it.** A hand-written
  multi-line anchor silently drops the neighbouring line you were not thinking about (an
  `overflow = …` beside a `color = …`), and a stray `}` typed into the same edit unbalances the
  file — then the compiler reports the *last* line of the file, not the edit, so the error points
  somewhere you never touched. Prefer `replace_all` on the bare expression
  (`Color.White.copy(alpha = 0.4f)` → `AppInk.Muted`); when a block anchor is unavoidable, include
  every line of it verbatim. **`replace_all` is only safe when the replacement resolves at every
  site it lands in** — a file often holds a top-level composable and a private helper below it, so a
  replacement using a `val` declared in the first lands in the second as an unresolved reference.
  Either use a file-scope name (`AppInk.Muted`) or split the sweep per function. After the batch, check
  `{`/`}` balance per touched file before pushing —
  a sweep of a dozen files produces one unbalanced file far more often than none:

  ```bash
  for f in $(git diff --name-only -- '*.kt'); do
    echo "$(awk '{n+=gsub(/\{/,"{")-gsub(/\}/,"}")} END{print n}' "$f") $f"
  done   # every line must read 0
  ```

  A non-zero balance makes the compiler report the *last* line of the file, so the error points
  somewhere the edit never touched.
- **Audit by declaration site, not by literal.** One `object SearchColors { val Field = Color(0xFF0F131B) … }`
  is an entire screen's palette, and a `Color(0xFF…)` grep scoped to that screen's file never sees it —
  the screen stays black under a light scheme while every other surface flips. Enumerate named kits
  (`grep -rn 'object [A-Za-z]*Colors' app/src/main`) and private per-screen palettes
  (`grep -rn 'private val [A-Za-z]* = Color(0xFF0[A-D]' app/src/main`) at the same time as the
  literals, or the audit queue is missing whole screens. A kit also returns colour from **functions**
  (`fun page(pureBlack: Boolean): Color = Color.Black`), which no `val`-shaped grep finds — and when
  every caller passes the mode flag `true` unconditionally, retinting the surrounding `val`s still
  leaves the page black. Add `grep -rn 'fun [a-z][A-Za-z]*(.*): Color'` to the same audit, and check
  the callers of any `pureBlack`-style flag before trusting it.
- **The screenshot is the only oracle for literal ink.** A palette contrast test asserts on
  `ColorScheme` fields; text coloured by a file-scope `val`/literal is outside its reach, so white 69%
  on white compiles, passes every test, and is invisible on the device. Compile-green plus green
  contrast tests is **not** evidence the UI is legible — say so plainly and get a screenshot before
  claiming the mode works.
- **Crop a user screenshot and re-ask before reporting a defect from it.** A whole-image read invents
  faults that are not there and states them as fact (a "dark status bar" that is light grey with dark
  icons, a "black bar" that is the glass nav). Re-run the analysis on the exact region with a pointed
  question; report only what survives the zoom. The real defects are worth the extra call — the
  phantom ones cost the user's trust in everything else you said. Region coordinates are in
  ORIGINAL-image pixels, not screen dp: a crop that comes back flat white means the region missed
  (check the real dimensions), not that the defect is absent — do not treat it as a confirmation.
- **A `?: Color.Black` scrim fallback is a light-mode bug even when every surface token is right.**
  Chrome scrims are written for dark pages; on a light page the fallback must be
  `colorScheme.background`, not black. One line at the overlay definition fixes the bottom fade, the
  unreadable content under it, and the "clipped" nav pill in the same pass.
- **White top-bar ink is conditional on artwork, not on mode.** A white brand mark or page title is
  correct over a cover and invisible over an empty hero state; the empty state is exactly where it
  shows up. Tie the tint to artwork presence, not to the theme, and give the scrolled top bar the
  page ink.
- **A palette swap breaks the exact-value palette test by design — update it in the same commit.**
  Tests that assert `Color(0xFF…)` per field (and any "default accent equals legacy" check) fail the
  moment the palette changes; that is the guard working, not a regression. Change the expected values
  to the new role tokens, keep every AA assertion intact, and keep the old spec hex in the palette
  object (`AzureSpec`, `SpecGray`) with the failing ratio in the comment so design intent is not
  erased. Never delete or relax a contrast assertion to make CI green.
- **A dark header inside a light app needs its own status-bar appearance.** System-bar icon mode
  follows the resolved theme, so a hardcoded deep-blue profile/recap header under a light scheme
  renders dark icons on dark blue — invisible. Set the light/dark icon flag per screen while that
  header is on top (the recap story already does this), not only once in `onCreate`.
- **Glass nav pill borders written for dark chrome vanish on light.** `Color.White.copy(alpha = 0.1f)`
  around a white pill on a tinted page has no visible edge; use `colorScheme.outline` in the
  non-pure-black branch so the pill keeps a hairline on both page models.
- **Prefer adding light mode over rewriting the app for it.** If the only honest answer is "the whole
  UI needs auditing first", say that with numbers before writing any code, and let the user choose
  between a small honest diff and a large unverifiable one.

## Verify before declaring done

```bash
./gradlew :app:compileDebugKotlin --no-parallel    # fastest signal; iterate here first
./gradlew :app:testDebugUnitTest   --no-parallel    # run separately (see below)
./gradlew :app:lintDebug           --no-parallel
./gradlew :app:assembleDebug       --no-parallel
```

On a machine where local Gradle is banned (shared production host, no RAM budget for a daemon),
stop there and treat CI as the compiler: the **lint job** proves the main source set compiles, the
**unit test job** proves main + test compile and that the palette test actually ran. Report which
proof you got — "lint + unit test green, no local build" — rather than claiming the palette is
verified. The "prove the test can fail" step in section 6 cannot be executed there; report it as
**not performed**, never as passed.

**"Job green" is not "my assertions ran" — pull the test report artifact and read the case names.**
A green unit-test job also passes when the palette test class was never discovered. That listing is
the difference between "the job passed" and "all seven palette assertions executed and passed", and
it is quotable to the user. The same artifact list carries the release APK — download it and hand over
the file so the user can install and judge the visuals, since no emulator job means no screenshot
from you.

Before handing the APK over, prove the new palette is actually inside it: `aapt` only shows the
manifest version, not colours. Scan `classes.dex` for the new ARGB constant as a little-endian int
(`struct.pack('<I', 0xFF…)`); a non-zero count proves the rebuild carried the theme change. That is
content proof, not visual proof — the screenshot is still the only oracle for legibility. Full
procedure: `android-ci-only-feature-development` → "Perubahan warna/konstanta".

**`concurrency: cancel-in-progress` turns every push into a cancelled run.** Older runs showing
`cancelled` are not failures, and a cancelled run still reports per-job conclusions. Read
`gh run view <id> --json jobs` for the job that matters (lint / unit test finish long before the APK
jobs) instead of the run-level `conclusion`, and push in batches so a real failure is not cancelled
out from under you before you read it.

Commands, permission checks, artifact download and red-run triage: `references/ci-as-compiler.md`.

Run these as **separate invocations, in the background with completion notification.** Merging them
into one invocation exhausts RAM on a small machine and the daemon dies mid-build; a long build
in the foreground is killed by the tool timeout and takes the daemon with it. Confirm the test count
actually ran from the result XML — a suspiciously fast `BUILD SUCCESSFUL` usually means UP-TO-DATE
and no tests executed.
