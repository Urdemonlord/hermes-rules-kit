# Dependency / Compose BOM Version Upgrade

Deciding whether to bump the Compose BOM, or a single androidx artifact, and doing it without
breaking the build. Written from a session that burned hours discovering three of these the hard
way; every number here is measured, not assumed.

## 0. The rule that governs everything else

**Bytecode inspection proves a symbol EXISTS. Only compilation proves you can CALL it.**

Kotlin `internal` declarations compile to `public` JVM classes. So:

```
javap -classpath . androidx.compose.material3.MotionScheme
  -> public interface androidx.compose.material3.MotionScheme { ... }   # looks usable

# but the compiler says:
Cannot access 'interface MotionScheme : Any': it is internal in file.
```

This produced two consecutive wrong recommendations to the user before the build corrected them.
A `javap` signature is still worth having for parameter order and nested-class naming — just never
ask it "is this available?". Write the probe (step 3) instead.

## 1. Find the real library version (the BOM is a mapping, not a version)

`composeBom = "2024.12.01"` resolved to material3 **1.3.1**. Do not assume the BOM year maps to
the library's major version.

```bash
curl -s https://dl.google.com/dl/android/maven2/androidx/compose/compose-bom/<BOM>/compose-bom-<BOM>.pom \
  | grep -A2 '<artifactId>material3</artifactId>'
```

To find **which** BOM first carries a target artifact version, probe candidates oldest-first:

```python
import re
from hermes_tools import terminal

def mat3(bom):
    x = terminal(f"curl -s --max-time 25 https://dl.google.com/dl/android/maven2/"
                 f"androidx/compose/compose-bom/{bom}/compose-bom-{bom}.pom")['output']
    m = re.search(r'<artifactId>material3</artifactId>\s*<version>([^<]+)', x)
    return m.group(1) if m else None
```

Newest-BOM-first is the wrong direction: the BOM you need is usually several months old.

## 2. Pre-flight a candidate version WITHOUT building

Both files live inside the AAR. This predicts the entire cost of a bump before you touch a build
file — a `minCompileSdk` or `minAGP` you cannot meet makes the answer "no" for free.

```bash
cd /tmp && rm -rf m3 && mkdir m3 && cd m3
curl -s -o m.aar https://dl.google.com/dl/android/maven2/androidx/compose/material3/\
material3-android/<VER>/material3-android-<VER>.aar
unzip -o -q m.aar 'META-INF/com/android/build/gradle/aar-metadata.properties'
cat META-INF/com/android/build/gradle/aar-metadata.properties
# minCompileSdk=35
# minAndroidGradlePluginVersion=8.6.0
```

```bash
curl -s https://dl.google.com/dl/android/maven2/androidx/compose/material3/\
material3-android/<VER>/material3-android-<VER>.pom \
  | grep -B1 -A2 'kotlin-stdlib'
```

**The same file exists inside Maven Central AARs — use the other base URL.** androidx and AGP live on
Google Maven, but a third-party Compose/KMP library (a QR painter, chart, picker) lives on Maven
Central and carries the identical metadata. Getting the repo wrong yields a 404 that reads as
"version does not exist":

```bash
# Maven Central — note the different host AND path shape (no /dl/android/)
curl -sL -o t.aar https://repo1.maven.org/maven2/<group/path>/<artifact>/<VER>/<artifact>-<VER>.aar
unzip -p t.aar META-INF/com/android/build/gradle/aar-metadata.properties
```

**For a KMP library, check the PLATFORM-SUFFIXED module — and expect the suffix names to change
between releases.** The plain `qrose` coordinate is the metadata-only root; the Android artifact is
`qrose-encoder-matrix-android` in 1.3.0 but `qrose-matrix-android` in 1.2.0, and only the suffixed
module carries `aar-metadata.properties`. List the published modules rather than guessing a name
(`curl -s https://repo1.maven.org/maven2/<group/path>/ | grep -oE 'href="[^"]+"'`), and confirm the
version exists for **every** target platform you build — a KMP dependency must ship a klib per iOS
target (`...-iosarm64-<VER>.klib`) or the bump fails at resolution, not at link time.

Build the verdict table and show it to the user before deciding:

