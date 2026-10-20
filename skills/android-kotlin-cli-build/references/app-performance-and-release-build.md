# App feels heavy: release build + runtime performance

Triggered by a user saying the app is slow, janky, heavy, or laggy. Work the list in order —
the dominant cause is usually the build type, and it is invisible from the source tree.

## 1. Diagnose before optimizing — establish the facts first

Do NOT start rewriting composables. Four measurements decide where the cost actually is:

```bash
# (a) Which build type is actually SHIPPED? Inspect the published APK, not the repo.
BT=$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)
for f in /var/www/<host>/*.apk; do "$BT/aapt2" dump badging "$f" | grep '^package'; done
#   package: name='com.x.app.debug'  <- the .debug suffix means every shipped build was DEBUG

# (b) minify / shrink per build type
sed -n '/buildTypes/,/^    }}/p' app/build.gradle.kts

# (c) baseline profile present anywhere?
find . -name '*baseline*' -o -name '*.prof' | grep -v build/

# (d) image loading config
 grep -rn 'ImageLoader\|ImageLoaderFactory\|memoryCache\|diskCache' app/src/main --include=*.kt
 grep -rn '\.size(' app/src/main --include=*.kt | head
```

A `.debug` applicationId on a published APK answers the question by itself. Check it before
speculating about recomposition.

## 2. Debug vs release — the dominant factor

A debug APK differs from release in ways that all slow startup and scrolling:

| | debug | release |
|---|---|---|
| R8 / minify | off | on (shrinks + optimizes) |
| resource shrink | off | on |
| baseline profile | not installed | installed |
| `debuggable` flag | true | false |

`debuggable=true` is the big one: ART runs without the AOT/JIT optimizations it applies to
non-debuggable apps, plus JNI argument checking and profiling hooks stay enabled. Expect a
**2–4x difference** in cold start and noticeable scroll jank. If every version a user has ever
installed was `debug`, that alone explains "the app feels heavy" — no code change is needed.

The size gap is just as large and is the easiest number to show the user. Measured on one Compose +
Hilt + Room + Media3 app: **25.2 MB debug → 4.3 MB release (83% smaller)**. Quote both figures in the
report — it makes the build-type fix concrete in a way "we enabled minify" does not.

## 3. Ship release WITHOUT forcing a reinstall

Normally changing build type changes the applicationId (`com.x.app` vs `com.x.app.debug`), which
Android treats as a **different app**: the user must install fresh and re-scan their media library.
To get release optimization while upgrading in place, give release the SAME suffix the debug build
uses:

```kotlin
buildTypes {
    debug {
        applicationIdSuffix = ".debug"
        isMinifyEnabled = false
    }
    release {
        isMinifyEnabled = true
        isShrinkResources = true
        applicationIdSuffix = ".debug"   // <- same package id as the debug builds already installed
        proguardFiles(
            getDefaultProguardFile("proguard-android-optimize.txt"),
            "proguard-rules.pro",
        )
        signingConfig = signingConfigs.getByName("debug")
    }
}
```

Both conditions must hold: identical `applicationId` **and** identical signing key. The project
should already commit a fixed `debug.keystore` and point `signingConfigs.debug` at it; a random
per-machine debug key would reject the install. The cost is a `.debug` package name in production —
correct for a sideloaded personal app, wrong if it ever goes to Play.

Verify after building: `aapt2 dump badging app-release.apk | grep '^package'` must show the SAME
name as the currently installed version, and `apksigner verify --print-certs` the same digest.

## 4. The first `assembleRelease` will probably fail — and that is the useful part

R8 is stricter than the compiler. A release build that has never been run almost always fails once,
and **R8 writes the fix for you**:

```
ERROR: Missing classes detected while running R8.
ERROR: R8: Missing class java.beans.BeanDescriptor (referenced from:
       java.lang.Object org.mozilla.javascript.JavaToJSONConverters.lambda$static$4(...))
> Task :app:minifyReleaseWithR8 FAILED
```

```bash
cat app/build/outputs/mapping/release/missing_rules.txt   # the -dontwarn lines R8 generated
```

Add those lines to `app/proguard-rules.pro`. The classic source is a jar that references a JDK API
Android does not ship (`java.beans.*`, `javax.script.*` via Rhino) — a **dead code path**, so
`-dontwarn` is correct rather than a workaround.

