# Kotlin Multiplatform (KMP) scaffold — writing it without a build

Use when the project must run on **Android + iOS from one codebase** (Compose Multiplatform),
or when the user asks "why not full native Kotlin" and the answer lands on KMP. This file is the
scaffold shape, the version-catalog discipline, the compile traps that only a build catches, and
the per-platform secure-storage recipe.

## Choosing the stack — lead with the platform limit, not preference

`native` is NOT automatically safer than React Native. `jadx` reads a Kotlin/Java APK as readily as
`hermes-dec` reads a React Native bundle — obfuscation (R8, PairIP-class protectors) is what raises
the cost, and it applies to both. The security argument for native is *harder to read after R8*,
not *cannot be read*. Server-side authorization is what actually prevents abuse, in every stack.

The decisive argument is usually a **hard platform limit**, so state it before comparing:

| Capability | Android | iOS |
|---|---|---|
| Read other apps' notifications (bank/QRIS auto-detect) | `NotificationListenerService` | **impossible** — no public API, no entitlement |
| Bluetooth ESC/POS printing | full | limited / MFi-gated |
| Device integrity attestation | Play Integrity | **App Attest** (not Play Integrity) |
| Cashier, catalog, reports | yes | yes |

If the product's differentiating feature is Android-only, cross-platform value drops sharply and the
honest options are: (A) full native Android (smallest, fastest, no bridge, no OTA), (B) KMP (one
codebase, iOS gets the degraded subset), (C) RN/Expo (fastest to ship, OTA, JS bundle easier to
read). Name the cost of each: no-OTA means every fix goes through store review.

**An iOS need that is read-only (viewing reports) does not require a native iOS app.** A web
dashboard opened in Safari (Add to Home Screen) satisfies "owner checks reports on iPhone" with a
fraction of the work, no App Store review, and no second UI. Offer that before agreeing to build two
apps — especially for a solo developer.

## Project shape

```
composeApp/src/
  commonMain/kotlin/<pkg>/
    core/{model,network,storage,util,platform}/   # shared logic + Compose UI
    feature/{auth,cashier,catalog,cart}/
    ui/{theme,component}/
  androidMain/   # MainActivity, Application, manifest, Android secure storage
  iosMain/       # MainViewController(), iOS secure storage
  commonTest/    # pure-logic tests (money, parsing) — runnable headless
```

Root: `settings.gradle.kts` (`include(":composeApp")`), `build.gradle.kts` (plugins `apply false`),
`gradle/libs.versions.toml`, `gradle.properties`.

Plugin set in `composeApp/build.gradle.kts`:
`kotlinMultiplatform` + `androidApplication` + `composeMultiplatform` + `composeCompiler` +
`kotlinSerialization`. iOS targets: **`iosArm64()` + `iosSimulatorArm64()` only** with
`binaries.framework { baseName = "ComposeApp"; isStatic = true }`.

**Do NOT add `iosX64()`.** Compose Multiplatform removed the Apple x86_64 targets entirely in
1.11.0 (they were deprecated in Kotlin), so no CMP artifact — and no `org.jetbrains.androidx.lifecycle`
artifact — exists for `iosX64`. The failure is not a missing framework at link time; it aborts
**dependency resolution for the whole project**, including `commonMain`:

```
e: ❌ KMP Dependencies Resolution Failure
Source set 'commonMain' couldn't resolve dependencies for all target platforms
Couldn't resolve dependency 'org.jetbrains.compose.runtime:runtime:1.12.0' in 'commonMain'
The dependency should target platforms: [android, android, iosArm64, iosSimulatorArm64, iosX64]
Unresolved platforms: [iosX64]
```

Nothing is lost: a real iPhone is `iosArm64` and a current Mac simulator is `iosSimulatorArm64`.
Copying a three-target list from an older template is how this lands in a fresh scaffold.

**Ktor engine is per-platform, in the source set, not `commonMain`:** `ktor-client-okhttp` in
`androidMain`, `ktor-client-darwin` in `iosMain`, `ktor-client-core` in `commonMain`.

## Version catalog — verify against real releases, never from memory

A version catalog written from memory is reliably months behind and the first build fails on
nothing but versions. Check each artifact's release page before writing `libs.versions.toml`, and
respect the couplings:

