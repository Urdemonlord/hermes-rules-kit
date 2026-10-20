# Static-analysis pitfalls: bugs that compile nowhere near CI

Compile errors are cheap — CI catches them in minutes. The bugs below reach CI as
green-checkmarked jobs or reach the user's device, because nothing in the toolchain
is checking them. They are also all **findable by reading**, which means they
should be found BEFORE pushing, not by burning a 10-minute CI cycle.

## 1. Cross-package type used without an import

A data class declared in `playback` and referenced from a ViewModel in
`ui.viewmodel` needs `import com.meowlabs...playback.ThatType`. Nothing in the
same file hints at it, and reading top-to-bottom does not surface it.

Mechanical check, before push — `scripts/check-kotlin-symbols.py` runs both directions:

```bash
python3 scripts/check-kotlin-symbols.py app/src/main/kotlin com.meowlabs.player
```

It reports internal imports with no definition AND project symbols used in a file that never
imported them. Same trap in reverse: a `Fully.Qualified.Type` used inline in a parameter list
instead of an import. It compiles, so it never surfaces — but it makes the signature unreadable
and hides the dependency. Import it like any other type.

## 2. Extension properties need a per-symbol import

`androidx.compose.material.icons.Icons` tells Kotlin *where* icons live. Each
icon itself is an extension property, so `Icons.Filled.GraphicEq` needs its own
`import androidx.compose.material.icons.filled.GraphicEq`. No wildcard comes with
it, and the error points at the usage line, not the missing import.

Confirm the icon exists in the artifact you actually ship against, with no Gradle
invocation:

```bash
JAR=$(find ~/.gradle/caches -name 'material-icons-extended-*-runtime.jar' | head -1)
unzip -l "$JAR" | grep -i graphicEq
unzip -o -q "$JAR" 'androidx/compose/material/icons/filled/GraphicEqKt.class'
javap -p androidx/compose/material/icons/filled/GraphicEqKt.class
# public static final ...ImageVector getGraphicEq(androidx.compose.material.icons.Icons$Filled)
```

`javap` showing `getXxx(Icons$Filled)` while Kotlin reports unresolved means the
icon is present and the **import** is missing. The `Kt` suffix in the JAR is just
the top-level-property file convention; the property is `getGraphicEq`.

For `AutoMirrored` icons the import path is `automirrored.filled.X`, not
`filled.X`.

## 3. Handlers installed once, but the resource they attach to is rebuilt

Anything keyed to a native handle that the player/service recreates must be
installed from a callback, not from `onCreate`. `Player.Listener` exposes
`onAudioSessionIdChanged`, and it fires with `C.AUDIO_SESSION_ID_UNSET` (= 0)
before a session exists — so the handler must handle 0 explicitly.

Symptom when this is wrong: the feature works on the first launch and is silently
dead after the app is killed and reopened. Nothing errors.

Audio effects (`Equalizer`, `BassBoost`, `LoudnessEnhancer`) are the standard case. Inject the
effects controller into the **service**, not the UI: playback runs in the service while the app is
invisible, so an equalizer that only lives in the UI dies as soon as the screen closes. The UI
writes to storage; the same singleton controller applies it. The general shape is: attach in the
change callback, release in exactly one place.

## 4. Device-reported ranges must not be hardcoded

Native audio effects report per-device limits that differ by OEM —
`getBandLevelRange()` returns `-1500..1500` on some hardware and `-1200..1200`
on others, and `getCenterFreq()` gives band centers that differ per vendor.

- Persist values in a **device-independent unit** (millibels, not slider index
  0..n) so a stored preference means the same thing on any device.
- Clamp in the layer that *has* the range, not in the data class. A data class
  that clamps to a hardcoded range silently corrupts the stored value.
- Wrap each native setter in its own `runCatching`. Some ROMs reject levels in
  the *middle* of the range they themselves reported, so clamping does not make
  it safe, and one band's failure must not abort the remaining bands.
- APIs that silently clamp instead of throwing (e.g. `LoudnessEnhancer`) are
  worse than ones that throw: a slider will display a value that is not in
  effect and nothing reports the mismatch.

## 5. "Not supported" vs "not known yet"

A capability probe that returns empty before the resource exists will be read as
"this device does not support it". Users who open settings before playing
anything get told their phone lacks a feature it has.

Keep both states distinct in the UI state. Emit "unsupported" only when
construction of the effect actually failed, and re-probe when the screen opens.

## 6. Duplicate label next to its own control

A `SectionTitle` whose text is identical to the label inside the control directly
below it, ~20dp away, reads as a layout bug rather than a section marker. The
control already carries the label; drop the title.

## 7. Reset actions that depend on a probe result

```kotlin
// No-op when the probe has not returned yet: size == 0 produces an empty list.
val current = settings.eqSettingsFlowFirst()
settings.setEqSettings(current.copy(bandGains = List(uiState.value.bands.size) { 0 }))
```

Clearing the stored list is correct and needs no probe. Prefer it: it also stops
stale gains from a device with a different band count leaking into the next one.

## 8. YAGNI pass on fresh code

Before the first push, grep for every new public member and delete what nothing
calls. Helpers written "for later" (`clampToDeviceRange` duplicating a
`coerceIn` already in use, unused getters, test-only helper objects that assert
against their own constants) cost nothing to add and everything to read. If a test
defines the expected constant itself, it is testing the test.

## 9. Non-ASCII garbage in generated comments

Bulk `write_file` of a long Kotlin file can interleave stray CJK/Cyrillic
characters into comment text. It compiles, lints clean, and reads as corruption.
The scan is a script, not a snippet:

```bash
python3 scripts/scan-mixed-script.py app/src CHANGELOG.md README.md
```

Run it before pushing and over the commit message before committing. The scanner
excludes Latin-1 punctuation (en/em dash, curly quotes) and emoji, which are
legitimate in Indonesian prose.