Beyond the generated lines, keep rules are needed for anything reached by reflection. Libraries
that ship their own consumer rules are fine; the ones that do not must be kept explicitly:

```pro
# Reflection-based, no consumer rules shipped (verify per library, do not assume)
-keep class org.schabi.newpipe.** { *; }
-dontwarn org.schabi.newpipe.**
-keep class org.mozilla.javascript.** { *; }
-keep class org.mozilla.classfile.** { *; }
-dontwarn org.mozilla.javascript.**

# Generated / annotation-processed
-keep class * extends androidx.room.RoomDatabase
-keep class dagger.hilt.** { *; }
-keepclasseswithmembers class * { kotlinx.serialization.KSerializer serializer(...); }

-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn androidx.media3.**
```

Check whether a jar already ships rules before hand-writing them:

```bash
unzip -l <lib>.jar | grep -i proguard      # empty output = you must write them
```

### A green release build does NOT prove a reflection-based feature works

R8 strips names that reflection looks up at RUNTIME. A missing keep rule produces no build error and
no compile warning — the feature just fails on the device. So "release builds" is not the end of the
check: the user must exercise every reflection-heavy path (external extractor / streaming, JSON
deserialization, database open) and report. If one breaks, narrow the keep rule for that library
before considering disabling minify.

### Verify R8 on the ARTIFACT, not on the ProGuard file

A keep rule being present in `proguard-rules.pro` does not prove the class survived. When you cannot
run the app (headless host, no device), inspect the built dex + merged manifest instead:

```bash
A=$(find . -name '*release*.apk' | head -1)
mkdir -p dx && unzip -o -q "$A" 'classes*.dex' -d dx

# 1. Serializers survived — kotlinx.serialization is the #1 R8 casualty.
strings dx/classes.dex | grep -c '\$\$serializer'

# 2. Obfuscation actually ran — count references to the ORIGINAL package path.
#    A small count means classes were renamed/repackaged as intended.
strings dx/classes.dex | grep -c '<original/pkg/path>'

# 3. Manifest components + permissions survived shrinkResources.
aapt dump badging "$A" | head
aapt dump permissions "$A"
java -jar ~/tools/apktool.jar d -f -s -o mf "$A"
grep -iE 'service|intent-filter|permission' mf/AndroidManifest.xml
```

A surviving `$$serializer` set, evidence of repackaging, and an intact `<service>` + intent-filter in
the merged manifest is the proof that minification kept the reflection-reached paths. Say which of
these you ran and which you did not.

**Class-name obfuscation does NOT rename names inside `AndroidManifest.xml`.** Android resolves
components by the literal string, so `android:name=".MyApplication"` and a
`NotificationListenerService` declaration stay original by design — do not read that as "obfuscation
failed".

### The size gate belongs in its own CI step, and measure the right build type

**Never quote a debug APK size against a release size target.** Debug is un-minified and can be ~7x
larger (e.g. 14 MB debug vs 2.04 MB release). Measure the build type the target was written for.

Put the size assertion in a SEPARATE step from `assembleRelease`, so a red run tells you which
failed — the BUILD or the SIZE — and print the measured size to the step summary:

```yaml
- name: Bangun APK release
  run: ./gradlew :composeApp:assembleRelease
- name: Periksa target ukuran
  run: |
    set -e
    APK=$(find composeApp/build/outputs/apk/release -name '*.apk' | head -1)
    BYTES=$(stat -c%s "$APK")
    echo "Ukuran release: $BYTES byte" >> "$GITHUB_STEP_SUMMARY"
    if [ "$BYTES" -gt 4194304 ]; then echo "::error::APK > 4 MB"; exit 1; fi
```

**A release APK from a default Gradle Android app is `*-release-unsigned.apk` and CANNOT be
installed.** The size gate can pass while install-testing remains impossible — say so instead of
implying the release is verified. Signing needs a release keystore that must stay OUT of the repo;
keep a CI `secrets` job that fails when a `*.jks` / keystore appears in the tree. For the full
keystore-in-CI-secrets flow plus the `apksigner` verification gate that proves the shipped artifact
is signed, see `references/release-signing-and-secret-keystore.md`. Bytecode survival
proves a class is PRESENT, not that it is CONSTRUCTIBLE — static verification downgrades the risk,
it does not replace an on-device run.