- **The requirement is a CHAIN, and CMP sets its bottom: CMP → AGP → Gradle → compileSdk.** CMP
  1.12.0 bundles `androidx.compose.ui:ui-android:1.12.0`, whose `aar-metadata.properties` declares
  `minCompileSdk=37` and `minAndroidGradlePluginVersion=9.1.0`; AGP 9.1.1 in turn needs Gradle 9.3.1.
  So "use the newest CMP" is silently a four-part toolchain migration, and a project on AGP 8.x +
  compileSdk 36 **cannot** resolve it at all — CI fails with `requires Android Gradle plugin 9.1.0 or
  higher` and `requires libraries and applications that depend on it to compile against version 37`.
- **Read the bundled mapping from the CMP release notes, not from memory.** Each release body carries
  a `Dependencies` table naming the exact Jetpack version that CMP release wraps (plus the matching
  lifecycle/navigation), which is the authoritative way to assemble a self-consistent set:
  ```bash
  curl -s 'https://api.github.com/repos/JetBrains/compose-multiplatform/releases/tags/v<ver>' \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['body'][:3000])"
  ```
  Measured: CMP **1.11.1** wraps Jetpack UI **1.11.2** (compileSdk 35, AGP 8.6) and is the newest
  release that works on AGP 8.x; CMP 1.12.0 needs the AGP 9 chain above.
- **AGP 9.x changes the DSL AND breaks the KMP plugin pairing.** With AGP 9.0+, the Kotlin
  Multiplatform plugin is no longer compatible with `com.android.application` / `com.android.library`
  — migrating means moving the app entry point into a separate `androidApp` module and using the
  Android-KMP `androidLibrary` plugin for the shared module. Budget that restructure before telling
  the user "just bump the version"; the cheap answer is usually to pick the newest CMP that still
  fits the existing AGP.
- **AGP ↔ Gradle are coupled.** Each AGP has a minimum Gradle. Read it from the AGP release notes
  (`developer.android.com/build/releases/agp-<v>-release-notes`) — e.g. AGP 8.12 needs Gradle 8.13,
  AGP 9.1.1 needs Gradle 9.3.1.
- **Kotlin ↔ AGP**: Kotlin 2.4 requires AGP >= 8.5.2 (see `developer.android.com/build/kotlin-support`).
- **A third-party Compose library can drag the same floor in on its own.** A QR/chart/picker
  artifact is as capable of forcing the AGP 9 migration as CMP itself — qrose 1.3.0's Android
  artifact declares `minCompileSdk=37`. Run the AAR pre-flight
  (`references/dependency-version-upgrade.md`) on **every** Compose-dependent artifact, not just CMP,
  and note that a KMP bump also needs the artifact to exist for **each** target platform.
- **androidx artifacts live on Google Maven**, not Maven Central — probing `repo1.maven.org`
  returns 404 and reads as "version does not exist".
- **AndroidX Lifecycle for KMP is the JetBrains fork**:
  `org.jetbrains.androidx.lifecycle:lifecycle-*-compose`, versioned independently of the AndroidX
  `androidx.lifecycle` release numbers.

**A dependency declared in the catalog with ZERO references in the source tree is not free — grep
each entry before shipping the catalog.** `lifecycle-viewmodel-compose` sat in
`commonMain.dependencies` while `grep -rniE 'viewmodel|lifecycle' --include='*.kt' .` returned
nothing — and the declared version happened to be the one carrying the AGP 9 floor, so an unused
dependency was imposing a toolchain migration on the whole project. After writing the catalog,
confirm every entry has at least one import and delete what does not (this project had no ViewModel
at all, so the entry simply went away).

### `androidx.security:security-crypto` is DEPRECATED — do not use it for token storage

`EncryptedSharedPreferences` / `MasterKey` are deprecated (1.1.0) with **no official replacement**.
Do not scaffold a new project on them. Use the Android Keystore directly: generate an AES-256 key
in `AndroidKeyStore` (never leaves hardware), encrypt with `AES/GCM/NoPadding`, store
`"<iv b64>:<ciphertext b64>"` in a plain `SharedPreferences`. Keep `allowBackup="false"` plus
`dataExtractionRules` so the ciphertext never leaves the device.

## Ktor in `commonMain` — the generic-wrapper type-erasure trap (runtime, not compile)

A shared `ApiClient` that funnels every verb through one generic helper is where this bites, and it
**compiles clean and fails on the first request**:

```kotlin
// BROKEN — fails at runtime with "Serializer for class 'Any' is not found"
private suspend fun execute(method: HttpMethod, path: String, body: Any?): String =
    client.request(path) { this.method = method; if (body != null) setBody(body) }
```

