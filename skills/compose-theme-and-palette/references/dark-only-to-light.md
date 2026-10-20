# Dark-only app → light (or brand) palette

## When to Use

An app pins one mode (`ForceDarkTheme = true` or equivalent) and the ask is "make it light" or "use
this brand's colours". The work is not a palette swap: the app has dark **surfaces** hardcoded in the
UI layer, and that is what breaks. Skip this file for a plain accent change on an app that already
switches modes.

## Order of operations

Each step is independently verifiable. Do not skip ahead to per-screen kits — step 2 usually removes
most of the apparent work.

### 1. Palette, copied verbatim

Copy the brand's token values as-is from its stylesheet (`:root` for light, `.dark` for dark) and
cite the source path in the Kotlin doc comment, so the next palette change has an obvious starting
point. Then build the light ladder as its own set of values (surfaces **darker** than the page), not
by inverting the dark one.

Add every field the app actually uses, not just the five you were shown: `surfaceContainer*`,
`outline`, `outlineVariant`, `errorContainer`, `inverseSurface`. Fields left unset fall back to
Material defaults and render as a second, mismatched palette.

### 2. Surface tokens, mode-aware

Find the hardcoded dark surfaces first (section 0b of SKILL.md), then back them with one
`CompositionLocal` instead of editing call sites:

```kotlin
data class AppSurfaces(val chrome: Color, val sheet: Color, val row: Color)

val DarkSurfaces = AppSurfaces(
    chrome = Color(0xFF0C0F15),
    sheet = Color(0xFF080A0F),
    row = Color(0xFF10151F),
)
val LightSurfaces = AppSurfaces(
    chrome = Color(0xFFF7F9FC),
    sheet = Color(0xFFFFFFFF),
    row = Color(0xFFF4F7FB),
)

/** Default follows the shipped mode, so untouched call sites still render correctly. */
val LocalAppSurfaces = staticCompositionLocalOf {
    if (ForceDarkTheme) DarkSurfaces else LightSurfaces
}
val AppSurface: AppSurfaces
    @Composable @ReadOnlyComposable get() = LocalAppSurfaces.current
```

Provide it inside the theme's `CompositionLocalProvider`. Keep the dark values byte-identical — an
existing dark user must see no change at all.

### 3. Convert the token `val`s to composable getters, then repair

```kotlin
// before
val MenuRowSurface = Color(0xFF10151F)
// after
val MenuRowSurface: Color
    @Composable @ReadOnlyComposable get() = AppSurface.row
```

Call sites that only pass the colour through (`Modifier.background(MenuRowSurface)`) need no edit.
These break, and each has a fixed repair:

| Breakage | Repair |
|---|---|
| File-scope `private val CardSurface = MenuRowSurface` | Make it a `@Composable @ReadOnlyComposable` getter too |
| A `val` declared **inside** one composable but read by a sibling composable in the same file | Hoist to a file-scope `@Composable @ReadOnlyComposable` getter — a local dies at its function's closing brace, and the compiler reports the *reader* as an unresolved reference, far from the definition |
| Read inside `drawBehind` / `Canvas` / `graphicsLayer` | Hoist above the modifier chain: `val sheetFill = MenuSurface` |
| Default parameter of a plain (non-composable) function | Drop the default; pass the colour from the call site |
| `.map {}` / `forEachIndexed {}` lambda | Pass the colour in as a parameter |
| A plain `val X: Color get() = MenuRowSurface` (no `@Composable`) | Still compiles but reads outside the composition — mark it as well |
| A token read in **both** a composable and a draw lambda in the same file (`.background(Token)` and `drawCircle(Token, …)`) | Keep it a plain `val`. A composable getter fixes the first site and breaks the second; hoisting every draw call works but the plain `val` is one line, and a single-mode app needs no more |

Grep for the leftovers deliberately rather than trusting the compiler:

```bash
grep -rn 'Menu(Row)?Surface\|GlassChromeColor' app/src/main | grep -v '@Composable'
```

### 4. Per-screen kits

Only now go after the `Color(0xFF…)` ramps in `SearchDesign` / `AudioLabKit` / `SettingsGroup`-style
files. A kit is not only `val`s: `object SearchColors { fun page(pureBlack: Boolean): Color =
Color.Black }` **is** the page colour and no `val`-shaped grep sees it. Worse, the flag is what hides
it — every caller passed `true`, so the page stayed black while the rest of the object was correctly
retinted. Grep `fun [a-z][A-Za-z]*(.*): Color` inside kits and read the callers of any mode flag.

Treat the ones that mean something — placeholders (`BoneColor`, shimmer fills), pressed-row
highlights (`Color.White.copy(alpha = 0.12f)` is invisible on white), muted text — as tokens of their
own and give them light values. Leave the artwork scrims and object simulations alone.