| Requirement | Source | Project has | Verdict |
|---|---|---|---|
| `minCompileSdk` | `aar-metadata.properties` | `compileSdk` | |
| `minAndroidGradlePluginVersion` | `aar-metadata.properties` | AGP in `libs.versions.toml` | |
| `kotlin-stdlib` | `.pom` | `kotlin` in `libs.versions.toml` | |

### Kotlin metadata compatibility (catches the cascade)

A bumped artifact can require a newer Kotlin than the project uses, which drags KSP, Hilt, and the
Compose compiler plugin along with it — turning "one version number" into a toolchain migration.

```bash
mkdir -p cls && unzip -o -q classes.jar -d cls
javap -v -classpath cls androidx.compose.material3.MaterialThemeKt 2>&1 \
  | grep -A3 'kotlin.Metadata'
# mv=[2,0,0]  -> readable by Kotlin 2.0.x
```

## 3. Scan the version series for the cheapest usable version

When the newest release demands an upgrade cascade, walk backwards. The requirements are NOT
monotonic across a series in practice — they step, and the step is usually abrupt and findable.

Measured on material3 `1.5.0-alpha*`:

| Version | `minCompileSdk` | `minAGP` | `kotlin-stdlib` | Usable on Kotlin 2.0.21 / AGP 8.7.3 / compileSdk 35 |
|---|---|---|---|---|
| `alpha12` | 35 | 8.6.0 | 2.0.21 | **yes — zero toolchain change** |
| `alpha18` | 35 | 8.6.0 | 2.1.20 | no (Kotlin) |
| `alpha19`+ | 37 | 9.1.0 | 2.1.20 | no (everything) |
| `alpha28` | 37 | 9.1.0 | 2.1.20 | no (everything) |

**The boundary is the finding.** One session concluded "Expressive needs a full toolchain
upgrade" from `alpha28` alone, then found `alpha12` needed nothing — same feature, same library,
sixteen versions earlier. Scan the series before declaring a requirement unmeetable.

Also check what Compose UI version each candidate pulls, since that is what lint must tolerate:

```bash
curl -s <pom-url> | grep -E 'ui-android|runtime-android|foundation-android'
```

A candidate pinning `runtime 1.9.0-rc01` (a pre-release) is a lint-crash risk; prefer one on a
settled `runtime`.

## 4. The probe — the only real accessibility test

Temporary file, compiled, then deleted. Costs one `compileDebugKotlin` (~20 s warm) and replaces
every bytecode guess.

```kotlin
package <your>.ui.theme

import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.MaterialExpressiveTheme
import androidx.compose.material3.MotionScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

/** TEMPORARY probe — deleted after the test. */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
internal fun ExpressiveProbe(content: @Composable () -> Unit) {
    MaterialExpressiveTheme(
        colorScheme = darkColorScheme(),
        motionScheme = MotionScheme.expressive(),
        content = content,
    )
}
```

Notes that save a round-trip:

- **Reference only public symbols from other files in the probe.** A `private val` colour scheme in
  the real `Theme.kt` is not reachable, so a probe that uses it fails for the wrong reason.
  `darkColorScheme()` inline keeps the probe self-contained.
- **Do not guess the opt-in annotation.** If the symbol needs one and you name the wrong one, the
  probe fails on the annotation rather than the API. If unsure, omit `@OptIn` first and let the
  compiler tell you which annotation it wants.
- **Delete the probe before committing** — it is scaffolding, not code. Confirm with
  `git status` that it is gone.

## 5. Verify with the full gate, not the compile gate

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME=$HOME/android-sdk
./gradlew :app:lintDebug :app:assembleDebug :app:testDebugUnitTest --console=plain
```

**On a low-RAM host (<4GB), run those tasks ONE invocation at a time with `--no-parallel`.**
Combining them lets Gradle run the dex, lint, and Kotlin work concurrently, and the failure lands
somewhere that reads like a code error but is not:

```
Execution failed for task ':app:mergeExtDexDebug'.
> com.android.builder.dexing.DexArchiveMergerException: Error while merging dex archives:
  at com.android.tools.r8.dex.C.a(...)
  at java.base/java.util.concurrent.ForkJoinPool.runWorker(...)