Ktor resolves the request body's serializer from the **`TypeInfo` at the call site**. Inside
`execute`, the static type of `body` is `Any?`, so Ktor looks for a serializer for `Any` — which does
not exist — and every POST/PUT throws. Passing `@Serializable` data classes does NOT help; the
erasure already happened at the wrapper boundary.

Fix: capture the reified type in the *inline* public function and thread it down explicitly.

```kotlin
// public inline keeps the reified ergonomics; @PublishedApi internal lets it call the private one
inline fun <reified B : Any> post(path: String, body: B): String =
    execute(HttpMethod.Post, path, body, typeInfo<B>())

@PublishedApi internal suspend fun execute(
    method: HttpMethod, path: String, body: Any?, bodyType: TypeInfo,
): String = client.request(path) { this.method = method; if (body != null) setBody(body, bodyType) }
```

`setBody(body: Any?, bodyType: TypeInfo)` is the overload that takes the type explicitly
(`io.ktor.util.reflect.typeInfo<T>()`); the single-arg `setBody(body)` is the one that re-erases.
Callers need no change — `B` infers from the argument, `T` from the return type.

**A raw `mapOf(...)` as a body is the same failure in a plainer form.** `Map<String, String>` has no
inferrable serializer shape, so it throws too. Every request body is a `@Serializable data class`,
never a `Map`.

**Verifying a library's API without a build: download its `-sources.jar` from Maven Central and read
it.** For a third-party Compose/KMP library whose API you must call exactly (QR painters, charts,
pickers), guessing the overload from docs costs a compile round; the source is one command away and
shows the real package, signatures, defaults, and any companion-extension surprises:

```bash
curl -sSL -O https://repo1.maven.org/maven2/<group-path>/<artifact>/<ver>/<artifact>-<ver>-sources.jar
unzip -o -q <artifact>-<ver>-sources.jar -d src
sed -n '1,80p' src/<pkg-path>/<File>.kt          # package + signatures, verbatim
```

Reading it is what catches traps a doc page hides — e.g. a `QrBrush.solid(...)` that is actually an
extension on the companion object (so it needs its own import and is easy to mis-call), or the
overload set below.

**When a library ships several overloads and two of them have ALL parameters defaulted, a call that
names only the required argument is AMBIGUOUS and fails to compile.** A QR generator's
`rememberQrCodePainter(data = "…")` is the canonical case: four overloads, two of which are fully
defaulted, so the call cannot resolve. Read the overload list from the sources jar and call the
overload with the explicit parameters (`rememberQrCodePainter(data, options)`) rather than relying
on defaults to disambiguate. Prefer the fully-explicit arity whenever a library's overloads look
interchangeable.

## Compile traps — every one of these compiles clean in the head and fails the build

- **A public `inline` function cannot touch `private` members.** `suspend inline fun <reified T> get()`
  calling a `private suspend fun execute()` fails with "public-API inline function cannot access
  non-public-API". Mark the callee `@PublishedApi internal`, or make the wrapper non-inline and take
  a `KClass`/serializer. `@PublishedApi internal` is the small change that keeps the reified ergonomics.
- **`maxOf` / `minOf` need both operands the same type.** `maxOf(unitPrice * qty - discount, 0)`
  where the first operand is `Long` fails ("none of the following candidates is applicable"); write
  `0L`. Same for `maxOf(0, discount)` in a `Long` context. Mixed `Int`/`Long` literals are the most
  common Kotlin compile error in money code — be deliberate with the `L` suffix everywhere a value
  is money.
- **`lightColorScheme` / `darkColorScheme` no longer take `surfaceVariant`** in recent Material3.
  Passing it fails the build; drop it and use `onSurfaceVariant` (still present).
- **`expect`/`actual` must be paired exactly.** Every `expect fun` / `expect val` in `commonMain`
  needs an `actual` in **each** platform source set. Verify mechanically before compiling:
  `grep -rn '^expect' --include='*.kt' .` vs `grep -rn '^actual' --include='*.kt' .` — counts must
  match per declaration.
- **`androidMain` needs an `Application` to hand the context to `actual fun createSecureStorage()`.**
  Hold the `Application` in a `lateinit var` set from `Application.onCreate()`; an `expect fun` with
  no parameter cannot receive `Context`.

## iOS Keychain interop — the hardest part of KMP