Work **per surface family, in this order**: surfaces → ink inside them → screen roots. A family whose
surface is now white and whose ink is still white is worse than untouched, so never commit the
surface half of a family on its own.

### 4b. Ink, in one object

Every sheet kit writes the same five colours under different private names. Centralise them once
(`object AppInk { Primary, Muted, Divider, Chip, OnChip }`) and let each kit alias its locals, so the
next mode is one file. Do not reach for a `CompositionLocal` here: on a single-mode app a plain `val`
is correct, and it is the only option when the colour is a default parameter of a non-composable
class. Leave the one-line ceiling comment instead.

Two shapes that break when swapped rather than inverted:

- a filled circle plus its icon (`.background(Color.White…0.9f)` with `tint = Color.Black…`) — flip
  both, or the chip and its glyph vanish together;
- a highlight/ripple overlay (`Color.White.copy(alpha = 0.12f)`) — a lift, not a tint: use the ink at
  low alpha so it darkens the page instead of disappearing into it;
- **selection fills** — chip background, segmented-control thumb, switch dot
  (`if (selected) Color.White else Chip`, `.background(Color.White)` as a sliding thumb,
  `if (checked) Color.White else Color(0xFFD6DAE1)`). These are fills, not labels, so a pass that
  only rewrites `color = …` leaves the selected state invisible. Invert both sides (`Primary` fill +
  `OnPrimary` glyph) and give the *unselected* colour a light value too — an off-grey near
  `#D6DAE1` is white-adjacent and vanishes beside the page. When the pair sits in a `color = if (…)`
  argument, write the `else` branch: Kotlin rejects an `if` without one used as an expression.

### 4c. Screen roots that paint themselves

`val backgroundColor = Color.Black` inside a screen beats the scheme entirely: the screen stays
dark under a light palette. Repoint the root at `MaterialTheme.colorScheme.background`, and feed the
same value to any glass foundation colour. Keep the roots that are deliberately full-bleed art —
player, recap, onboarding, cropper, webview capture — and say why in the closeout.

### 5. Static splash / window background

See section 4c of SKILL.md. Easy to forget, visible on every cold start.

## Screenshot triage

A dark→light conversion cannot be closed on tests alone. The contrast test asserts on `ColorScheme`
fields; every label coloured by a file-scope `val` or a literal is outside its reach. Expect at least
one round of "install → screenshot → fix" and plan the report around it instead of claiming the mode
works on green CI.

The failures a screenshot catches and nothing else does:

| What you see | What it means | Fix |
|---|---|---|
| A whole screen still black | its palette lives in a named object (`SearchColors`, `LabColors`, `StatsInk`) or a `private val` in that screen's file, not in a literal the audit grepped | enumerate named kits, retint in place |
| One line almost invisible | white/low-alpha ink on the now-white page, usually a `Color.White.copy(alpha = 0.6f)` label the sweep skipped | page ink or muted ink |
| A filled circle with no glyph (or glyph with no circle) | the inverted pair was swapped, not flipped | `Chip` + `OnChip` |
| A dark band on one edge | a scrim built from `Color.Black.copy(…)` under a rail/nav overlay | scrim in page colour |

How to read the screenshot, in order:

1. Ask **one pointed question per region**, not "does this look right". "What colour is behind the
   clock, and are the icons dark or white?" — a general question returns a general, confidently
   wrong description.
2. **Crop and re-ask before reporting any defect.** Whole-image reads invent faults and state them
   as fact. Two phantoms in one session (a "dark status bar" that was light grey with dark icons, a
   "black bar" that was the glass nav) both dissolved under a zoom. Report only what survives it.
3. Describe the fix by **what the element sits on**, then check it against the artwork exclusion. A
   faint label in the hero is only a bug where the hero has no artwork; the same token is correct one
   function away, over a cover. Fix the call site, not the shared token.
4. Ship a new APK and ask for the same screen again. The pass is not done until the specific text is
   legible — "terang sekarang" from a screenshot with one invisible line is not a pass.

## Checks before reporting

- Contrast in **both** modes for: text on page, text on card, accent on page, text on accent, text on
  `errorContainer`. Light `primary` on white usually lands just over 4.5 — check it, do not assume.
- Grep the app for a surviving `Color.White` in a file whose surface token you already flipped. That
  combination is a guaranteed unreadable label, and it is the one thing a compile cannot catch.
- Report the sweep as a list of families **done** and families **remaining**, not as a percentage.
  A "mostly done" palette claim is worth less than "sheet family done, screen kits next", because
  the next session needs the queue, not the score.
- The surface-ladder test: light `surfaceContainer` luminance **below** the page, dark above it.
- A test that pins the light palette to the brand's literal values, so a later brand change cannot
  silently drift.
- `git diff --stat` sanity: a token-level migration is a small diff across a handful of files. A
  three-digit file count means the sweep started at the literals instead of the definitions.
- State the proof you actually have. No local Gradle → CI only. No emulator job → no visual claim.