```

An R8 `ForkJoinPool` stack with no message under `mergeExtDexDebug` is an **out-of-memory during
concurrent dexing**, not a broken build file. Confirm before touching any code:

```bash
free -m                                  # little free + swap in use = memory, not code
ls java_pid*.hprof                       # a heap dump in the repo root is the smoking gun
grep -E '^e: ' <the same run's output>    # zero Kotlin errors means the code compiled fine
```

In one session `compileDebugKotlin` reported success inside the very same invocation that then
failed at `mergeExtDexDebug` — that combination is the tell. **Do not start hunting a Kotlin error
that does not exist.** Clear the daemon (it is still holding the exhausted heap) and re-run
sequentially, cheapest task first:

```bash
./gradlew --stop
pkill -f GradleDaemon; pkill -f KotlinCompileDaemon
free -m                                   # confirm the memory came back before re-running
./gradlew :app:lintDebug     --console=plain --no-parallel
./gradlew :app:assembleDebug --console=plain --no-parallel
```

This is also why CI splits lint and packaging into separate jobs: they are separate JVMs there, so
they never contend for one heap. Reproduce that isolation locally instead of trusting that the
combined command works because it works in CI.

Add `*.hprof` to `.gitignore` — heap dumps land in the project root at hundreds of MB and will
otherwise show up in `git status` as an untracked file worth deleting by hand.

**`compileDebugKotlin` green does NOT mean the bump is safe.** androidx artifacts ship their own
lint detectors. A detector built against a newer Kotlin Analysis API than the AGP-bundled lint
crashes the lint task:

```
IncompatibleClassChangeError
```

Observed with material3 1.4.0 under AGP 8.7.3: the Kotlin compile passed and `lintDebug` failed.
So the cheap gate is right for *iterating*, and the full gate is what decides whether to keep the
bump. If the bump buys nothing and breaks lint, **revert it** — do not add a lint baseline to hide
it, and do not keep a version that only compiles.

## 6. When the daemon dies: metaspace, not heap

```
Gradle build daemon disappeared unexpectedly (it may have been killed or may have crashed)
The Daemon will expire after the build after running out of JVM Metaspace.
```

The second line is the diagnosis. **Metaspace holds class metadata**, so a dependency set that
adds many classes — plus its own lint detector — grows metaspace directly, and raising `-Xmx`
does nothing.

```properties
# gradle.properties
org.gradle.jvmargs=-Xmx1536m -XX:MaxMetaspaceSize=768m -Dfile.encoding=UTF-8
kotlin.daemon.jvmargs=-Xmx768m
```

On a low-RAM host, budget all three JVMs together before raising any one — heap + metaspace +
Kotlin daemon. A cap that was correct for the previous dependency set can be too small for the
new one, so check `gradle.properties` for a stale limit first. An earlier `-Xmx` OOM and this
metaspace death look similar in the tail of the output and are fixed by opposite changes.

## 7. Report shape

The user is making a version/architecture decision, so lead with the verdict, not the journey:

1. **Does it work, and at what cost** — the requirement table, filled in.
2. **What the alternative costs** — the version that needs nothing vs. the one that needs a
   toolchain migration, with the concrete list (SDK, AGP, Gradle, Kotlin, KSP).
3. **Which parts are verified and which are not** — say which gates ran green and what was never
   run on a device.
4. **Revert cleanly if the answer is no.** Restore the version file, delete probe/scratch sources,
   confirm `git status` is clean, and leave the reasoning in the project's canonical doc so the
   next session does not re-run the investigation.

## 8. A TRANSITIVE pin defeats your own downgrade

Downgrading your direct declaration changes nothing while a library you depend on pins the newer
artifact — Gradle resolves to the HIGHEST version in the graph. Check the dependency's `.pom`,
not just your own version catalog:

```bash
curl -s "<repo>/<group-path>/<artifact>/<ver>/<artifact>-<ver>.pom"
```

Observed: CMP lowered to 1.11.1 but `checkDebugAarMetadata` still demanded compileSdk 37, because
the QR library at 1.2.0+ declared `org.jetbrains.compose.ui:ui:1.12.0`. Fix the library that
carries the pin (downgrade it) — its older release pinned `compose.ui:1.10.0`, which is safe.
When a version bump does not take effect, suspect a transitive pin before doubting your edit.

## 9. AGP 9 changes the KMP project shape

AGP 9+ no longer supports `com.android.application` / `com.android.library` alongside the Kotlin
Multiplatform plugin. Migrating means splitting into a separate `androidApp` module plus the new
`androidLibrary` plugin — a restructure, not a version bump. Do not "just bump AGP" on a KMP
module; either budget the restructure or hold the toolchain at the AGP 8 line.

Also: modern Compose Multiplatform no longer publishes `iosX64` / `macosX64` (Kotlin deprecated
Apple x86_64). Keep `iosArm64` + `iosSimulatorArm64` only; a missing artifact surfaces as
`Unresolved platforms: [iosX64]`. Verify per-target availability with a HEAD request on the
`.klib`/`.aar` — a `404` is the real answer.

## 10. CI as the compiler when the host cannot build

On a low-RAM host where a Gradle daemon OOMs, let GitHub Actions be the compiler and iterate:

```bash
git push origin main
gh run list --limit 3 --json databaseId,status,conclusion,headSha
gh run view <id> --json status,conclusion,jobs
gh run view <id> --log-failed          # often TRUNCATES the Kotlin errors
gh run view <id> --log > /tmp/ci.log   # full log, then grep '^e: ' for compile errors
```

`--log-failed` shows the Gradle failure but the `e: file:///... .kt:LINE ...` lines can be cut
from the middle. Save the full `--log` to a file and grep it — the log is large enough to be
truncated in the tool result too, so write it to disk and search the file.

