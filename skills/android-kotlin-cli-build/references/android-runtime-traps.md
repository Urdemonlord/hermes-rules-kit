# Android runtime + compile traps found without a device

Traps that compile clean, pass every local gate, and only surface in the user's hands.
Each is stated as mechanism → proof → fix, because the mechanism is what makes the fix stick.

Siblings of `§11 Cross-reference every boundary symbol before pushing` in
`dependency-version-upgrade.md`; that section covers *your own* symbols and library
**method names**, these cover **import granularity**, **resource config semantics**, and
**test fidelity**.

---

## 1. `FileProvider` `<cache-path path="...">` registers a DIRECTORY

**Symptom.** Installing a downloaded APK in-app fails on *every* device with one of:

- `StringIndexOutOfBoundsException: length=N; index=N+1` from
  `FileProvider$SimplePathStrategy.getUriForFile`
- `IllegalArgumentException: Failed to find configured root`

### The exception message is the diagnostic

`length` is the absolute character length of the file being installed. Recompute it:

```python
len("/data/data/<pkg>/cache/update.apk")     # -> 58 matches length=58; index=59
```

A match means this bug, not a guess. **When a stack trace prints string lengths, treat the
numbers as data to reproduce, not noise to skip.** This turns a two-day spelunk into one
division.

### Mechanism

`FileProvider` builds each root as `new File(context.getCacheDir(), path)`, stores its
`getCanonicalPath()`, then matches:

```java
if (path.startsWith(rootPath)) {
    if (SEPARATOR.equals(path.substring(rootPath.length()))) {
        path = path.substring(rootPath.length());
    } else {
        path = path.substring(rootPath.length() + 1);   // throws
    }
}
```

The `path` attribute on `<cache-path>` means **a folder relative to cacheDir**. Writing
`path="update.apk"` registers `cacheDir/update.apk` as the root — the very file to install.
`path` and `rootPath` become byte-identical: `startsWith` is true, then
`substring(len + 1)` runs on a string of length `len`.

**Fix:** `path="."`. `new File(cacheDir, ".")` yields `cacheDir/.`, and **canonicalization
turns it into `cacheDir`** — that is the only reason this works. Without the canonicalize
step `startsWith` fails and the symptom becomes `Failed to find configured root`.

Verify `addRoot` really canonicalizes in the androidx.core version in use; do not assume:

```bash
javap -c -p androidx/core/content/'FileProvider$SimplePathStrategy.class' \
  | grep -iE 'getCanonicalPath|substring'
```

Expect `substring` twice, with `iconst_1; iadd` marking the `len + 1` branch.

### Never "fix" this by widening the provider

Adding `<root-path>` or `<external-path>` lets the provider reach outside the app — user
storage becomes shareable with other processes. A correct fix here opens nothing new.

### Why it survives for many releases

Nothing connects the contents of `file_paths.xml` to the filename the downloader actually
writes. Two files drift apart with no gate objecting. Guard it by reading the name from the
runtime's own source, not a literal copied into the test:

```kotlin
val source = File("src/main/kotlin/.../ApkDownloader.kt")
val name = Regex("""File\(context\.cacheDir,\s*"([^"]+)"\)""").find(source.readText())!!.groupValues[1]
```

---

## 2. Material Compose icons are per-icon extension properties

`Icons.Filled.GraphicEq` fails to resolve even when the artifact is a declared dependency and
the icon provably exists:

```
Unresolved reference 'GraphicEq'.
```

`import androidx.compose.material.icons.Icons` does **not** carry any icon with it. Each icon
is its own extension property and needs `import androidx.compose.material.icons.filled.<Name>`
(or `.automirrored.filled.<Name>` for directional ones).

Confirm the symbol is really there before hunting the dependency:

```bash
unzip -l material-icons-extended-*.jar | grep -i graphiceq
javap -p androidx/compose/material/icons/filled/GraphicEqKt.class
```

`GraphicEqKt.class` present + property `getGraphicEq` means the only defect is the import.

**Gate:** after any `Icons.Filled.X` / `Icons.AutoMirrored.Filled.X` in a new file, check
that file imports `X`. Nothing but the compiler will tell you.

---

## 3. A test that mimics library internals must mimic EVERY step

A test that copies a library's algorithm is only as good as its fidelity. Copying
`startsWith` + `substring` but omitting `getCanonicalPath()` produced a test that **failed on
the correct fix** — `cache/.` does not `startsWith` `cacheDir/update.apk`.

Read the failure as a defect in the copy, not as an argument for reverting the fix. A test
that enforces the opposite of the right behaviour is worse than no test: it pushes the next
reader toward reintroducing the bug.

Two rules:

1. **Mirror incidental steps too.** Canonicalization, default-value ordering, and null
   coercion look like implementation noise; they are the parts the real behavior hinges on.
2. **Prove the copy catches the original defect.** Run the mimic against the *broken*
   configuration and require it to fail. A faithful copy that passes both ways is not
   faithful — it is decorative.

