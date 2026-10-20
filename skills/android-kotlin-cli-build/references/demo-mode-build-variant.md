# Demo / offline mode as a SEPARATE build variant

Use when a money-handling app must be try-able before its backend exists — the user
wants to install it and click through, but there is no server to log into yet.

## The trap

Turning on demo behaviour in the existing `release` build is the obvious move and it
is wrong: the artifact you hand out is then the same artifact a real shop installs,
and it carries a path that marks orders paid with no server involved. For an app that
handles money that is a backdoor, not a feature.

Turning it on only in `debug` is also wrong — the APK you publish is usually the
`release` one, so the demo build never reaches the user's phone and the login screen
still fails.

## The shape that works

A **third build type** that is production-grade except for the demo flag:

```kotlin
android {
    buildFeatures { buildConfig = true }   // required; AGP 8+ no longer emits BuildConfig by default

    buildTypes {
        getByName("release") {
            isMinifyEnabled = true
            isShrinkResources = true
            buildConfigField("boolean", "DEMO_MODE", "false")
        }
        getByName("debug") {
            buildConfigField("boolean", "DEMO_MODE", "true")
        }
        create("demo") {
            initWith(getByName("release"))      // same R8/shrink as production
            signingConfig = signingConfigs.findByName("release")
            buildConfigField("boolean", "DEMO_MODE", "true")
            applicationIdSuffix = ".demo"       // installs side by side with production
            versionNameSuffix = "-demo"
            manifestPlaceholders["appLabel"] = "<App> (Demo)"   // user can tell them apart
        }
    }
}
```

- `applicationIdSuffix` means both APKs can be installed on one phone; the user can
  compare without uninstalling.
- `versionNameSuffix` + a distinct launcher label stop the demo from being mistaken
  for the real app.
- Keep `initWith(release)` so the demo is measured against the same R8 pipeline — a
  demo that is not obfuscated proves nothing about the release path.

## Gate the demo behind ONE flag read in ONE place

Do not sprinkle `if (demo)` through the UI. Route it through the app's normal
interfaces so the production path is byte-for-byte unchanged:

```kotlin
// commonMain — the flag is the ONLY difference
interface SalesGateway { suspend fun createSale(...): SaleOrder /* ... */ }
class SalesApi(...) : SalesGateway              // real HTTP
class DemoSalesGateway(...) : SalesGateway      // in-memory, seeded samples
```

Then `App.kt` picks the implementation once, and shows a permanent banner the user
cannot dismiss while in demo. The bonus is real: the controller becomes testable
without a network, because it depends on the interface, not the HTTP class.

## Verify the gate — inspect the SHIPPED dex, not the source

R8 obfuscates class names, so a source-level check proves nothing. Prove the demo
code is **absent from the release artifact** by grepping for a string literal that
cannot be renamed:

```bash
cd /tmp && rm -rf dx && mkdir dx && cd dx
unzip -o -q /path/to/app-release.apk 'classes*.dex'
strings classes*.dex | grep -E 'BUKAN-UNTUK-BAYAR|Toko Demo|demo-access-token'
# demo APK   -> matches present
# release APK-> ZERO matches
```

Pair this with a CI step that reads `BuildConfig` in both variants and **fails** when
`DEMO_MODE` is true for release. A build-config gate catches the mistake at build
time; the dex grep proves what actually shipped.

**Expect the two APKs to differ by only a few bytes.** Compressed dex can make the
demo artifact the same size as production. Size is not evidence — the string grep is.

## Do not report the demo as tested on a device

Matching strings and a green CI prove the gate works. They do not prove the demo
login-to-cashier flow runs on real hardware. Say which one you proved.
