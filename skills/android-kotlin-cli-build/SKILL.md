---
title: Android / Kotlin CLI Build (Headless Host)
name: android-kotlin-cli-build
description: Build Kotlin/Android apps headless via CLI, no IDE.
triggers:
  - User asks "bisa jalanin Android Studio?", "bisa ngoding Kotlin?", "can you build an Android app?"
  - Building an APK on a headless VPS / server with no display
  - Setting up kotlinc, Android SDK (sdkmanager), or Gradle from the command line
  - Compiling Kotlin (JVM, JS, WASM) without an IDE
  - Gradle build OOM or killed on a low-RAM (<4GB) machine
    (`references/low-ram-build-discipline.md` — separate invocations, background builds, daemon death)
  - A dependency demands a newer compileSdk / AGP / Gradle, or Compose Multiplatform version
    compatibility is unclear (`references/dependency-version-upgrade.md`)
  - A crash message contains string lengths, index bounds, or other numbers that look like
    noise, or a runtime trap compiles clean and only surfaces on device
    (`references/android-runtime-traps.md`)
  - Using GitHub Actions as the compiler, or proving a green test job actually ran
    (`references/dependency-version-upgrade.md`)
  - A crash message with string lengths or index bounds, or a trap that compiles clean
    but only surfaces on device (`references/android-runtime-traps.md`)
  - A green test suite that never reads the file it is supposed to guard (fixtures written inside
    the test), a shipped asset whose schema silently breaks the whole screen, or a test task that is
    UP-TO-DATE whenever only an asset changed (`references/dependency-version-upgrade.md`)
  - Writing Kotlin you cannot compile locally and wanting a pre-push check that every imported
    type is actually defined (`scripts/check-dangling-imports.py`)
  - Reviewing Kotlin/Compose code by reading before pushing — missing cross-package imports,
    per-icon `Icons.Filled.X` imports, audio effects attached to a rebuilt `audioSessionId`,
    hardcoded device ranges, "unsupported" shown for "not known yet", non-ASCII garbage in
    generated comments (`references/compose-static-analysis-pitfalls.md`,
    `scripts/scan-mixed-script.py`)
  - A release APK that must be installable while the user holds no keystore — signing from CI
    secrets plus an `apksigner` verification gate (`references/release-signing-and-secret-keystore.md`)
  - Measuring a release APK against a size target, or proving R8/shrinkResources did not strip
    reflection-reached classes (`references/app-performance-and-release-build.md`)
  - Shipping a try-able DEMO build before the backend exists — a third build type, a one-flag
    gateway swap, and proving the demo code is absent from the release dex
    (`references/demo-mode-build-variant.md`)
  - The API base URL changed, or a fix must reach users who already have the app installed —
    versionCode bump, reading the host back out of the dex, serving the API from a path while DNS
    is unavailable, and refusing to publish the wrong variant
    (`references/in-app-update-and-base-url.md`)
  - Adding a Media3 / ExoPlayer playback service, Room migration, or MediaStore scan to an
    Android app (`references/media3-playback-service.md`)
  - Albums/singles are grouped wrong, two albums with the same title merge into one, or songs with
    no album tag vanish from the Albums screen — grouping by a stable identity key, the "no value"
    bucket, and the Kotlin-vs-SQL key-parity check (`references/media3-playback-service.md`)
  - Adding user-picked music folders via Storage Access Framework, or any `OpenDocumentTree`
    / `DocumentFile` work (`references/saf-custom-folder-scanning.md`)
  - Validating a Room migration before shipping it to a device
    (`scripts/validate-room-migration.py`)
  - Adding an external media extractor (YouTube Music / SoundCloud via NewPipe-style libs),
    or judging what a headless/cloud host can and cannot verify for streaming
    (`references/streaming-extractor-integration.md`)
  - Adding an in-app "new version available" prompt to a sideloaded APK, or distributing
    builds from your own host (`references/sideloaded-app-update-checker.md`)
  - Adding an in-app version history / "what's new" screen listing every past release, or rewriting
    a developer CHANGELOG into user-facing notes (`references/sideloaded-app-update-checker.md`)
  - Adding lyrics (LRCLIB lookup, LRC parsing, synced line highlighting)
    (`references/lyrics-integration.md`)
  - Porting a feature or client module FROM another open-source repo ("integrate X like repo Y
    does it"), especially when the source is copyleft — licence decision, version-compat gate,
    seam mapping, and per-layer compile (`references/porting-from-reference-repo.md`)
  - Fixing spurious playback/search error messages that appear while the track plays fine, a track
    that plays twice, or adding loading skeletons to a list (`references/media3-playback-service.md`)
  - A screen shows a false empty/zero state on open ("no music yet", "0 songs", "no playlists",
    a switch that flips on its own), or you are adding loading skeletons / retry buttons / empty
    states to a Compose list backed by Room (`references/compose-loading-state.md`)
  - Adding a listening-stats screen (play counts, top songs, minutes listened), or fixing a 403 on
    a stream URL that is still valid (`references/media3-playback-service.md`,
    `references/streaming-extractor-integration.md`)
  - Persisting the playback queue / position across app restarts, or adding a sleep timer
    (`references/media3-playback-service.md`)
  - A user reports a force close / crash on a screen, with no device attached and no logcat
    (regression check, candidate causes, duplicate lazy-list keys, class-loading probes, AND building
    an in-app crash recorder so the next crash names its own class and line —
    `references/headless-crash-triage.md`)
  - A 403 / "forbidden" on a streamed track, a User-Agent that must match between extraction and
    playback, or a `Downloader` bridge that never sets a UA
    (`references/streaming-extractor-integration.md`)
  - Bumping the Compose BOM or a single androidx artifact, or judging whether a newer library
    version is reachable at all (`references/dependency-version-upgrade.md`)
  - The user says the app feels heavy / slow / laggy, or you are setting up a release build
    (minify, baseline profile, image decode size, upgrading in place without a reinstall)
    (`references/app-performance-and-release-build.md`)
  - Adding or changing motion/animation in a Compose app that has a `docs/design-spec.md` motion
    contract (artwork crossfade on track change, press feedback, screen transitions), or a numeric
    design rule that should be enforced by a unit test (`references/compose-motion-design-contract.md`)
  - Letting the user choose stream quality / bitrate, or any setting that governs streamed tracks
    but not local files (`references/streaming-extractor-integration.md`)
  - Search returns only songs — albums/artists are missing — or a search/list screen shows only the
    first page (`references/streaming-extractor-integration.md`)
  - The "next" button does nothing (sometimes), or a queue built from a filtered list plays only one
    track (`references/streaming-extractor-integration.md`)
  - Deriving UI colors from the playing track's cover art (the Apple-Music look), or any "read the
    pixels of an image" work (`references/artwork-derived-theming.md`)
  - User asks to "remove / disable the dynamic theme" or "turn off dynamic colors" — identify WHICH
    dynamic thing they mean before deleting anything; Material You is usually already absent and the
    themed launcher icon is usually the real one (`references/artwork-derived-theming.md`)
  - Making streamed tracks playable offline / adding a "download" button (one track, a whole album,
    a whole playlist) — WorkManager worker, saving into the public Music folder via MediaStore,
    per-track progress, and the two integration points that decide whether it works at all
    (`references/offline-download-media-store.md`)
  - A download fails with a raw platform message naming a container ("Unsupported MIME type
    audio/webm"), or you are choosing which stream to save as opposed to which to play
    (`references/offline-download-media-store.md`)
  - Building an app for Android AND iOS from one codebase (Kotlin Multiplatform + Compose
    Multiplatform), or answering "why not full native Kotlin / why RN?" for a POS-style app
    (`references/kotlin-multiplatform-scaffold.md`)
  - Storing an auth token securely on Android without the deprecated
    `androidx.security:security-crypto`, or writing iOS Keychain interop in Kotlin/Native
    (`references/kotlin-multiplatform-scaffold.md`)
  - Auto-detecting an incoming QRIS/bank transfer by reading the bank app's notification
    (Android `NotificationListenerService`, the three-part service+bus+listener pattern, the
    manifest declaration that decides whether the feature exists, the Settings-only permission and
    its banner, and the parser ordering rule that stops legitimate payments being rejected —
    `references/bank-notification-payment-detection.md`)
---

# Android / Kotlin CLI Build on a Headless Host

Building Android/Kotlin apps without Android Studio. The IDE and emulator are impossible on a
headless VPS; the CLI toolchain is not. Answer capability questions with the triage table first,
then set up only what the task needs.

## 0. Capability triage — answer this before installing anything

Check the host, then state plainly what works:

```bash
java -version; javac -version          # JDK present?
echo "DISPLAY=$DISPLAY"; ls /tmp/.X11-unix 2>/dev/null   # GUI possible?
ls -la /dev/kvm 2>/dev/null            # emulator possible?
free -h; nproc; df -h /
```

| Task | Headless VPS | Why |
|------|--------------|-----|
| Write + compile Kotlin (JVM/lib/CLI) | ✅ | Pure CLI, JDK + kotlinc |
| Build APK/AAB from CLI | ✅ | Gradle + Android SDK, no GUI needed |
| Kotlin/JS, Kotlin/WASM | ✅ | `kotlinc-js`, `kotlinc-wasm` ship with kotlinc |
| Inspect APK (badging, dex) | ✅ | `aapt2`, `apkanalyzer` from build-tools |
| `adb install` to a real device | ✅ | If a device is attached over USB/TCP |
| **Android Studio (GUI IDE)** | ❌ | Needs a display server — `DISPLAY` empty on a server |
| **Android emulator** | ❌ | Needs `/dev/kvm` (hardware virtualization) — absent on most VPS |

The honest recommendation: author and compile here, then build/run in a local Android Studio,
or hand the artifact to a device. Do not promise an emulator.

## 1. Install the Kotlin compiler (standalone)

Do not use the distro package — `apt` Kotlin lags years behind (e.g. 1.3.31). Pull the current
release from GitHub:

```bash
VER=$(curl -s https://api.github.com/repos/JetBrains/kotlin/releases/latest \
      | grep -oP '"tag_name":\s*"v\K[^"]+' | head -1)
curl -sL -o /tmp/kotlin.zip \
  "https://github.com/JetBrains/kotlin/releases/download/v${VER}/kotlin-compiler-${VER}.zip"
mkdir -p ~/kotlin && unzip -q -o /tmp/kotlin.zip -d ~/kotlin && rm -f /tmp/kotlin.zip
~/kotlin/kotlinc/bin/kotlinc -version   # verify
```

Compile and run a JVM program:

```bash
~/kotlin/kotlinc/bin/kotlinc App.kt -include-runtime -d app.jar
java -jar app.jar
```

## 2. Install the Android SDK (headless)

**Install the SDK into a user-writable dir, not `/usr/lib/android-sdk`.** A distro-installed SDK
is root-owned, so `sdkmanager` cannot write new packages into it without `sudo` on every call.
Point `--sdk_root` at `~/android-sdk` instead. (If no `sdkmanager` exists yet, download Google's
command-line tools and place them at `<sdk>/cmdline-tools/latest/` — the directory name `latest`
is required.)

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME=$HOME/android-sdk
SDKM=<path-to>/cmdline-tools/latest/bin/sdkmanager

# Accept licenses once (non-interactive)
yes | $SDKM --sdk_root=$ANDROID_HOME --licenses >/dev/null 2>&1

# Install the minimum for an APK build: platform + build-tools + platform-tools
$SDKM --sdk_root=$ANDROID_HOME "platform-tools" "platforms;android-35" "build-tools;35.0.1"
```

List what is available before choosing versions: `$SDKM --sdk_root=$ANDROID_HOME --list`.
`platforms/` is the package people forget — without it Gradle fails on `compileSdk`.
A minimal SDK (~platform + build-tools + platform-tools) is only ~300–500 MB.

## 3. Install Gradle (or use a project wrapper)

Use the project's `gradlew` when it exists — it pins the right Gradle version. Otherwise fetch one:

```bash
curl -sL -o /tmp/gradle.zip https://services.gradle.org/distributions/gradle-8.11.1-bin.zip
unzip -q -o /tmp/gradle.zip -d ~/ && rm -f /tmp/gradle.zip
~/gradle-8.11.1/bin/gradle --version
```

## 4. Tune Gradle for a low-RAM host

The single biggest cause of a killed build on a small VPS is the JVM heap default. Cap it in the
project's `gradle.properties`:

```properties
org.gradle.jvmargs=-Xmx1024m -XX:MaxMetaspaceSize=384m
org.gradle.daemon=false
org.gradle.parallel=false
kotlin.daemon.jvmargs=-Xmx768m
android.useAndroidX=true
android.nonTransitiveRClass=true
```

`org.gradle.daemon=false` avoids a lingering daemon eating RAM between builds;
`org.gradle.parallel=false` keeps one module's compile from competing for the 2 cores.
A minimal app still takes ~3–4 minutes on 2 vCPU / 4 GB — that is normal, not a hang.

**A full Compose + Hilt + Room + KSP project DOES build on a ~4 GB DEDICATED host — slow,
not impossible.** Measured: **7m 45s** first build, **2m 26s** warm. **If `AGENTS.md`
forbids local builds (shared prod host), that rule WINS — do not build even if the host meets
the RAM bar.** Profile that worked:

```properties
org.gradle.jvmargs=-Xmx1536m -XX:MaxMetaspaceSize=512m -Dfile.encoding=UTF-8
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configuration-cache=true
kotlin.daemon.jvmargs=-Xmx1024m
```

`daemon=true` + `caching=true` is what buys the ~3× rebuild speedup on a project you will
build repeatedly; use `daemon=false` only for a genuine one-shot build where you want the RAM
back afterwards. An OOM kill is the signal to lower `-Xmx`, not to give up on the host — **unless the project's
`AGENTS.md` forbids local builds entirely, in which case the OOM kill is proof the rule was right,
not a tuning opportunity. Re-read the project rule; do not tune around it.**

**On a SHARED production host the daemon is a hazard, not just a cache — stop it when the build
finishes.** A Gradle daemon defaults to `idleTimeout=10800000` (**3 hours**), so every build leaves
~1.5 GB parked for three hours; a session that builds five times holds several daemons' worth of
memory with no build even running. Check before and after, and stop BOTH JVMs:

```bash
free -m                        # require ~1.5 GB available before starting
./gradlew --stop               # after EVERY build, not just at session end
pkill -f KotlinCompileDaemon   # the Kotlin daemon is a separate JVM (~1 GB)
```

Measured failure: on a 3.7 GB VPS that also runs nginx, docker, mariadb and PM2, a Gradle daemon
(1.6 GB) + Kotlin daemon (~1 GB) + those services (~1.5 GB) exceeded RAM. Swap filled, the kernel
could not reclaim, and the host **hung hard and was force-rebooted from the provider panel**,
taking every co-hosted project down. `./gradlew --stop` then returned **1.7 GB instantly**. Budget
heap + metaspace + `kotlin.daemon.jvmargs` against the host's *available* RAM, not its total, and
do not run `assembleRelease` (R8 loads the whole app) while other heavy jobs are live. Swap
absorbing the overflow is NOT acceptable on a shared host — that assumption is what caused the
outage.

Route to CI anyway when the build is the *deliverable* (you want a shareable APK artifact rather
than a local check) — a `ubuntu-latest` runner has ~7 GB RAM and 4 cores for free:

```yaml
# .github/workflows/build.yml — build off-box, download the APK artifact
- uses: actions/setup-java@v4
  with: { distribution: temurin, java-version: 17 }
- run: chmod +x gradlew && ./gradlew assembleDebug
- uses: actions/upload-artifact@v4
  with: { name: apk, path: app/build/outputs/apk/debug/*.apk }
```

Tell the user which path you are taking and why — the RAM budget, not preference, decides.

## 5. Build the APK

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME=$HOME/android-sdk
cd <project>
~/gradle-8.11.1/bin/gradle :app:assembleDebug --no-daemon --console=plain
# or, with a wrapper:  ./gradlew :app:assembleDebug
```

The project needs `local.properties` with `sdk.dir=<absolute path to ANDROID_HOME>` (or
`ANDROID_HOME` exported — Gradle reads either).

For a from-scratch project, run `scripts/scaffold-minimal-android-app.sh <outdir> <package>` to
generate a known-good minimal app (manifest + Kotlin activity + Gradle files) that builds an APK.

For a **real** project (version catalog, Compose theme, Hilt, Room, KSP, adaptive icon, CI) rather
than a minimal one, follow `references/compose-hilt-project-scaffold.md` — it records the exact
configuration that built successfully headless, plus the Room schema-export and font-bundling steps.

For the app layer on top of that skeleton — Media3 playback service, controller pattern, manifest
permissions, MediaStore scanning, Room migrations — see `references/media3-playback-service.md`.
For user-picked folders outside the system index (SAF: persistable grants, `DocumentFile` walk,
`MediaMetadataRetriever`, de-duplication) see `references/saf-custom-folder-scanning.md`.
For streaming (external extractors such as NewPipe, YouTube Music search/resolve, expiring stream
URLs, the datacenter-IP verification wall) see `references/streaming-extractor-integration.md`.
For a user-reported force close with no device attached and no logcat (regression check, the
`Error`-not-`Exception` candidate list, class-loading and dex-vs-android.jar probes, and what a
honest report looks like) see `references/headless-crash-triage.md`.
For an in-app update prompt on a sideloaded APK (static `update.json`, version comparison,
throttling, opening the download) see `references/sideloaded-app-update-checker.md`.
For lyrics from a third-party API (LRCLIB two-step lookup, LRC parsing rules, why a secondary
feature must never surface its failures) see `references/lyrics-integration.md`.
For porting a feature or client module from another open-source Android repo (the licence fork and
what adopting copyleft obliges, the Kotlin/AGP version-compat gate that can make a verbatim port
impossible, mapping the target's existing seams so the port shrinks, extracting it as a pure JVM
module, and the constant/mechanism parity sweep that catches what the port silently omitted) see
`references/porting-from-reference-repo.md`.
For bumping the Compose BOM or one androidx artifact (why the BOM version is not the library
version, the `aar-metadata.properties` + POM pre-flight that predicts the cost before you edit
anything, scanning a version series for the cheapest usable alpha, the one-file compile probe that
is the ONLY way to confirm an API is reachable, why the gate is the full lint+assemble+test
command, and metaspace-vs-heap when the daemon dies) see `references/dependency-version-upgrade.md`.
For a listening-stats screen (range selector, minimum-listen threshold, hour/weekday buckets,
timezone-correct `strftime`, plotting time vs play count) see the stats section of
`references/media3-playback-service.md`, and verify the aggregates with
`scripts/verify-dao-queries.py` — it runs the DAO's own SQL against a throwaway SQLite database.
For album/artist grouping (a stable identity key instead of `GROUP BY` on the display name, the
`albumArtist`-in-the-key rule for compilations, keeping untagged songs in a "no album" bucket
instead of filtering them away, release-type-as-inference, and deriving the verification fixture's
schema from the exported `*.json` rather than retyping it) see the same
`references/media3-playback-service.md`.
For a user-reported "the app feels heavy / slow / laggy" (check the shipped APK's build type FIRST,
then R8 keep rules, baseline profile, and image decode size) see
`references/app-performance-and-release-build.md`.
For adding or changing motion against a numeric design-spec contract (spec durations are targets
routed through ONE shared motion object, not literals pasted per call site; enforcing a numeric
rule with a unit test; the artwork-crossfade-on-track-change recipe and why
`AsyncImage.crossfade(true)` is a different feature) see
`references/compose-motion-design-contract.md`.
For a screen that renders a false empty/zero state on open, and for the whole loading/empty/error
model behind it (`Loadable` Loading/Ready/Failed, the `asLoadable` wrapper and its operator order,
retry via re-subscription, `Loadable`-taking shared composables, one-clock shimmer skeletons) see
`references/compose-loading-state.md`.
For taking colors from the playing track's cover art (scoping it to the Now Playing layer instead of
a repo-wide theme refactor, keeping the palette rules pure and unit-tested, the
`allowHardware(false)`-or-`getPixels()`-crashes trap, the absent-vs-null cache and HashMap-tie-break
traps, and verifying the Coil/androidx API from the POM and bytecode) see
`references/artwork-derived-theming.md`.
For downloading streamed tracks for offline playback (the `CoroutineWorker`-in-`work-runtime` and
`EntryPointAccessors`-in-`dagger.hilt.android` artifact facts, the Hilt-without-`@HiltWorker`
EntryPoint route, writing into the public Music folder via MediaStore with `IS_PENDING`, the pure
filename rule, sharing the playback request headers so the download is not 403'd, and the two
one-line mistakes that leave the feature useless — playback not checking `isDownloaded` first, and
the scanner re-indexing the download folder as duplicate rows — plus why the download path must
choose a DIFFERENT stream from playback: `MediaStore` rejects a container it cannot name
(`Unsupported MIME type audio/webm`), so "highest bitrate" picks the one track that can never be
written) see `references/offline-download-media-store.md`.

For a Kotlin Multiplatform project (Android + iOS from one codebase) — the stack-choice argument
that leads with the hard platform limit rather than preference, the CMP→AGP→Gradle→compileSdk
coupling chain that decides which CMP version is even resolvable, the `iosX64` target removal that
aborts dependency resolution for the whole project, the KMP compile traps (`inline` public + `private` callee,
`maxOf(Long, Int)`, removed `surfaceVariant`), Android Keystore storage because
`androidx.security:security-crypto` is deprecated, the iOS Keychain `CFDictionaryCreate`
interop that cannot be guessed, and the Ktor-in-`commonMain` generic-wrapper trap that erases the
body type and breaks every request at runtime (`setBody(body, typeInfo<B>())`, no raw `mapOf`
bodies, plus reading a library's `-sources.jar` to disambiguate overloads) — see
`references/kotlin-multiplatform-scaffold.md`.

For auto-detecting an incoming bank/QRIS payment from the bank app's notification (the
service+bus+listener split forced by `NotificationListenerService` not being constructible from app
code, the manifest `<service>` whose absence makes the feature fail silently, the Settings-only
permission plus the banner that keeps it from failing silently, the parser ordering rule where an
ambiguous "money out" keyword rejects legitimate incoming payments, forwarding numbers not
`rawText`, the package allowlist that rots on rebrand, and the `rememberCoroutineScope`-not-
`MainScope` subscription) see `references/bank-notification-payment-detection.md`.

### Build in small compile-checked steps, not one giant write

A full feature layer is many files; writing them all and then building means a long wait before you
learn anything, and a single typo invalidates the whole run. Compile per layer instead — it is fast
because dependencies are already cached:

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME=$HOME/android-sdk
export PATH=$JAVA_HOME/bin:$PATH
./gradlew :app:compileDebugKotlin --console=plain 2>&1 | grep -E "^e:|FAILURE|BUILD"
```

`compileDebugKotlin` (not `assembleDebug`) is the cheap gate — ~20 s warm, and it catches every
Kotlin error before you spend minutes on DEX + packaging. Finish each layer (data, then playback,
then UI) with a green compile before starting the next.

**Standalone `kotlinc` is NOT the project compiler — a green run there does not mean the build
passes.** A throwaway harness compiled with `~/kotlin/kotlinc/bin/kotlinc` uses its own default
language settings, which are more permissive than the flags Gradle applies. A pure-logic parser
that passed 31/31 assertions in a standalone harness still failed the real build with
`error: The feature "break continue in inline lambdas" is experimental and should be enabled
explicitly` — caused by a `continue` inside a `?.let {}` lambda. Treat a standalone run as a
logic check only, then always run the project's `:app:compileDebugKotlin` before calling the work
verified; reporting "tested and passing" off the harness alone is a false claim. Avoid
`continue`/`break` inside lambdas altogether — restructure to `if`/`else`, which compiles under
every configuration and reads better.

**Two labelled-control-flow traps compile clean and do the wrong thing silently — check both by
reading, because no gate will.** First: **`return@repeat` / `return@forEach` is `continue`, not
`break`.** A pagination loop written as `repeat(200) { if (page.isEmpty()) return@repeat }` keeps
iterating — it fires 200 API calls after the data ran out instead of stopping at the first empty
page, and the loop looks correct. Use `while (true) { … break }` for an early exit; a labelled
return can only skip the current iteration. Second: **adding a branch to a `when` that already has an
`else ->` makes the new branch unreachable, with no warning.** A new tab/case inserted before an
existing catch-all (or a numbered `4 ->` placed after `else ->`) is dead code — the feature simply
never appears, and the compiler stays silent. When adding a case, read the whole `when` and put it
before any catch-all, or narrow the catch-all to the values it actually means. Third: **inserting a tab into a `when (selectedTab)` of bare indices silently shifts every
downstream index** — all compile, but tab N renders tab N-1's content. Prefer keying on a tab
enum/object, or renumber every branch in the SAME edit.

**A whole feature written in one batch is the failure this rule exists to prevent.** Writing ten
files and only then compiling means: you cannot tell which of them is wrong, one typo hides the
next, and if the session ends first (iteration cap, context limit, user stops you) you hand over
code with *zero* compile signal — nothing verified, nothing usable, and any bug you spotted while
writing still unfixed. Compile after each file or small group, and never end a turn with a known
error left in place; fix it or revert it before reporting. If you are running low on budget, stop
writing new files and spend what remains on making what exists compile.

**Commit at every green gate — an uncommitted green tree is work the next turn may have to redo.**
A multi-file refactor reliably spans more than one turn, and the iteration cap lands mid-way. The
difference between the two ways to be interrupted is large: a tree that compiles, passes lint and
unit tests, and is **committed** is a safe checkpoint the next turn builds on; the same tree
uncommitted is fragile (one bad patch away from losing it, and `git checkout` is not something you
want to need), while a tree that does not compile is worse still. So once a gate goes green, commit
before starting the next layer — small, self-contained commits per coherent step rather than one
large commit at the end. Then, when the budget runs out, stop at a state that is either committed
or trivially revertible, and say plainly in the handoff which files are uncommitted and what state
they are in. Also expect to be interrupted at a moment when a *sweep* is half done (three of seven
instances fixed): finish the current file's fix, get it green, commit, and list the remaining known
instances by name so the next turn resumes instead of re-discovering them.

**When the host is forbidden to build, CI is the ONLY compile gate — so push early rather than
sitting on unverified code.** A project can carry a standing rule that Gradle must not run on the
shared box (the daemon OOMs it and takes co-hosted services down), which removes
`compileDebugKotlin` from your reach entirely. **Read the project's canonical doc for that rule
BEFORE the first Gradle call — a stale note in your own memory that says "build with ./gradlew" does
not override the project's own rule, and a warm dependency cache makes the forbidden build SUCCEED,
which is exactly what makes it tempting.** A green build on a host that forbids building is luck,
not permission: it risks the co-hosted services, and the honest report names the rule and says you
violated it rather than presenting the green build as normal. In that setup the local "compile after
each step" loop is impossible, and the substitute is: write in small coherent batches, commit each one, and
**push to a branch / open the PR as soon as the first batch is coherent** so the runner compiles
it. Do not finish all the files and only then think about pushing — the compiler is remote now, and
every unpushed batch is a batch with zero signal. Expect the first CI run to fail on type errors
that no amount of reading or SQL/fixture testing could surface (a non-`Comparable` sort key, a
missing callback parameter); that is the gate doing its job, not a mistake in the approach.

**Confirm a CI run actually STARTED — creating the repo can put your commit on a branch the
workflow does not watch.** `gh repo create <name> --source . --push` pushes to **`master`** by
default, while the workflow's `on: push: branches: [main]` watches `main` only — so the push
succeeds, the repo looks correct, and **no run is ever queued**: the "remote compiler" you are
relying on silently does not exist, and every later batch is written against zero signal. Check
`gh run list --limit 5` immediately after the first push; an empty list means fix the branch, not the
code. Rename and re-point in one go — `git branch -m master main && git push -u origin main`, then
`gh repo edit --default-branch main`, then delete the stale remote branch — and re-confirm a run
appears.

**Reading CI back: poll the run, and prove the test count from the uploaded report — a green
checkmark is not a count.** `gh run watch` blocks until the run finishes and routinely outlives the
tool's own timeout, so a run that is actually progressing reads as a hang. Poll with a bounded loop
instead, and stop the moment the status is `completed`:

```bash
for i in $(seq 12); do
  s=$(gh run view <id> --json status,conclusion -q '.status + " " + (.conclusion // "-")')
  echo "$i $s"; case "$s" in completed*) break;; esac; sleep 30
done
gh run view <id> --json jobs -q '.jobs[] | "\(.name)\t\(.status)\t\(.conclusion)"'
```

**Merging and then bumping the version puts TWO runs on `main` — ship the artifact from the BUMP
commit's run, not the first green one.** The merge push triggers a run, and the version-bump push
seconds later triggers a second; both go green and both upload an APK, but the earlier one was built
from the pre-bump tree, so downloading its artifact publishes the OLD `versionCode` under the new
file name. Resolve the run by commit (`gh run list --branch main --limit 5`, or
`gh run view <id> --json headSha`) and confirm the downloaded APK's `versionCode`/`versionName`
match the bump before running the release script. A green run is not necessarily the right run.

When the host is forbidden to build, the local `app/build/test-results/.../*.xml` never exists, so
the pass count has to come from the CI artifact. Download it from inside the repo (the command needs
git context; `--dir` chooses the destination). **Check what the artifact actually contains before
choosing a parser** — workflows commonly upload Gradle's HTML report (`classes/<fqcn>.html`, one file
per test class, each carrying `N tests` / `N failures` / `N ignored`) rather than JUnit XML. A regex
run straight against that markup matches nothing and reports `tests=0`, which reads as "every test
vanished" and sends you hunting a collection failure that does not exist. Strip the tags first (or
use an XML parser only when the artifact is genuinely XML):

```bash
gh run download <id> -n <test-report-artifact> --dir /tmp/ci-tests
```

Confirm the specific test classes you added appear with `failures=0 errors=0 skipped=0` — that is the
evidence the new code was genuinely compiled and executed, which a green "Unit test" job alone does
not give you. List what a run uploaded with `gh api /repos/{owner}/{repo}/actions/runs/<id>/artifacts`
(or `gh run download <id>` with no `-n` to take them all) — `gh run view --json artifacts` is not a
valid field and errors out, which is easy to misread as "this run uploaded nothing".

**And never report such work as "done" or "working" — say plainly what was never compiled.**
When the code has not been through any compiler, the honest handoff is: files written, nothing
verified, CI not yet run, and here is what I would expect CI to catch. A feature described as
finished when it has never been compiled is the failure this whole section exists to prevent;
"I wrote it and it is probably right" is not a status, and the user cannot tell the difference
from the outside.

**Changing the shape of an EXISTING shared symbol: find every reference first, then edit once.**
Widening or renaming a field used across a class (`pending: (() -> Unit)?` → a list, a changed
signature, a moved helper) is the same hazard in a sharper form: the moment the declaration changes,
the tree no longer compiles, and hunting the call sites one tool call at a time is how you run out
of budget holding a broken build. Grep the whole reference set up front, then make the declaration
change and every call-site change together in one pass:

```bash
grep -rn '\bpending\b' app/src/main/kotlin/   # do this BEFORE touching the declaration
```

**Adding a method to an interface is the same edit seen from the other side — and the implementers
include fakes in the test tree.** Every `: Repository` implementation, hand-rolled or generated,
must gain the member in the same pass or the whole test source set stops compiling. Grep for them
before widening the interface (`grep -rn ': MusicRepository\b\|override fun <aMethodYouKnow>' app/src/`);
a hand-rolled mock that reimplements the old shape fails on a shard you did not run. If exactly one
real implementation exists and no fake exists, say so in the report and proceed — that check is one
call and it converts "I hope nothing else implements this" into a fact.

If the budget is nearly gone, prefer leaving the old shape intact over half-migrating it — a
working single-slot field is better than a half-renamed one, and the improvement can land next turn.

**Renaming or deleting a file is the same hazard with no compiler pointing at the cause: a type
used across the tree can be left with no definition at all.** Swapping a file for a differently
named one drops the declaration several other files still import, so the tree stops compiling with
errors that name the *users*, never the removal. After any rename/removal,
`grep -rn '<TypeName>' --include='*.kt' .` and confirm a definition exists (`data class X`,
`class X`), not just call sites. Also check a moved declaration did not leave a duplicate: two
definitions of the same name is the mirror failure.

## 6. Verify the artifact — do not trust BUILD SUCCESSFUL alone

```bash
APK=app/build/outputs/apk/debug/app-debug.apk
BT=$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)   # resolve it; do NOT hardcode a version
ls -lh "$APK"
"$BT/aapt2" dump badging "$APK" | head
unzip -l "$APK" | grep -E 'classes.dex|AndroidManifest'
```

Confirm `package:`/`minSdkVersion`/`launchable-activity` in the badging output and that
`classes.dex` exists — that is proof the Kotlin compiled through to DEX, which a bare
"BUILD SUCCESSFUL" does not show.

### Run lint as a gate, not just assemble

Lint errors abort the build (`lintDebug` fails, not warns), so a green `assembleDebug` alone does
not mean CI will pass. Gate on both:

```bash
./gradlew :app:lintDebug :app:assembleDebug --console=plain
```

Triage the report by category instead of reading all of it — on a fresh Compose project expect
~80 warnings that are almost all "a newer dependency version exists" noise:

```bash
grep -E "^[0-9]+ error" app/build/reports/lint-results-debug.txt
grep -oE "\[[A-Za-z]+\]$" app/build/reports/lint-results-debug.txt | sort | uniq -c | sort -rn
grep -E "^/.*Warning" app/build/reports/lint-results-debug.txt \
  | grep -vE "AndroidGradlePluginVersion|GradleDependency"   # real warnings only
```

Fix real findings (opt-in violations, exported components, hardcoded strings); do not chase version
warnings — and never silence a finding with a lint baseline when the underlying issue is fixable.

### Verify the shipped APK's signature and its baked-in URLs

Two failures that surface only in the field, after the artifact is already in users' hands.

**1. Signature must match the previous release.** A debug APK signed by a different key cannot be
installed over the old one; the install is rejected and the user must uninstall first, losing app
data. Android Studio and CI each generate a *random* debug keystore per machine/run unless the
project pins one, so "it installed fine locally" proves nothing.

```bash
BT=$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)
"$BT/apksigner" verify --print-certs app/build/outputs/apk/debug/app-debug.apk | grep 'SHA-256'
# Run this against EVERY published version — the digests must be identical.
```

Fix at the source: commit a fixed `debug.keystore` and point `signingConfigs.debug` at it
(`storeFile = rootProject.file("debug.keystore")`), with `*.keystore` ignored but
`!debug.keystore` re-included. A debug key is not a secret — it only enables sideload upgrades.

**2. URLs compiled into the app are immutable once shipped.** Grep the DEX, not the source, because
only the DEX is what the device runs:

```bash
rm -rf /tmp/dexchk && mkdir -p /tmp/dexchk
unzip -oq app/build/outputs/apk/debug/app-debug.apk 'classes*.dex' -d /tmp/dexchk
for f in /tmp/dexchk/classes*.dex; do strings -a "$f"; done \
  | grep -oE 'https://[a-z.]+' | sort -u
```

When a hostname moves, run this against the **old published APK too** — it is the evidence that the
"one manual install required" warning is real rather than assumed. A URL baked into an installed
APK cannot be fixed remotely: the update mechanism itself is what points at the dead host.

**3. The served manifest must match the client's parsing model.** After deploying, diff the live
JSON's field names and types against the app's deserialization class (`UpdateManifest`); a renamed
or retyped field parses to a failure the user sees as "update check failed". Also assert the served
`versionCode` is strictly greater than the version already installed, or the update is never offered.
**Dump the whole object first (`curl -s <url> | python3 -m json.tool`) before writing a check that
reads a named field.** A verification one-liner that queries a field you assumed exists
(`d.get('checksum')`) prints the same nothing as a genuinely missing field, so an invented key reads
as "the deployment is broken" and sends you re-running the release. Read the real shape from the
live document, then assert against the names it actually has.

## Pitfalls

- **`du -sh` under-reports SDK/Docker size for root-owned paths** — drill root-owned dirs with
  `sudo du`. (Same class of trap as `/var/lib/docker`.)
- **`sdkmanager` writes need a writable `--sdk_root`** — a root-owned distro SDK forces `sudo`
  on every install; use a user dir.
- **`apt install kotlin` is ancient** — always take the GitHub release.
- **Missing `platforms/` package** — `build-tools` alone is not enough; Gradle fails on `compileSdk`.
- **Size the Gradle heap to what the host can actually give, and treat an OOM as a tuning
  signal, not a verdict** — a minimal app is happy at `-Xmx1024m`, a Compose + Hilt + KSP build
  was measured working at `-Xmx1536m` on a 3.6 GB host. Lower `-Xmx` when you get an OOM kill;
  do not conclude the host cannot build the project at all.
- **A heavy (Compose + Hilt + KSP) build is slow on a small host, not impossible** — measured
  ~8 min cold / ~2.5 min warm on 2 vCPU / 3.6 GB. Do not refuse the build or assume OOM; try it.
- **Room rejects `@Database(entities = [])`** — KSP fails with "must specify list of entities".
  A placeholder empty database will not compile. Start with at least one real entity (the schema
  you actually need) rather than a dummy.
- **Verify dependency versions against the RIGHT Maven repo before writing build files** — androidx
  artifacts (compose, room, media3, activity, navigation, datastore) live on **Google's Maven**
  (`https://dl.google.com/dl/android/maven2/<group-path>/<artifact>/<ver>/<artifact>-<ver>.pom`),
  not Maven Central. Probing `repo1.maven.org` for androidx returns 404 and yields a false
  "version does not exist". AGP is on Google Maven too; Kotlin/KSP/Hilt/kotlinx/Coil are on
  Maven Central. One HTTP HEAD per candidate version is enough to lock a version catalog before
  the first build.
- **A Compose BOM's version is NOT the library's version — read the mapping before quoting one.**
  `composeBom = "2024.12.01"` resolved to material3 **1.3.1**, not 1.4.0. The two numbers look
  interchangeable and are not, so a plan (or a message to the user) built on "we're on 1.4.0"
  starts from a version that was never in the build. Read the mapping from the BOM's own POM:
  `https://dl.google.com/dl/android/maven2/androidx/compose/compose-bom/<bom>/compose-bom-<bom>.pom`,
  grep `<artifactId>material3</artifactId>`. To find which BOM first carries a target artifact
  version, probe candidate BOMs — the answer is usually older than the newest BOM.
- **A dependency bump is not verified by `compileDebugKotlin` — androidx ships its own lint
  detectors, and a detector built against a newer Kotlin Analysis API than AGP's lint crashes the
  lint task with `IncompatibleClassChangeError` while the compile stays green.** Gate every bump on
  the project's full release command (`:app:lintDebug :app:assembleDebug :app:testDebugUnitTest`),
  not on a compile check. A bump that gains nothing and breaks lint is a net loss — revert it
  rather than adding a lint baseline to work around it. Procedure and the pre-flight that predicts
  the cost up front: `references/dependency-version-upgrade.md`.
- **An option you offer the user is a claim — verify each branch before presenting the menu.**
  A version bump is usually presented as "here are your choices", and the user then decides on the
  premise that each one is possible. When a branch rests on bytecode inspection, an unread
  requirement, or an unrun command, it is a guess sitting beside a fact with nothing marking the
  difference. Label untested branches as untested **in the option text**; if you discover afterwards
  that a branch was never viable, lead the next message with that correction, because the user's
  decision was made on a false premise and they may need to re-decide. **Also disclose the risk the
  option carries, not just its feasibility.** A "release now" option is a claim about quality: when
  the previous release has never been installed on a device, shipping on top of it stacks two
  untested versions and the user only learns that after installing — put that in the option text so
  they can choose to test first. Same rule for a constraint
  you stated earlier ("this needs a full toolchain upgrade") that later turns out false: it is a
  plan-invalidating surprise, not a footnote. See `references/dependency-version-upgrade.md`.
- **An error string the user reports that you cannot find in your own source came from the
  PLATFORM — grep your tree to establish that, then read the platform's throwing line before
  fixing.** `grep -rn 'Unsupported MIME' app/src/` returning nothing is a positive finding: the
  message is thrown by the framework, not by a bug in your string handling. Confirm the exact
  source line (AOSP source is fetchable: `curl -sL 'https://android.googlesource.com/...?format=TEXT'
  | base64 -d`) and mirror its own check in your code, rather than inventing an allowlist that can
  drift from what the platform actually accepts. Guessing at a platform rule from the message text
  alone is how you "fix" a symptom that recurs on a sibling container.
- **A rule used for two different jobs is the bug, not the value.** When one selection/validation
  rule feeds two callers with different requirements (which stream to PLAY vs which to SAVE, which
  field to DISPLAY vs which to PERSIST), the shared rule is correct for one and wrong for the
  other, and the failure surfaces only on the caller you did not think about. Keep the shared
  inner rule and add a filter for the stricter caller, rather than writing a second copy of the
  rule — two copies drift and the drift is invisible until a user hits it.
- **Do not narrow the version search to the newest release and declare the requirement unmeetable.**
  A single probe of the latest version is a sample, not a survey: declared requirements step rather
  than slide across a series, so walking backwards often finds a version that needs nothing. In this
  session `1.5.0-alpha28` demanded compileSdk 37 + AGP 9.1 + Kotlin 2.1.20, and the same feature was
  reachable at `alpha12` with zero toolchain change. Scan the series before telling the user a
  feature costs a migration.
- **"Newest of every dependency" is not a coherent set — the requirement propagates as a CHAIN, so
  bumping the top one silently obliges you to bump all of them.** A Compose Multiplatform release
  bundles a specific Jetpack UI, whose AAR declares `minCompileSdk` + `minAndroidGradlePluginVersion`,
  and that AGP declares a minimum Gradle: CMP → AGP → Gradle → compileSdk. Aligning each artifact to
  its own latest release therefore lands the project on the most expensive possible combination and
  reads as "these libraries are broken" when CI rejects it (`requires AGP 9.1.0 or higher`). Prefer
  the newest version of the OUTERMOST framework that still fits the toolchain you already have, and
  read each framework's release-notes dependency table rather than each artifact's own newest tag.
  A project that has never been compiled is the worst place to discover this, because the failure is
  a resolution error with no relationship to your code.
- **A bigger dependency set can exhaust METASPACE while the heap is fine.** Gradle's "daemon
  disappeared unexpectedly" together with the log line "The Daemon will expire after the build
  after running out of JVM Metaspace" is a metaspace limit, not an `-Xmx` limit — metaspace holds
  class metadata, so a dependency adding many classes (plus its own lint detector) grows it
  directly and heap tuning does nothing. Raise `-XX:MaxMetaspaceSize` in `org.gradle.jvmargs` and
  check `gradle.properties` for a cap sized for the previous, smaller dependency set. On a low-RAM
  host, budget heap + metaspace + `kotlin.daemon.jvmargs` together before raising any one.
- **Do not hand-copy a `gradle-wrapper.jar` out of a Gradle distribution** — the jar at
  `lib/plugins/gradle-wrapper-main-*.jar` is NOT the wrapper jar and will not run. Prefer
  `gradle wrapper --gradle-version <ver> --distribution-type bin`. **When you cannot run Gradle at
  all** (the host forbids it, or the system `gradle -v` reports something ancient like 4.4.1 that
  cannot generate an 8.x wrapper), fetch the three official files from the Gradle repo **tag**
  instead — `gradlew`, `gradlew.bat`, `gradle/wrapper/gradle-wrapper.jar` from
  `https://raw.githubusercontent.com/gradle/gradle/v<tag>/…` — `chmod +x gradlew`, and write
  `gradle-wrapper.properties` with the distribution URL plus its `distributionSha256Sum` (the
  checksum makes a swapped distribution fail the build instead of running silently). **Verify the jar
  is real before trusting it:** `unzip -l gradle/wrapper/gradle-wrapper.jar | grep GradleWrapperMain`
  must print `org/gradle/wrapper/GradleWrapperMain.class` — a few-hundred-byte jar, or a listing that
  shows `lib/plugins/…`, means you downloaded the wrong artifact. Then `./gradlew --version` proves
  the wrapper resolves: it downloads the distribution and prints the version **without compiling
  anything**, which is what makes it safe to run on a host where a build is forbidden. Finish with
  `./gradlew --stop` so the JVM is not left parked on a shared low-RAM box.
- **A pushed commit is not a shipped release — for a self-distributed APK the repo cannot tell you
  what users have.** Building, committing, and pushing are separate from the release script run that
  actually publishes, so a green pushed tree can have delivered nothing (a session found the served
  `update.json` three versions behind the repo, meaning earlier "released" work had never reached the
  user). Read the live manifest's `versionCode` before building on top of previous work or telling
  the user to install: when the user's only verification channel is installing a published APK, an
  unreleased change is indistinguishable from no change. Recipe:
  `references/sideloaded-app-update-checker.md`.
- **The build type that is actually SHIPPED is invisible from the source tree — inspect the
  published APK, not the repo.** A project can build `release` in its config and still have every
  distributed artifact be `debug` (because that is the command everyone runs). `aapt2 dump badging`
  each published APK and read `package:` — a `.debug` suffix means users have only ever run a
  debuggable build, which is 2–4x slower to start and visibly janky, and no amount of composable
  rewriting will fix it. Check this before optimizing any code. Recipe:
  `references/app-performance-and-release-build.md`.
- **A release build that has never been run is not "working", it is untested — and R8 will usually
  fail on the first try.** `assembleRelease` fails on missing classes (a jar referencing a JDK API
  Android lacks: `java.beans.*`, `javax.script.*`) and R8 writes the exact `-dontwarn` lines into
  `app/build/outputs/mapping/release/missing_rules.txt`. Copy those into `proguard-rules.pro`, plus
  explicit `-keep` for every reflection-based library that ships no consumer rules of its own
  (`unzip -l <lib>.jar | grep -i proguard` — empty output means you must write them).
- **A green release build does NOT prove a reflection-based feature works, and the failure is
  silent.** R8 strips names reflection looks up at runtime, so a missing keep rule yields no build
  error — the feature just fails on the device. Do not report a minified build as verified on
  compile evidence alone; name the reflection-heavy paths (external extractor/streaming, JSON
  deserialization, DB open) and have the user exercise them, then narrow the keep rule rather than
  disabling minify.
- **Shipping release without a reinstall requires BOTH the same applicationId AND the same signing
  key.** Changing build type normally changes the package (`com.x.app` vs `com.x.app.debug`), which
  Android treats as a different app — fresh install, media library re-scan. Setting
  `applicationIdSuffix = ".debug"` on release keeps the package id, and the project's committed
  `debug.keystore` keeps the signature; both are needed or the install is rejected. Verify with
  `aapt2 dump badging` + `apksigner verify --print-certs` against the currently installed version.
- **An image request with no `size()` decodes at native resolution — jank, not an error.** Album art
  is routinely 1000x1000 px+, so each one is ~4 MB decoded; in a scrolling list the allocations
  outrun the cache and the GC runs continuously. Pass the display size (`LocalDensity` →
  `roundToPx`) and register ONE app-wide `ImageLoader` via `ImageLoaderFactory` on the
  `Application` (per-screen loaders mean per-screen caches and repeated decodes). Two API traps:
  `MemoryCache.Builder.maxSizeBytes` takes an `Int` while `DiskCache.Builder.maxSizeBytes` takes a
  `Long`, and `maxSizePercent`/`maxSizeBytes` are the same setting so the last call wins.
- **`aapt2 dump badging` floods stdout with `application-label-<locale>` for ~80 locales** —
  grep `^package|launchable-activity|sdkVersion` instead of `application-label` when verifying.
- **Never read `versionCode`/`versionName` by piping `AndroidManifest.xml` through `strings` — the
  packaged manifest is BINARY, so that returns nothing and reads as "the APK has no version".**
  `unzip -p app.apk AndroidManifest.xml | strings | grep versionCode` produces empty output on a
  perfectly valid APK, which is a false negative that sends you inspecting the artifact instead of
  the command. Use `aapt2 dump badging` (it decodes the binary manifest) and grep `^package`, which
  prints `versionCode='16' versionName='0.11.0'` in one line. Corollary of the
  resolve-the-build-tools-path rule: when a version check returns empty, suspect the METHOD before
  suspecting the artifact.
- **Resolve the `build-tools/<version>/` directory — never hardcode it, and never suppress the
  tool's stderr.** The installed build-tools version is host-dependent (`35.0.1` exists, `35.0.0`
  does not), so a guessed path fails with "No such file" on stderr. Piping that through
  `2>/dev/null` converts a path typo into **empty output**, which reads as "the APK has no version
  info" rather than "wrong path" — a false negative that sends you debugging the artifact instead
  of the command. Glob it instead:
  `BT=$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)`.
- **Gradle first build is slow because it downloads dependencies** — 3–4 min on a minimal app is
  expected; do not conclude it is stuck.
- **A host that rebooted with no shutdown record was HUNG, not restarted cleanly — and a build you
  were running is the prime suspect.** `journalctl --list-boots` dates each boot; if the previous
  boot's last entries stop mid-sentence with no `Stopping…`/`Stopped…`/`Reached target Shutdown`,
  systemd never ran its shutdown path, so the machine hung and something external force-rebooted it
  (provider panel, host watchdog). Read the last minutes before death
  (`journalctl -b -1 --since … --until …`) and check for an OOM kill
  (`journalctl -b -1 | grep -i 'oom-kill\|killed process'`), then check what YOU had running at that
  timestamp before attributing the outage elsewhere. Do not report "the VPS went down" as a mystery
  when `free -m` plus a process list at build time already explains it. Note the daemon's own log
  names the limit: "The Daemon will expire after the build after running out of JVM Metaspace" or a
  bare "daemon disappeared unexpectedly" both mean resource exhaustion, not a code fault.
- **No `/dev/kvm` means no emulator, ever** — do not promise a running emulator on a VPS; verify
  with an artifact (APK) instead.
- **Do not delegate an Android build to a subagent** — a subagent's time budget is far shorter
  than a cold Gradle build plus dependency resolution. It will burn its whole budget on
  reconnaissance and return nothing, leaving the repo untouched. Do the build in the main session
  (or, for the artifact, on CI). If you do delegate, scope it to a single file or a read-only
  investigation, never "write the feature and make it build".
- **`javap` proves a class EXISTS and shows its shape — it does NOT prove you can call it.**
  Kotlin `internal` declarations compile to `public` JVM classes, so `javap` prints
  `public final class androidx.compose.material3.MotionScheme` and
  `public static final void MaterialExpressiveTheme(...)` for APIs the Kotlin compiler then
  rejects with `Cannot access 'interface MotionScheme': it is internal in file`. Use `javap` from
  the Gradle transform cache (`find ~/.gradle/caches/*/transforms -name '<lib>-api.jar'`) for
  signatures, parameter order, and nested-class names (`Outer$Inner`, quote them) — never for
  "is this available?". Confirm accessibility by compiling a one-line probe. Concluding
  "the API exists, so we can use it" from bytecode is how you present a user two options that
  both turn out to be dead. Recipe: `references/dependency-version-upgrade.md`.
- **The ABSENCE of a `SomethingKt` class does NOT mean a Kotlin API is missing — androidx has been
  moving Kotlin-facing methods onto the Java class itself, so `javap` the class you actually call
  before concluding anything.** Grepping `work-runtime` for `WorkManagerKt` finds nothing, which
  reads as "the `Flow`-returning overload does not exist here" — but
  `javap androidx.work.WorkManager` shows `getWorkInfosByTagFlow(String)` declared as a method of
  `WorkManager` itself (2.10.x). A `*Kt` class only exists when the function is a genuine top-level
  extension; its absence is a fact about packaging, not about availability. This is the same javap
  rule read the other way: bytecode tells you the shape of what IS there, and can only prove
  absence after you have inspected the right class. Concluding "not available" from a missing `*Kt`
  file pushes you to rewrite working code around an API you already have.
- **An opt-in / `@Experimental*` annotation seen on a CLASS may belong to a different OVERLOAD —
  check the method you actually call, not the type.** `javap -v` on the class shows the annotation
  and reads as "this needs opt-in", but `CrossfadeKt` carries `@ExperimentalAnimationApi` from an
  older deprecated overload while the overload with the `animationSpec` parameter you want is
  stable and needs nothing. Grepping the class-level annotation is a false positive that adds a
  spurious `@OptIn` (harmless but misleading) or, read the other way, makes you avoid a callable
  API. Read the annotations on the *specific* method signature with
  `javap -v … | grep -A40 '<methodName>('` and confirm which overload carries them. When the
  uncertainty is cheap either way, prefer the harmless side: an extra `@OptIn` on a file that
  already calls the experimental surface costs nothing, while guessing wrong the other direction
  costs a full CI round.
- **`maxByOrNull` / `minByOrNull` / `sortedBy` need a `Comparable` key — a `List<Int>` is not one.**
  Comparing version strings by mapping each to a list of integers and calling
  `maxByOrNull { it.version.toIntList() }` fails to compile with a "not comparable" error, and only
  the compiler catches it: a SQLite/fixture test of the same logic passes, because the ordering
  happens on the Kotlin side, not in the query. Use the explicit comparator overload —
  `maxWithOrNull { a, b -> compareVersionNames(a.version, b.version) }` (or `sortedWith`). General
  rule: every `*By` / `*ByOrNull` selector must return something the standard library can order;
  when the "key" is composite, switch to the `*With`/comparator form. This is the concrete shape of
  "a green data-path test is not a compile signal" — validate the SQL, then compile before claiming
  the feature ready.
- **Map an enum to its label/option with an exhaustive `when`, never a `first {}` / map lookup —
  a lookup turns a future edit into a runtime crash.** A settings row that resolves a stored enum to
  a chip or label via `OPTIONS.first { it.value == stored }` compiles and works for every value that
  exists today; the day someone adds a fourth enum member and forgets the list, the screen throws
  `NoSuchElementException` **the moment the user opens it** — a crash with no compile warning, on the
  one screen they must reach to change anything. An exhaustive `when` makes the same omission a
  compile error at the definition site instead. Same shape for a lookup table keyed on the enum:
  prefer `when` and let the compiler prove totality.
- **A composable that applies `.size()` internally cannot be reused for responsive layouts** —
  `size = 0.dp` renders nothing. Add a second entry point that sizes from the modifier.
- **A patch whose `old_string` ends in a newline and whose `new_string` does not silently deletes
  that newline** — joining the next line onto the previous one (`private fun X() {    Text(`), or
  collapsing a blank line before a KDoc block so `/**` is left dangling. The diff looks plausible
  in isolation and the file no longer compiles. Keep the trailing newline out of both sides, or
  include it in both. **And when a patch returns a diff that is not what you intended, re-read the
  file before patching again** — re-issuing near-identical patches blind is how one wrong edit turns
  into six calls and a mangled file. If the same edit has failed twice, stop and read the region.
  **Also confirm the patch hit the FILE you meant.** Applying a change meant for one screen to
  another file (a shared-looking `old_string` such as a constant declared in two places) succeeds
  silently and reports a normal diff and char count — nothing distinguishes "landed where I wanted"
  from "landed in the wrong file". When a change spans several files with similar structure, patch
  them one at a time and read the returned diff's file path, rather than firing near-identical
  patches at several files in a batch and assuming each found its target.
  **A patch result's "was modified by sibling subagent ... but this agent never read it" warning is
  a read-guard notice, NOT evidence that work was lost or overwritten.** It fires on any file this
  session did not read first, including files the same session legitimately edited earlier. Do not
  pass it to the user as a possible collision — that is a false alarm they cannot act on and it
  costs them worry. If you want to know whether anything was actually lost, ask git:
  `git status --short` plus `git diff --stat` shows the real set of changed files, and a diff that
  matches what you intended is the answer. Only report a collision when the diff shows one.
- **A flag that is already present is not the feature — verify the mechanism, not the keyword.**
  `AsyncImage.crossfade(true)` crossfades the *image load* (placeholder → bitmap) inside one
  composable; "crossfade artwork when the track changes" needs a `Crossfade`/`AnimatedContent`
  keyed on the song id, and the existing flag can sit there while the feature is entirely absent.
  Same shape as a settings row that exists but is wired to nothing. When asked to add something
  that sounds like it might already be there, grep for the MECHANISM (a state-keyed transition,
  a call site, a read of the value) rather than the concept's keyword. Recipe:
  `references/compose-motion-design-contract.md`.
- **A setting whose value must be read on a non-suspending thread needs an in-memory holder, not a
  DataStore read at the point of use.** A Media3 `DataSource` resolver runs on the playback thread
  and cannot suspend; collect the preference into a `@Volatile` field from an application-lifetime
  scope (a DI singleton under an `@ApplicationScope` qualifier) and read that field. Blocking the
  playback thread on disk stalls audio. Also invalidate any TTL cache of derived values when the
  preference changes, or the new setting does not take effect until the cache expires.
  **Declare every field an `init` block touches ABOVE that block — an `init` that launches a
  coroutine reading a later-declared property is a startup race.** Kotlin runs property
  initializers and `init` blocks in declaration order, so `init { scope.launch { cache[x] } }`
  placed before `private val cache = ...` lets the coroutine read `cache` while it is still `null`
  — an intermittent `NullPointerException` at construction, not a compile error. When adding an
  `init` that collects a flow or starts work, move the fields it reads to the top of the class.
- **A brace/paren balance check done with regex gives false alarms on `//` inside string literals
  (e.g. `https://`) — it is a smoke signal, not proof.** Counting `{` vs `}` after stripping
  comments with a regex mis-handles `//` that appears inside a URL or string, reporting an imbalance
  in a file that is fine. Do not treat its output as evidence of a syntax error, and do not treat a
  clean count as evidence the file compiles — only the real compiler does that.
  **When your checker flags a file, check that file at `HEAD` before believing it.** A file that
  already ships and compiles cannot be unbalanced, so an imbalance it reports there is a defect in
  the checker, not in the code — and `git diff` shows whether you introduced it. The trustworthy
  form of the check is the **delta diff**: count braces/parens on only the `+` and `-` lines of the
  diff (`git diff | grep '^[+-]'`), because the baseline is by construction balanced and any
  imbalance in the delta is a real edit error. A whole-file count mixes the checker's blind spots
  with your change and cannot tell them apart.
- **Building a shell command with an f-string from `execute_code` breaks on the first `{}` or
  nested quote — build it as a plain string.** Orchestrating a release means `terminal()` calls whose
  command text embeds JSON, `awk` programs, or `grep` patterns; an f-string treats every `{` as a
  substitution and a `"` inside the command terminates the Python string early, so the cell dies with
  `SyntaxError` or `NameError` *before* the command ever runs. Pass `terminal(command="...")` a plain
  (non-`f`) string, keep the shell quoting as the shell's business, and if a value must be
  interpolated use `%`-formatting or concatenation. A syntax error in the *cell* is not a failure of
  the command — fix the quoting and re-run rather than concluding the tool is broken.
- **A batch of file writes inside one `execute_code` call can leave a file UNCHANGED while the call
  reports success — read the changed files back before reporting the change done.** Writing several
  files in a loop and discarding the return values means a silent miss (a wrong path, a concurrent
  writer, a later overwrite) stays invisible until something downstream reads the stale content — and
  the summary you then write confidently claims a migration that half happened. When the writes
  matter, either do them one at a time so each result is visible, or re-read afterwards and grep for
  a string only the NEW content has (`grep -c 'Kotlin Multiplatform' README.md`, `grep 'jvmargs'
  gradle.properties`). A tool result that names the file and reports a byte count is evidence about
  the write; it is not evidence about the file's current contents.
- **Land a multi-line commit message via a file, or verify a heredoc actually committed.**
  `git commit -F - <<'EOF'` can trip the terminal tool's backgrounding guard, and when it does the
  commit never runs. It is not guaranteed to fail — it has both worked and silently no-op'd — so
  either write the message to `/tmp/commit-msg.txt` with `write_file` and use
  `git commit -F /tmp/commit-msg.txt`, or run the heredoc and then **confirm with
  `git log --oneline -1` that the commit landed** before moving on. Never assume a commit succeeded
  because the command returned without an error. **A single `&` in the message text is enough to
trigger this** — an ordinary sentence containing "album & artist" makes the shell background
  everything before the `&` and run the rest as a second command, so the commit silently never
  happens (or runs with a truncated message). Any message body that can contain `&`, quotes, or
  backticks must go through a file, not inline.
- **Set an explicit `workdir` on every build/commit command, and never `rm -rf` the directory the
  shell is sitting in.** If the session cwd is deleted, later commands die with a bare `exit 126`
  that looks like a permissions problem but is really "cannot resolve the current directory".
  Passing `workdir` per call (rather than a leading `cd`) sidesteps it entirely. A scratch dir has
  the same fragility in miniature: a `cd /tmp/x` in one call does not carry into the next, so refer
  to scratch files by absolute path rather than relying on an earlier `cd`.
- **Commit the generated Room schema JSON** (`app/schemas/<db>/<version>.json`) alongside the
  migration. It is the artifact that proves migrations line up, and `.gitignore` needs
  `!/app/schemas` to keep it tracked.
- **Do not "tidy" a `-v26` (or other version-qualified) resource directory away.** Lint may call
  `mipmap-anydpi-v26` redundant once `minSdk >= 26`, but that directory is what actually provides
  `ic_launcher`; renaming it to `mipmap-anydpi` breaks resource linking with
  "resource mipmap/ic_launcher not found". Leave adaptive-icon qualifier dirs where the templates
  put them.
- **`R` needs an explicit import when a composable lives in a subpackage** — a screen under
  `ui/screens` referencing `R.string.x` without `import <pkg>.R` fails to compile. Cheap to miss
  because files at the package root resolve it implicitly.
- **A green build does not validate a data path.** Queries and upserts compile regardless of whether
  they are destructive. After the layer builds, read back every DAO statement that mutates
  persisted user data and ask what it does to columns the writer does not supply — the two real bugs
  in a music-player scan path (`REPLACE` resetting play stats, `MIN(uri)` returning an audio URI as
  cover art) both compiled clean. See `references/media3-playback-service.md`.
- **Fixing a bug CLASS is not the same as fixing the bug instances — sweep the whole tree for the
  rule, then write the rule down.** When a defect comes from a pattern rather than a typo (a default
  value standing in for "not yet read", an unguarded `controller?.` call, a swallowed
  `CancellationException`), the reported screens are a sample, not the set. The count grows on every
  sweep: a bug found in 3 screens and fixed turned out to be 7 places once a mechanical grep was run
  against the stated rule — including inside the screen that had been the source of the good pattern.
  Procedure: fix the known instances → write the rule into the project's canonical doc (as a rule,
  not a changelog line) → grep the entire tree for it → classify each hit → repeat until clean. Also
  state the rule by MECHANISM, not by symptom: "never use `emptyList()` as an initial value" misses
  `0`, `false`, and `null`, while "no default may stand in for a value that has not been read yet"
  matches every shape. See `references/compose-loading-state.md` for a worked example.
- **A user reports ONE example; that is a sample, not the population — derive the affected set from
  the selection mechanism before calling it an edge case.** When a failure is produced by a shared
  default (the highest bitrate, the first result, the newest schema), the instance the user hit is
  a demonstration, not the boundary: the same rule fires for every input that lands in the same
  branch, so a one-off workaround leaves the rest broken and the next bug report is the same bug.
  Walk the code from the failing input back to the rule that chose it ("default quality -> highest
  bitrate -> Opus/WebM container -> rejected by the platform") and state the blast radius from that
  path before sizing the fix. The inverse costs just as much: announcing "this affects everything"
  without the mechanism is a guess the user may plan around.
- **A Room migration is the one thing you CAN fully verify headless — so verify it.** Room's check is
  pure schema comparison, reproducible in plain SQLite against the exported `app/schemas/*.json`. Run
  `scripts/validate-room-migration.py` for every hop before committing; a migration that compiles and
  passes lint can still crash on the **first open of the upgraded database** on the user's device,
 which is the one failure mode with no build-time signal at all. Validate each individual hop, not
 just the total, because a user several versions behind replays them in order. **Compare via PRAGMA,
 never via the `createSql` text in the `*.json`** — a `ALTER TABLE` result omits `IF NOT EXISTS`
 while Room's `createSql` includes it, so the strings always differ even when the schema matches
 (a permanently-red, meaningless comparison). Compare columns (`cid`, `name`, `type`, `notnull`,
 `dflt_value`, `pk`) and, per index, `PRAGMA index_info` — a migration that forgets to recreate an
 index passes `table_info` and is caught only by the index check. After bumping the version, confirm
 the new `<version>.json` was actually generated before trusting it as the reference.
- **Do not infer a stale artifact from APK file size.** A CI-built APK landing on the exact byte
  count of an older local build is a coincidence, not proof it rebuilt the wrong commit — DEX
  layout shifts cancel out and produce identical totals. Confirm which commit a downloaded APK
  actually contains by grepping its dex for a string only the new code has, or by unzipping and
  checking the classes you added, then compare the CI run's head SHA against your local `HEAD`.
  Concluding "CI is building a cached old commit" from size alone wastes a full investigation and
  can send you re-running a pipeline that was already correct.
- **A verification command can silently compare a thing with itself — so when two methods disagree,
  neither result is right until you re-run both cleanly.** A chained one-liner like
  `mkdir a b && cd a && unzip -o L -d . && cd ../b && unzip -o C -d . && sha256sum *.dex &&
  sha256sum *.dex` runs BOTH hashes in whichever directory the `cd` actually landed in, so the two
  outputs are the same files and the comparison prints "IDENTIK" for a pair that is in fact
  different. When that bogus "identical" then contradicts a `diff` that says five files differ,
  do not believe the convenient one, and do not believe whichever you ran first: re-extract each
  side to its own absolute path in its own command (`unzip -o "$APK" -d /tmp/vL 'classes*.dex'`,
  then `cd /tmp/vL && sha256sum classes*.dex > /tmp/hL.txt`), `diff` the two manifests, and let
  that settle it. In this case the hash loop was the broken side and `diff` was right — the
  opposite of the usual "trust the hash" instinct, which is exactly why a disagreement means
  re-verify rather than pick.
- **`ADD COLUMN x TEXT DEFAULT NULL` is rejected by Room — omit the default.** The literal `'NULL'`
  becomes the column's stored default (`PRAGMA table_info` shows `dflt_value='NULL'`), while Room
  expects no default for a nullable column. Write `ADD COLUMN x TEXT`. See
  `references/media3-playback-service.md`.
- **A cloud/datacenter build host cannot verify anonymous stream resolution — say so before coding,
  not after.** Search and parsing are verifiable headless; fetching the audio URL is not (YouTube
  bot-checks datacenter IPs: `SignInConfirmNotBotException`). Probe ~10–15 items to get a ratio
  rather than trusting one old upload, and build so a failed resolve shows on screen. Do not write an
  unverified bypass (iOS client, PoToken) into the design as "the fix". See
  `references/streaming-extractor-integration.md`.
- **When an external API hangs but other hosts work, test IPv4 explicitly before blaming the API.**
  A host whose DNS returns only AAAA records will hang on a machine with broken IPv6 routing — the
  connection neither succeeds nor fails fast, so it reads as a flaky third-party service. Diagnose
  with `getent hosts <host>` (are there any A records?) then retry with `curl -4`; a response over
  IPv4 proves the API is fine and the problem is local routing. This matters beyond the build: it is
  the difference between "the provider is unreliable" (design for retries) and "this host cannot
  reach the provider" (design cannot fix it) — two conclusions with opposite consequences.
- **A third-party jar can implement a JDK API Android does not ship — check transitive deps, not
  just bytecode version.** `android.jar` has **zero** `javax.script` classes, so an artifact that
  binds a scripting engine through `javax.script` compiles cleanly and crashes on device. A
  JavaScript-based extractor pulls in `rhino-engine` (the `javax.script` binding) next to `rhino`
  (the engine); exclude the binding, keep the engine. For any jar, `javap -v` a few classes and
  grep for `javax/script`, `java/awt`, `javax/swing`, `java/beans` before adding the dependency.
  See `references/streaming-extractor-integration.md`.
- **Check the exact class, not the package — a package-level grep lies.** `android.jar` is not empty
  for every JDK package: it ships a handful of `java.beans` classes but **not**
  `java.beans.Introspector`, `BeanInfo`, or `PropertyDescriptor`, which Rhino's
  `JavaToJSONConverters` references. `grep -c java/beans` on `android.jar` returns a nonzero count
  and reads as "present". Diff the *specific* classes your dependency references against the jar
  (`unzip -l $ANDROID_HOME/platforms/android-35/android.jar | grep 'java/beans/'`), never the
  package prefix.
- **A missing class fails as `NoClassDefFoundError` — an `Error`, so `catch (Exception)` does NOT
  catch it, and a desktop-JVM probe CANNOT reproduce it.** That combination is why a jar-compat gap
  reaches users as a bare force close with no error message: the desktop JDK *has* the class, so a
  standalone probe resolves it and passes while the device throws. Treat "works in my probe but
  crashes on device" as a class-availability problem and check `android.jar`/the dex, not the logic.
- **Before blaming the newest release for a user-reported bug, diff the suspect files against the
  previous release tag.** A crash reported in a screen your last commit did not touch is a
  pre-existing bug that was never exercised on a device, not a regression — and the two call for
  different investigations. `git diff v<last>..HEAD -- <suspect files>` settles it in one call;
  byte-identical output means the code path is unchanged, so stop hunting your recent work and
  reproduce from scratch. It also answers what the user actually needs to know: whether updating
  fixes it.
- **A `fillMaxSize()` child inside a `Column`/`Row` pushes its siblings off-screen.** A centered
  "message + action button" block written as `Column { Message(); Button() }`, where `Message`
  applies `fillMaxSize()` internally, gives the message all the height and leaves the button zero —
  it is never reachable, and the code compiles and lints clean. Wrap the pair in a
  `Box(contentAlignment = Center)` and let the inner `Column` wrap its content instead. Check any
  helper you reuse for a hardcoded `fillMaxSize()`/`fillMaxWidth()` before placing it beside a
  control the user has to tap.
- **Modifier order decides what padding does.** `.height(14.dp).padding(vertical = 4.dp)` applies
  the padding *inside* the 14 dp, leaving a 6 dp bar that looks like a different bug. Put
  `.padding()` before the size modifier, and read modifier chains outward-in when a measurement is
  wrong.
- **Never hardcode the app version in a runtime string.** A `User-Agent`, header, or log line
  built with a literal `"v0.4.0"` becomes a second source of truth that goes stale every release
  with nothing to catch it. Read `BuildConfig.VERSION_NAME`.
- **A comment that claims a property the code does not have is a bug with a witness — verify the
  claim against the code, don't trust it.** A cache documented as "stores null too, so a colourless
  image is not recomputed" was implemented as `cache[url]?.let { return it }`, which cannot
  distinguish "not computed" from "computed, empty" — so it recomputed exactly what it claimed to
  skip. Comments are written from intent and read as fact by the next session (and by you, minutes
  later); when a comment states a behaviour, read the adjacent lines and confirm they implement it.
  The same reading catches the inverse: a comment describing the OLD behaviour left above code that
  has since changed.
- **Keep user-facing strings to plain ASCII punctuation — no em dash.** Em dashes in
  `strings.xml`, screen titles, commit messages, and release notes are a house style violation for
  this user; use a hyphen, a colon, or a full stop. Code comments and internal docs are exempt and
  may use them freely, so a repo-wide em dash audit gives false alarms — scope the grep to the
  string resource files, the commit message, and the release-facing docs. Check all three before
  reporting a UI-text or release change done. The trap is that `strings.xml` also contains XML
  comments, so a raw `grep -c '—' strings.xml` over-reports: run `grep -n '—'` and read each hit to
  separate a `<string>` value (must fix) from a `<!-- -->` comment (exempt). Three more scopes count
  as release-facing and are easy to miss: `README.md`, `CHANGELOG.md`, and the in-app version-history
  JSON (e.g. `app/src/main/assets/changelog.json`). The last one is easy to forget because it lives
  under `assets/` next to machine data, but a version-history screen renders it verbatim to the
  user, so it is a user-facing string source and follows the same punctuation rule as `strings.xml`. The full sweep is
  `grep -c '—'` over strings.xml, README.md, CHANGELOG.md, the version-history JSON, plus
  `git log -1 --format=%B | grep -c '—'` — and note that a string already shipped in a published
  APK cannot be fixed by editing the repo alone; it needs a patch release to reach users. If you
  publish via `gh release create`, the notes file is a fifth scope: `grep -c '—' /tmp/notes.md`
  before the release call.
- **An extractor library sets no User-Agent — YOUR bridge must, and it must match playback's.**
  A `Downloader` bridge that only forwards the extractor's own headers sends no UA at all, while the
  playback `DataSource` sends its own; YouTube binds a `videoplayback` URL to the requesting client,
  so two different (or missing) UAs produce an intermittent 403 on a URL that is still valid. Write
  the UA once and reference it from both sides. Also: grepping the extractor jar for the UA value is
  a **false negative** (`DownloaderImpl` lives in the NewPipe app, not the library) — do not conclude
  a value is invented from a jar search. See `references/streaming-extractor-integration.md`.
- **Never set `User-Agent` on `DefaultHttpDataSource.Factory` when a URL needs its own.** Media3
  writes the factory UA *after* the `DataSpec` headers, so it overrides any per-request UA and
  silently breaks URL variants that require a different one (e.g. visionOS). Put `User-Agent` into
  `DataSpec.httpRequestHeaders`.
- **Never persist an extractor's stream URL** — they expire in hours. Store stable identity and
  resolve at playback time, which puts resolution in the playback service, not the scanner. The
  mechanism is a private placeholder scheme swapped by a `ResolvingDataSource` (recipe in
  `references/streaming-extractor-integration.md`). Also remember `INTERNET` permission: a project
  that started local-only will not have it, and its absence fails at runtime, not build time.
- **Check the licence before adapting code from a reference repo — and write the adaptation
  yourself.** Reading another app for design ideas is legitimate; copying its source into the user's
  project is a licence question, not a technical one. A GPL/copyleft source dropped into a repo with
  no `LICENSE` file (or a permissive one) contaminates the whole project, and the user is the one
  exposed. Check the reference repo's `LICENSE` **before** reading code with intent to reuse, then
  re-implement the pattern in your own words: keep the idea (SQL shape, threshold value, layout,
  state model), discard the expressions. Say plainly in the report that this is what you did — the
  user needs to know the constraint existed, not just the outcome. The same check applies when the
  user says "make X like repo Y": "referenced from" is the goal, not "copied from".
- **`pgrep -f <pattern>` matches the shell command that CONTAINS the pattern, so a liveness check can
  report "still running" forever.** Polling a background Gradle build with
  `pgrep -f lintDebug >/dev/null && echo "MASIH JALAN"` inside a `terminal` call reports the build is
  alive even after it finished, because the shell running that very command has `lintDebug` in its own
  command line. The same trap hits `ps | grep`, which also matches the `grep` itself. Trust the log's
  exit marker (`tail` for the `EXIT=` line the job appends) or the task-notification, and treat a
  bare process-name match as inconclusive rather than as "still running". If you need a process
  check, exclude yourself (`pgrep -f "[l]intDebug"`) or check the Gradle daemon's actual state.
- **A background build started before your last edits is stale — never report its result.** Starting
  `assembleDebug` and then continuing to edit source is normal; treating the notification that
  eventually arrives as proof of the *current* tree is not. Re-run the build after the final edit, or
  state explicitly which revision it was covered. Same trap for any long-running verification: bind the
  result to the revision it was produced from.
- **Writing a source file WHILE `lintDebug` runs crashes lint with an internal error, and the crash
  names YOUR new file — which reads as a bug in that file.** Editing during a background
  `lintDebug :app:assembleDebug` produced
  `Unexpected failure during lint analysis of SpotifyTrackResolver.kt` /
  `Cannot find a KaModule for the VirtualFile` (a lint/Kotlin-PSI internal failure, not a finding).
  The tell that it is a race and not a code defect: `assembleDebug` in the SAME run had already
  printed its task line successfully, so the APK existed and the compile had passed. Re-running the
  build after all edits finished went green with the same file untouched. When a lint crash cites a
  file you just wrote, do not start debugging that file — re-run the build first; only if it
  reproduces on a quiet tree is it real. Corollary of the stale-build rule above: finish all edits
  BEFORE starting the release build, never during it.
- **A `javap` signature also tells you the MODIFIERS — read the `Continuation` parameter and you
  know the function is `suspend` before the compiler tells you.** `javap` printing
  `setProgress(androidx.work.Data, kotlin.coroutines.Continuation<? super kotlin.Unit>)` means
  `CoroutineWorker.setProgress` is suspend, so a plain lambda cannot call it; the compile error then
  lands on the lambda ("Suspension functions can only be called within coroutine body") and reads as
  a problem with the callback rather than the API. When you verify an artifact, read the parameter
  list for `Continuation` (suspend) and for the declared type, not just the method name — the shape
  you were checking is the shape that decides how you write the caller.
- **A fact you established by inspection must actually reach the code you then write — re-read your
  own output against the verified fact before compiling.** Verifying `EntryPointAccessors` lives in
  `dagger.hilt.android` and then writing `import androidx.hilt.android.EntryPointAccessors` compiles
  cleanly in the head and fails at the gate; the verification was done and wasted. This is the same
  failure as "I checked the interface implementers" followed by editing only one. When a check is
  expensive enough to be worth running, it is worth pasting its answer verbatim into the edit rather
  than re-deriving the value from memory one line later.
- **A `by`-delegated property cannot be smart-cast — bind it to a local `val` before the `when`,
  never reach for `!!` inside a branch.** `val ctx by vm.ctx.collectAsStateWithLifecycle()` gives a
  property whose getter re-runs on every read, so the compiler refuses to smart-cast
  `ctx != null ->` into a non-null type and pushes you toward `ctx!!` — a crash waiting for the
  state to flip between the null check and the use. Capture it once above the `when`
  (`val context = ctx`) and branch on that; the delegated-property case is exactly the shape the
  compiler warns about and the reason the fix is a local, not an assertion. Same reason a labelled
  early exit from inside a `when` branch (`return@Column`) is fragile: it depends on the enclosing
  lambda's label, which silently breaks when the block is wrapped in another `{}` or moved into a
  helper. Capture-then-branch has neither problem.
- **`Flow.map<T> { }` takes the INPUT type as its first parameter.** Writing
  `.map<SomeState> { SomeState.Ready(it) }` fails with a confusing "Cannot infer type" cascade,
  because `T` is the upstream element type, not the output. To widen a flow's element type (e.g. to
  emit `Loading` / `Ready` / `Failed` on one stream), declare the type on the receiving variable
  (`val flow: Flow<ScreenState> = combine(...) { ... }`) and let the lambda return the subtype. The
  same "first type param is the input" rule applies to `transform` and `mapNotNull`.
- **Extract device-untestable logic into a pure top-level function, then unit-test it.** Android
  playback/UI logic cannot be run headless, but the *decisions* inside it often can. Pull the risky
  branch (which index to restore, how a range maps to a timestamp, how an option maps to a stored
  value) into a plain `internal fun` with no Android types, and cover it with `testDebugUnitTest` —
  the one part of the app you can actually assert on without a device. Run it beside the other
  gates, `./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug`, and read the pass
  count from `app/build/test-results/testDebugUnitTest/*.xml` rather than trusting a green task.
  Spend this on logic whose failure is silent and user-visible (the wrong track restored, the wrong
  bucket counted) — exactly the bugs a build cannot catch.
  **Parse that XML with an XML parser, not a regex.** JUnit's `testsuite` element does not guarantee
  attribute order, so `re.search(r'tests=(\d+).*?failures=(\d+)', x)` can match nothing and report
  `tests=0 failures=0` — which reads as "every test disappeared" and sends you hunting a
  test-collection failure that does not exist. Use `xml.etree.ElementTree`: it reads the attributes
  by name and cannot be fooled by reordering. A zero count from a regex over generated XML is a
  parsing artifact until an XML parser confirms it.
- **A test task that reports `UP-TO-DATE` did NOT run — force it before treating the result as
  verification of your change.** Gradle skips `testDebugUnitTest` when it believes nothing relevant
  changed, so a green run right after an edit can be the PREVIOUS run's result and its pass count is
  not evidence about the code you just wrote. Clear the results and force execution:
  `rm -rf app/build/test-results/testDebugUnitTest && ./gradlew :app:testDebugUnitTest --rerun-tasks`.
  Only a run that actually executed the new tests is a gate; report an `UP-TO-DATE` line as "not run",
  never as "passing".
- **`runCatching {}` swallows coroutine cancellation — same bug as `catch (Exception)`, harder to
  grep.** It catches `Throwable`, so `CancellationException` is absorbed and a ViewModel being
  cleared or a superseded job reads as a real failure. It is worse than the `catch` form because
  there is no `catch` keyword to search for. Inside a coroutine (or a `suspend` call path) use
  `try { … } catch (e: CancellationException) { throw e } catch (t: Throwable) { … }`. Outside one
  (file I/O, JSON parse) `runCatching` is fine — there is no cancellation to lose. Audit with
  `grep -rn 'catch (e: Exception)\|runCatching' app/src/main/kotlin/` and check each hit for a
  surrounding coroutine.
- **A blocking call that bypasses the target's IO-wrapped repository seam runs on the main thread,
  and a per-item `catch` then hides it as an empty result.** A repository method that wraps a
  blocking call in `withContext(Dispatchers.IO)` is not interchangeable with the raw source beneath
  it: calling the source directly from a `viewModelScope.launch` throws
  `NetworkOnMainThreadException`, which a resilience catch (`catch (_: StreamException) { return
  null }`) converts into "no match". The symptom is the worst kind, the operation reports success
  with zero output and no log line, so it reads as "none of these exist upstream". Route the call
  through the seam (do not add a second `withContext` at the call site when the seam already exists),
  give the swallow a counter/hook so a systemic failure can surface, and install any pluggable logger
  the borrowed client ships, which the target usually never wires. Recipe:
  `references/porting-from-reference-repo.md`.
- **A state field you WRITE is not "visible to the user" until you grep where it is READ.** Wiring a
  failure into `uiState.errorMessage` and claiming "the user will now see it" is a false claim until
  you confirm a composable actually renders that field — and renders it on the screen the user is
  on when it fires. `grep -rn 'errorMessage' app/src/main/kotlin/` shows both the writes and the
  single read; if the only read is on a full-screen destination the user is not on, the message is
  invisible. Put the surface where the failure actually happens (e.g. a banner in the always-visible
  `bottomBar` slot, which also auto-hides on full-screen routes so it never doubles up), and add a
  dismiss path so a transient failure does not stick on screen for the whole session. The same holds
  for a callback or hook you ADD but never fire: a `onSearchFailure` lambda field compiles, sits in
  the constructor, and does nothing until a caller invokes it, so a report claiming "the failure is
  now logged/counted" is false until you grep the call site that actually calls it. Add the field and
  its invocation together, or do not add the field.
- **A callback PARAMETER that is never invoked makes a whole control silently inert — grep each
  callback's name inside its own function body.** A composable that declares `onPlay: (List<SongEntity>, Int) -> Unit`,
  renders the rows, and never calls `onPlay` compiles, lints, and ships: tapping an album does
  nothing at all, with no error anywhere, and it reads to the user as "the app is broken" rather
  than "this screen has no click handler". It is the same shape as the write-vs-read trap above
  (declared but never consumed) and it hits entire LIST SCREENS, because a `LazyColumn` of rows is
  exactly where the click is easy to forget. Detect it mechanically — for every callback parameter
  of every screen composable, confirm the name appears at least once outside its own declaration
  (`grep -c 'onOpenAlbum' LibraryScreen.kt` must be > 1: the parameter, plus a call site). Fix by
  wiring the control to a navigation route, not by deleting the parameter — the parameter existing
  is evidence the intent was there and the wiring was dropped. Note that a tab whose only action is
  "play all" and a tab whose action is "open detail" need DIFFERENT callbacks; collapsing both onto
  one `onPlay` is how the detail screen gets skipped and the parameter goes unused.
  **The mirror-image failure is on the CALLER side, and no compile, lint, or test gate sees it: a
  shared menu/row component that invokes its callback correctly still renders that action inert at
  every call site that does not PASS the argument.** Adding an optional callback parameter
  (`onDownload: (() -> Unit)? = null`) to keep untouched callers compiling is exactly what hides it —
  the new action appears on the screens you edited and silently vanishes on the ones you did not,
  and the user reports it as "the menu is missing" on one specific screen. After wiring a new
  per-item action, grep the component's own name and read EVERY construction site, not just the one
  you changed (`grep -rn 'SongMenu(' app/src/main/kotlin/`), and confirm each passes the new
  argument. Rows whose item is not in the database yet (search results) must derive their id from
  the SAME source the writer uses, or the action's per-row state never connects to the row it
  created. **A helper written for a case but never called is the same bug wearing a different hat —
  grep for at least one caller before reporting the feature done** (a helper whose name appears only
  at its own declaration means the wiring was dropped, not that the code is spare).
  **The third form is a handler wired to the WRONG action: invoked, but not what its label
  promises.** A shared no-arg-callback menu (`onPlayNext: () -> Unit`, plus
  `onPlay: (List, Int) -> Unit`) makes it natural to point two rows at one lambda —
  `onPlayNext = { onPlay(theWholeList, 0) }` compiles, renders, and queues the entire list instead
  of the one track the row's label says it queues, so "play next" silently plays the whole album.
  It is invisible to every gate because the callback IS called and the control IS responsive. When
  wiring a menu of several actions, read each action's LABEL against the handler behind it — a
  distinct action needs a distinct lambda, not merely a non-null one.
- **Do the self-review pass BEFORE the final build, not while it runs.** Re-reading your own diff is
  valuable and will always find something; if you do it while a build is in flight, every finding
  becomes an edit that invalidates that build, and you end up killing and restarting it repeatedly.
  Sequence it: finish edits → review the diff → fix what the review finds → *then* build once. The
  stale-build pitfall above is the symptom; reviewing at the wrong time is the cause.
- **Before porting a module from another Kotlin project, diff the version catalogs — a library that
  requires a newer Kotlin makes the port a decision, not a copy.** A Ktor 3.x-based client needs
  Kotlin 2.1+, so it cannot be dropped into a project pinned at Kotlin 2.0.x, and bumping Kotlin
  drags KSP, Hilt, and the Compose compiler plugin along with it on a project that currently builds.
  Prefer porting the LOGIC and rewriting only the transport onto a dependency the target already
  has (OkHttp + kotlinx.serialization are common) — the port stays faithful, the version catalog
  stays put, and there is nothing new to justify. Check `kotlin`/`agp`/`ksp` in the target's
  `gradle/libs.versions.toml` against the source's before writing a single file. Recipe:
  `references/porting-from-reference-repo.md`.
- **`git grep` on a `--filter=blob:none` partial clone fetches every blob and hangs.** A sparse or
  partial clone is fine for `git ls-tree -r --name-only HEAD | grep <pattern>` (paths only, no
  blobs), but the moment you search file CONTENTS, git backfills the whole object store and the
  command times out with no output — which reads as "the pattern is not there". Either search paths
  with `ls-tree`, or take a plain `git clone --depth 1`; a mid-size app repo is tens of MB and
  clones in seconds, and a full clone makes every later grep instant.
- **When the user chooses to ADOPT a reference repo's copyleft licence rather than re-implement,
  the obligations are work items, not a note.** Add the licence text at the repo root, put an
  attribution header (source project, author, licence, pointer to root `LICENSE`) on **every**
  ported file — GPL §4/§5 require preserving notices — and state it in `README.md`. Leave
  from-scratch files unheadered so the derived ones stay identifiable.

## Cleanup note

A full toolchain (kotlinc + Android SDK + Gradle) is ~1–1.5 GB. Remove the downloaded zips after
unpacking, and if the toolchain was only for a one-off test, delete `~/kotlin`, `~/android-sdk`,
`~/gradle-*` afterwards.