Push small commits so each one is a single compiler iteration; errors get progressively deeper
(dependency resolution -> AAR metadata -> Kotlin compile). **Check the workflow's branch trigger
before pushing** — a repo whose default branch is `master` while CI listens on `main` runs
nothing, and the silence looks like a passing build.

### Prove the tests actually RAN — a green test job can execute zero tests

A Gradle test task **succeeds when it runs nothing**. In a KMP project `commonTest` is not always
wired to the Android unit-test task, so `:app:testDebugUnitTest` prints `BUILD SUCCESSFUL` having
executed no assertions — the most dangerous kind of green, because it is indistinguishable from a
passing suite. Do not claim "N tests pass" from a green job; gate on the **count**.

```yaml
- name: Uji modul bersama
  run: ./gradlew :composeApp:testDebugUnitTest --stacktrace

# Without this, the task is green even when zero tests ran.
- name: Laporkan jumlah tes
  run: |
    set -e
    TOTAL=0
    for f in composeApp/build/test-results/testDebugUnitTest/*.xml; do
      [ -e "$f" ] || continue
      N=$(grep -o 'tests="[0-9]*"' "$f" | head -1 | grep -o '[0-9]*')
      TOTAL=$((TOTAL + N))
      echo "  $(basename "$f"): $N tes"
    done
    echo "TOTAL TES DIJALANKAN: $TOTAL"
    if [ "$TOTAL" -eq 0 ]; then
      echo "::error::Tidak ada tes dijalankan - commonTest tidak terhubung."; exit 1
    fi
    grep -rl '<failure\|<error' composeApp/build/test-results/testDebugUnitTest/ \
      && { echo "::error::Ada tes yang GAGAL."; exit 1; } || echo "Semua tes lulus."

- name: Simpan hasil tes
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: hasil-tes
    path: composeApp/build/test-results/testDebugUnitTest/
    if-no-files-found: warn
```

`--log-failed` and even the full `--log` routinely truncate a step's stdout, so read the count back
from the **artifact**, not the job summary — the number is the evidence:

```bash
gh run download <id> -n hasil-tes -R <owner>/<repo>
# then sum tests= / failures= / errors= / skipped= across TEST-*.xml
```

**A total count proves SOME tests ran — not that the ones you just added did.** A new test class
placed in the wrong source set or package compiles fine and never executes, and the count stays
green because the pre-existing suites supply the number. Gate on the NAMES you added, read from the
downloaded report:

```bash
gh run download <id> -n <report-artifact> -R <owner>/<repo>
find . -path '*test-results*' -name 'TEST-*.xml' | grep -E '<NewClassA>|<NewClassB>'
# each new class must appear; the HTML report also carries per-method results
#   build/reports/tests/testDebugUnitTest/classes/<pkg>.<Class>.html
```