Building a `CFDictionary` for `SecItemAdd`/`SecItemCopyMatching` **does not work** by casting a
Kotlin `mapOf(...)` to `CFDictionaryRef`. That compiles and crashes/misbehaves at runtime. Use the
pattern proven in `multiplatform-settings` (Apache-2.0): build the dictionary with
`CFDictionaryCreate` over `allocArrayOf(*keys)` / `allocArrayOf(*values)` with `reinterpret()`, and
manage lifetimes with `CFBridgingRetain` / `CFBridgingRelease` in a `memScoped` block.

```kotlin
@OptIn(ExperimentalForeignApi::class)
private fun MemScope.cfDictionaryOf(map: Map<CFStringRef?, CFTypeRef?>): CFDictionaryRef? {
    val keys = allocArrayOf(*map.keys.toTypedArray())
    val values = allocArrayOf(*map.values.toTypedArray())
    return CFDictionaryCreate(
        kCFAllocatorDefault, keys.reinterpret(), values.reinterpret(),
        map.size.convert(), null, null,
    )
}
```

Then `SecItemAdd` on write (fall back to `SecItemUpdate` on `errSecDuplicateItem`), and
`SecItemCopyMatching` with `kSecReturnData = kCFBooleanTrue` on read, converting the `NSData` via
`NSString.create(data, NSUTF8StringEncoding)`. Read the reference implementation before writing this
by hand — it is the one part of the scaffold that cannot be guessed and cannot be tested off macOS.

## CI for a KMP project

`.github/workflows/ci.yml` with three jobs: `test` (`:composeApp:testDebugUnitTest`), `build-android`
(`:composeApp:assembleDebug` + upload the APK), and a cheap `secrets` job that greps tracked files
for `.env` / `*.jks` / `*.keystore` / `google-services.json` / `GoogleService-Info.plist` and fails
if any are committed. Cache `~/.konan` keyed on `libs.versions.toml`. The iOS framework build needs
macOS runners — keep it out of the default workflow unless required.

## Install the Gradle wrapper without running Gradle

A no-build host still wants a wrapper, so the first local command is `./gradlew …` rather than a
manual `gradle wrapper` step — and `gradle wrapper` is usually unavailable in exactly this situation
(the host forbids Gradle, or the system `gradle` is too old to generate a modern wrapper). Fetch the
three official files from the Gradle repo **tag** and pin the distribution checksum:

```bash
V=8.13.0   # the Gradle release tag, matching the AGP's required Gradle
mkdir -p gradle/wrapper
curl -sSL -o gradlew      "https://raw.githubusercontent.com/gradle/gradle/v$V/gradlew"
curl -sSL -o gradlew.bat  "https://raw.githubusercontent.com/gradle/gradle/v$V/gradlew.bat"
curl -sSL -o gradle/wrapper/gradle-wrapper.jar \
  "https://raw.githubusercontent.com/gradle/gradle/v$V/gradle/wrapper/gradle-wrapper.jar"
chmod +x gradlew
```

```properties
# gradle/wrapper/gradle-wrapper.properties
distributionUrl=https\://services.gradle.org/distributions/gradle-8.13-bin.zip
distributionSha256Sum=<the official gradle-8.13-bin.zip.sha256>
validateDistributionUrl=true
```

Two cheap verifications, both necessary:

```bash
unzip -l gradle/wrapper/gradle-wrapper.jar | grep GradleWrapperMain  # must print the .class
./gradlew --version                                                   # resolves, compiles nothing
```

`./gradlew --version` is safe even where a build is forbidden — it downloads the distribution and
prints the version with no compilation — but run `./gradlew --stop` afterwards so the daemon does not
stay parked on a shared low-RAM host.

## Honest handoff when the project has never been built

The build is forbidden on a shared low-RAM host, so a KMP scaffold is written, not compiled. Say so:

- files written, **nothing compiled**; the Gradle wrapper CAN be installed without building (see
  "Install the Gradle wrapper without running Gradle" above), so the handoff can ship a repo whose
  first local command is `./gradlew …` instead of a manual `gradle wrapper` step;
- **iOS Keychain + `MainViewController()` must be tested on macOS** — they cannot be verified on Linux;
- versions in `libs.versions.toml` are verified against release pages but **not** resolved by a real build;
- prove the pure logic you CAN: port the money/parsing functions to Python and run the same assertions.
  Report it as "logic proven via Python port, Kotlin not compiled" — never as "tests pass".