## 5. Baseline profile — free startup win, needs one dependency

Compose's `ui`/`foundation` AARs ship a `baseline-prof.txt`, which tells ART which classes to AOT
compile at install time. Verify it exists:

```bash
unzip -l ~/.gradle/caches/modules-2/files-2.1/androidx.compose.ui/ui-android/**/ui-release.aar \
  | grep baseline-prof
```

It is only installed on the device if `androidx.profileinstaller` is a dependency — without it the
file is packaged and never used, and startup stays slow:

```toml
profileinstaller = { module = "androidx.profileinstaller:profileinstaller", version.ref = "profileinstaller" }
```
```kotlin
implementation(libs.profileinstaller)
```

**Verify the profile landed in the built APK, not just that the dependency is declared** — the two
are different claims and only the first one helps the user:

```bash
unzip -l app-release.apk | grep -i baseline   # expect assets/dexopt/baseline.prof (+ .profm)
```

## 6. Image loading in long lists — the runtime cost that survives R8

**No `size()` on an `ImageRequest` means Coil decodes at the image's native resolution.** Album art
is routinely 1000x1000 px or larger; decoded at full size that is ~4 MB in memory per image, and in
a scrolling list the allocations outpace the cache so the GC runs continuously — which the user
feels as jank, not as an error. Pass the display size explicitly:

```kotlin
val density = LocalDensity.current
val px = with(density) { size.roundToPx() }
ImageRequest.Builder(context)
    .data(source)
    .size(px)          // drives inSampleSize; without it you pay for the full bitmap
    .build()
```

A composable that knows its own size should pass it down. For a blurred background layer, half the
screen width is more than enough — blur discards the detail anyway, and it cuts that layer's memory
to a quarter.

**Give the app ONE ImageLoader, via `ImageLoaderFactory` on the `Application`.** Constructing
`ImageLoader(context)` per screen gives each screen its own memory and disk cache, so the same
artwork is decoded repeatedly and disk caches pile up.

```kotlin
class App : Application(), ImageLoaderFactory {
    override fun newImageLoader(): ImageLoader = BlossomImageLoader.create(this)
}
```

Bound the caches explicitly. Defaults are percentages of available memory/disk and can be huge:

```kotlin
ImageLoader.Builder(context)
    .memoryCache { MemoryCache.Builder(context).maxSizeBytes(64 * 1024 * 1024).build() }
    .diskCache  { DiskCache.Builder().directory(context.cacheDir.resolve("artwork"))
                    .maxSizeBytes(128L * 1024 * 1024).build() }
    .build()
```

### Two Coil API traps that cost a build cycle each

- **`MemoryCache.Builder.maxSizeBytes` takes an `Int`; `DiskCache.Builder.maxSizeBytes` takes a
  `Long`.** Writing `64L * 1024 * 1024` for the memory cache is a type error. Pass an `Int` there.
- **`maxSizePercent` and `maxSizeBytes` are the same setting — the last call wins.** Calling both is
  not a belt-and-braces clamp, it silently discards the first. Pick one and delete the other, or the
  next reader will believe a limit that is not in effect.

Confirm signatures against the artifact before writing, rather than trusting recall:

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
cd /tmp && unzip -oq <coil-base>.aar classes.jar && unzip -oq classes.jar -d cls
$JAVA_HOME/bin/javap -classpath cls 'coil.memory.MemoryCache$Builder' | grep maxSize
```

(Quote nested class names — `$` is special to the shell.)

## 7. Close-out checklist

1. `./gradlew :app:lintDebug :app:assembleDebug :app:testDebugUnitTest :app:assembleRelease` — all green.
   Budget the time honestly: the FIRST `assembleRelease` on a 2 vCPU / 3.6 GB host took **~10.5 min**
   (R8 loads the whole app into memory) against ~2 min for a warm debug compile. Run it in the
   background with a completion notification rather than blocking, and check `free -m` first.
2. `aapt2 dump badging` the release APK: same package name as the installed version, versionCode bumped.
3. Bump `versionCode`/`versionName` — an unchanged versionCode means the in-app updater never offers it.
4. Release it, then have the user exercise the reflection-heavy paths and report.
5. Only then continue with any other pending work — do not stack a large unrelated change on top of an
   unverified release.