Each new test method should appear as `passed` on that class page, not merely be counted. When a
class you just wrote is absent from the report, the suite never saw it — fix the source set or
package before believing the green. Reading the named methods back from the artifact is what turns
"the build is green" into "my change is tested".

### A green test can still pass without reading the file it guards

The count gate above proves tests RAN. It does not prove they read the artifact you ship. A suite
whose fixtures are JSON strings written inside the test file stays green while the real asset is
broken, because the two never meet. Two silent mechanisms:

1. **A required field with no default fails the WHOLE file, not one entry.** In a serialized list
   where the version field has no default, a single entry using the wrong key (`version` instead of
   `versionName`) makes the parser throw for the entire document — so the whole screen shows an
   error instead of one missing row. A typo in a data file is a total-feature outage, not a
   cosmetic glitch, and nothing in the build notices.
2. **An asset is not a test input unless you declare it.** Change only `src/main/assets/*.json` and
   Gradle considers the test task UP-TO-DATE, skips it, and prints `BUILD SUCCESSFUL` — the same
   false green the count gate prevents, one level deeper.

Fix both: read the real file from disk, and declare it as an input.

```kotlin
// test: resolve from the module dir, which is the CWD under Gradle
val file = java.io.File("src/main/assets/changelog.json")
val entries = Parser.parse(file.readText(Charsets.UTF_8))
assertTrue(entries.isNotEmpty())
// the version in the asset must equal the app's own version, or "current" points at the wrong row
assertEquals(BuildConfig.VERSION_NAME, Parser.latest(entries)?.versionName)
```

```kotlin
// build.gradle.kts — without this the task is UP-TO-DATE whenever only the asset changed
android {
    testOptions {
        unitTests.all {
            it.inputs.file(layout.projectDirectory.file("src/main/assets/changelog.json"))
        }
    }
}
```

**Prove the test catches the bug before trusting it.** A regression test that has never failed is a
guess. Rewrite the asset into the broken shape, run the suite WITHOUT `--rerun-tasks`, and require a
non-zero exit plus a failure naming the new test. If it stays green, either the assertion is wrong
or the input declaration is missing — a suite that only fails under `--rerun-tasks` is the tell that
the input is undeclared. Restore the asset and confirm green again.

### Dates in the asset: format checks are not truth checks

The same asset-reading gate has a second failure mode that has nothing to do with schema. A
version-history asset carries a release date per entry, and a suite that only checks
`YYYY-MM-DD` **passes on invented dates**. Real case: three releases shipped the same day were
written with consecutive dates (one day per version) to look tidy, so the in-app history showed
`2026-10-01` while `update.json` / the download page (generated from the system date) showed
`2026-09-28` for the same release. Two sources, two dates, and the one inside the app was wrong.

Assert the date against **the clock**, not against a literal:

```kotlin
// Reads the shipped asset, like the schema test above, not a fixture in the test.
val entries = Parser.parse(File("src/main/assets/changelog.json").readText(Charsets.UTF_8))
val today = java.time.LocalDate.now()
val future = entries
    .mapNotNull { e -> e.publishedAt?.let { d -> e.versionName to d } }
    .filter { (_, d) -> java.time.LocalDate.parse(d).isAfter(today) }
assertTrue("tanggal rilis di masa depan: $future", future.isEmpty())
```

Three rules that make this test worth having:

1. **Use `LocalDate.now()`, never a hard-coded date.** A test pinned to a literal date passes
   forever and guards nothing. This is the same trap as a fixture written inside the test file.
2. **A format check is not a truth check.** `matches(Regex("""\d{4}-\d{2}-\d{2}"""))` accepts every
   fabricated date. Both checks are needed; neither replaces the other.
3. **Also assert the entries are ordered newest-first.** The history screen renders the list as
   written, so an entry in the wrong position just looks "odd" and nothing flags it.

A future-dated entry is only *possible* because the date is hand-written while `update.json` is
generated. Wherever one value is typed and its twin is derived, the typed one is the one that
drifts. Prefer deriving both, and test the typed one against the derived one.

### Derive the generated date FROM the asset, not from the clock

"Prefer deriving both" is not enough on its own: two derivations from two different clocks still
disagree. A release script that stamps `update.json` with `datetime.date.today()` computes a
*second* date, so any run after local midnight (or on a host in another timezone) writes a date
that differs from the one inside the APK.