This generalizes past FileProvider: any hand-rolled mimic of library behavior is only
evidence if it was demonstrated to fail on the thing it claims to guard. Related trap already
in `dependency-version-upgrade.md`: "Prove the test catches the bug before trusting it" — that
section covers *fixtures*; this covers *mimics*.

---

## 4. Bytecode answers ordering questions documentation does not

When the load-bearing detail is an **order of operations** — which value wins, which default
overrides which, which step normalizes a path — docs frequently omit it. Read the bytecode.
Cheap, decisive, and often the only source:

```bash
# Which overload / which constant is actually referenced
javap -c -p <Class.class> | grep -B4 -A4 '<methodName>'

# Find which nested class holds the state you need
for c in androidx/core/content/FileProvider*.class; do javap -p "$c" | head -6; done
```

Disassembling from the Gradle cache needs no download:

```bash
find ~/.gradle/caches -path '*<artifact>*' -name '*.jar' | head -3
```

Bytecode still proves only *existence* and *shape* — per §0 of
`dependency-version-upgrade.md`, only compilation proves you can call it.

---

## 5. Numeric parameters in bug reports are evidence

`length=58; index=59` is not diagnostic noise to strip before reporting. Every number in a
crash is a claim about the runtime that can be **reproduced locally** and confirmed or
refuted before any code changes. Same for HTTP status, offset/length pairs, and index bounds.

Reproduce the numbers first, write the fix second. It converts a speculative fix into a
verified one, and when the numbers do *not* match your hypothesis, that mismatch is the next
lead — cheaper than any amount of code reading.

---

## 6. Dump a class's FULL public API before asserting on any of it

**Symptom.** A JVM test asserting `processor.getMethod("isEnabled")` looks plausible, passes
review, and fails in CI. Guessed accessors in a row: `isEnabled()` absent, `getEnabled()`
absent. The members actually declared were `setEnabled(boolean)` and `isActive()`.

**Mechanism.** `javap` on a class prints only members **declared in that class**, never
inherited ones. So grepping its output for a name proves nothing about callability — absence
in the output does not mean absence in the class, and presence of a *similar* name does not
mean that name exists.

**Procedure.** List the whole surface before writing a single assertion, then quote only
from that list:

```bash
javap -p <Class>.class | grep -E 'public|protected'
```

Inherited members may live in a **different artifact** than the subclass — a base class in
`media3-common` can supply a superclass for a type in `media3-exoplayer`, so check both jars
before concluding a method is missing. This is §4 (read the bytecode) applied to *method
existence* instead of ordering; a green compile only ever proves the symbols you actually
call, so reflection-based assertions can fail long after compile passed.

---

## 7. Gradle unit tests run with the working directory set to the MODULE

**Symptom.** A test that reads a source file throws `FileNotFoundException` for paths that
are obviously correct when read from the repo root.

- `File("PlaybackService.kt")` — fails
- `File("../data/repository/SettingsRepository.kt")` — fails
- `File("src/main/kotlin/com/meowlabs/player/playback/PlaybackService.kt")` — works

The working directory is the module dir (`app/`), not the package dir and not the repo root.

**Procedure: don't derive it, copy it.** Before writing the first source-reading test in a
project, grep the tests that already pass:

```bash
grep -rn 'File("' app/src/test/ | head
```

A project that already has green tests reading project files has already settled the
convention — reuse it rather than reasoning about what Gradle "should" do.

**Reading source text as a wiring test is legitimate.** When a bug class is "two files that
stopped matching" (a service never references the preference; a key is spelled differently
in the writer and the reader), asserting on the source text catches it while the file is
still cheap to change. Bound it honestly: source-text assertions prove the symbol is
*mentioned*, never that it runs. And make a missing file fail as a missing path rather than
an absent symbol — check existence first and report the absolute path, so "wrong path" never
reads as "feature not implemented":

```kotlin
private fun readSource(path: String): String {
    val file = File(path)
    assertTrue("Tidak bisa menemukan $path dari ${file.absolutePath}", file.exists())
    return file.readText()
}
```

---

## 8. Before disabling a switch on older Android, find the gate

**Symptom.** A plausible-sounding claim ("this needs Android 7.0+, so gate it by API level")
shipped into a plan as if it were fact. Verifying it against bytecode refuted it entirely: no
`@RequiresApi` annotation and no `Build.VERSION` check anywhere. The feature was pure DSP
(`SilenceSkippingAudioProcessor` / `DefaultAudioSink`) and worked on every supported release.

Guessing here is worse than not mentioning it — the fix built on the guess disables a working
switch on every older device, and the removal ships as an "improvement".

**Procedure — two greps before you write the gate:**

```bash
# Does the method carry an API-level annotation?
javap -v -p <Class>.class | grep -A6 '<methodName>' | grep -iE 'RequiresApi|SdkInt'

# Does any code path in the chain branch on the OS version?
javap -c -p <Class>.class | grep -iE 'SdkInt|Build|VERSION'
```

Both empty ⇒ no gate ⇒ the switch works everywhere. Say so, and keep a test asserting the
absence so a future library upgrade that *does* add a gate gets noticed.