**Pinning a timezone is not the fix.** By the time the mismatch is noticed the clock has already
crossed midnight, so `today()` under the "correct" zone still yields the later date. The root cause
is two sources, not a wrong zone. Read the date out of the asset the APK actually ships, and refuse
to publish when the version being released is not in it:

```python
import json, zipfile
entries = json.loads(zipfile.ZipFile(apk).read("assets/changelog.json"))
published_at = next(e["publishedAt"] for e in entries if e["versionName"] == VERSION)
# no fallback to date.today() — a missing entry is a hard error, not a default
```

A guard test can lock this: assert the release script contains no clock-derived date and does read
`publishedAt` from the asset.

**Strip comments before scanning the script in that test.** A first version that grepped the raw
file for `date.today()` failed on the *comment explaining the defect*: the substring was in prose,
not code. Scan code lines only:

```kotlin
val kode = skrip.lines().filterNot { it.trimStart().startsWith("#") }.joinToString("\n")
assertFalse("skrip memakai jam sistem", kode.contains("date.today()"))
```

A test that fires on your own explanatory comment is worse than no test: the next person "fixes" it
by loosening the assertion until it guards nothing.

The same discipline applies to the APK: a debug APK is un-minified, so a size target measured for a
**release** build (R8 + shrinkResources) is not evidence about a debug artifact — measure the build
type the target was written for. Then verify the release artifact itself, not just its size: a green
build can ship an R8-minified APK whose reflection-reached classes were silently stripped. See
`references/app-performance-and-release-build.md` for the size-gate step, the dex/manifest survival
checks, and the unsigned-artifact blocker.

## 11. Cross-reference every boundary symbol before pushing

With no local compiler, a batch of generated files can reference a type or function that was
never written. Grep each cross-file symbol and confirm a DEFINITION exists — `grep` proves a name
is *used*, not that it is defined, so search for `class X` / `fun x(` rather than the bare name.
Importing a symbol that does not exist is the most common self-inflicted compile error, and the
compiler reports it as a cascade (every use site, plus downstream `Unresolved reference` for
fields of the missing type).

Run `scripts/check-dangling-imports.py <src-root> <package-prefix>` before every push — it scans
every internal import and fails if any has no matching definition. It collects **extension
functions** (`fun Type.name(`) as definitions too; a naive `class|fun|val` scan reports every
storage/helper extension as a false positive.

This pattern recurs whenever code is written without a compiler: in one session the same mistake
appeared three separate times (a notification model, a platform context accessor, a payment-signal
DTO), each discovered only after a CI round-trip. Treat "did I actually define every type I
import?" as a mandatory gate, not a habit.

### The same gate covers library METHOD names, not just your own types

`check-dangling-imports.py` only sees *your* package prefix, so it passes clean while the real
error is one level out: a call on a library object whose method name you wrote from memory. The
name is plausible enough to survive review and wrong enough to be a compile error — JUnit's
`TemporaryFolder` has `newFile(name)`, not `createFile(name)`, and nothing else in a small test
file hints that `createFile` was invented. The compiler reports it as
`Unresolved reference` plus a cascade of `Cannot infer type for this parameter` on the same
expression, which reads like a lambda-typing problem and sends you to the wrong line.

Two cheap checks, in order of cost:

1. **Grep the repo's own existing usages before writing a new one.** If nobody has used this helper
   before, you have no evidence the name is right.
   ```bash
   grep -rn 'TemporaryFolder\|\.newFile(\|\.createFile(' app/src/test --include='*.kt'
   ```
   A grep that returns only your own new file has confirmed nothing.

2. **`javap` the artifact when no local usage exists.** This is the same "bytecode proves the symbol
   exists, compilation proves you can call it" rule from §0, aimed at the method name.
   ```bash
   JAR=$(find ~/.gradle/caches -name 'junit-4.13.2.jar' | head -1)
   javap -classpath "$JAR" org.junit.rules.TemporaryFolder | grep -E 'File|folder'
   ```

The same class of error covers anything reached through a receiver you did not write: rule and
fixture APIs, builders whose factory is named differently from the type, platform constants.
When the failing expression is a **method call on something the test did not define**, stop reading
the error as a typing problem and go verify the method name.
