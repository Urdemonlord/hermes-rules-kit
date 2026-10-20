# Compose + Hilt + Room project scaffold (headless, verified)

A full modern Android project — version catalog, Compose, Hilt, Room, KSP, adaptive icon, CI —
built end-to-end on a headless 2 vCPU / 3.6 GB VPS. Use this as the known-good starting point
instead of rediscovering the version matrix. Pair with `scripts/scaffold-minimal-android-app.sh`
when you only need a throwaway APK.

## Verified version matrix

These versions were confirmed present in their repositories and built together successfully.
Re-probe before reuse if time has passed (see the SKILL.md pitfall on the right Maven repo).

| Component | Version | Repository |
|---|---|---|
| AGP | 8.7.3 | Google Maven |
| Kotlin | 2.0.21 | Maven Central |
| KSP | 2.0.21-1.0.28 | Maven Central |
| Hilt | 2.52 | Maven Central |
| Room | 2.6.1 | Google Maven |
| Media3 | 1.5.1 | Google Maven |
| Compose BOM | 2024.12.01 | Google Maven |
| activity-compose | 1.9.3 | Google Maven |
| navigation-compose | 2.8.5 | Google Maven |
| lifecycle | 2.8.7 | Google Maven |
| hilt-navigation-compose | 1.2.0 | Google Maven |
| Coil | 2.7.0 | Maven Central |
| datastore-preferences | 1.1.1 | Google Maven |
| kotlinx-serialization-json | 1.7.3 | Maven Central |
| Gradle (wrapper) | 8.11.1 | services.gradle.org |
| compileSdk / targetSdk | 35 | — |
| minSdk | 26 | — |
| JDK | 17 (source/target), 21 runtime is fine | — |

**KSP version must be `<kotlin-version>-<ksp-version>`** and match Kotlin exactly. A mismatch is a
hard build failure, not a warning.

## `gradle.properties` (the low-RAM profile that worked)

```properties
org.gradle.jvmargs=-Xmx1536m -XX:MaxMetaspaceSize=512m -Dfile.encoding=UTF-8
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configuration-cache=true
kotlin.code.style=official
kotlin.daemon.jvmargs=-Xmx1024m
android.useAndroidX=true
android.nonTransitiveRClass=true
```

## `settings.gradle.kts`

```kotlin
pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://jitpack.io") }   // only if you need JitPack-hosted libs
    }
}
rootProject.name = "YourApp"
include(":app")
```

## `app/build.gradle.kts` — the parts that matter

```kotlin
android {
    namespace = "com.example.app"
    compileSdk = 35
    defaultConfig {
        minSdk = 26
        targetSdk = 35
        vectorDrawables { useSupportLibrary = true }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
        freeCompilerArgs += listOf("-opt-in=kotlin.RequiresOptIn")
    }
    buildFeatures { compose = true }
}

// Room: persist schema to version control so migrations are reviewable.
ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
    arg("room.incremental", "true")
}
```

Plugins needed: `com.android.application`, `org.jetbrains.kotlin.android`,
`org.jetbrains.kotlin.plugin.compose`, `org.jetbrains.kotlin.plugin.serialization`,
`com.google.devtools.ksp`, `com.google.dagger.hilt.android`.

`local.properties` must contain `sdk.dir=<absolute path to ANDROID_HOME>` (gitignored).

## Room: the empty-database trap

`@Database(entities = [])` **fails KSP** with "must specify list of entities". You cannot scaffold
an empty Room database as a placeholder to prove the wiring compiles. Write at least one real
entity up front.

**Never use `fallbackToDestructiveMigration()` once the app stores user data** (a scanned library,
playlists) — it silently wipes it on the next version bump. Write an explicit `Migration` and
register it with `.addMigrations(...)`. Its SQL must byte-match Room's generated DDL or schema
validation fails **at runtime**, not at build time; copy the `createSql` entries out of the
generated `app/schemas/<version>.json`. See `references/media3-playback-service.md` for the
playback-service integration layer.

```kotlin
@Database(entities = [SongEntity::class], version = 1, exportSchema = true)
abstract class AppDatabase : RoomDatabase() {
    abstract fun songDao(): SongDao
    companion object { const val NAME = "app.db" }
}
```

Provide it through Hilt with `@ApplicationContext` + `Room.databaseBuilder(...)`. Commit the
generated `app/schemas/**.json` — it is the migration contract.

## Bundling fonts (no Roboto)

Download variable TTFs into `app/src/main/res/font/` (lowercase, `[a-z0-9_]` only — the resource
name is the filename). Google Fonts variable files are OFL, so bundling is fine. Example sources:

```bash
curl -sL -o app/src/main/res/font/manrope_variable.ttf \
  "https://github.com/google/fonts/raw/main/ofl/manrope/Manrope%5Bwght%5D.ttf"
```

```kotlin
val ManropeFamily = FontFamily(
    Font(R.font.manrope_variable, weight = FontWeight.Normal),
    Font(R.font.manrope_variable, weight = FontWeight.SemiBold),
    Font(R.font.manrope_variable, weight = FontWeight.Bold),
)
```

**Variable-font caveat:** listing the same file at multiple `weight` values may render every
weight identically on some devices. If that happens, switch to
`FontVariation.Settings(FontVariation.weight(n))`. It is a cosmetic issue, never a build blocker —
note it and move on rather than blocking the build.

## Adaptive launcher icon without any copyrighted asset

Draw it as a vector instead of shipping a PNG. Five rotated petals + a centre circle is a few
lines of `<path>` with `android:rotation` / `android:pivotX|Y`, referenced from
`mipmap-anydpi-v26/ic_launcher.xml`:

```xml
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/brand_elevated" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <monochrome android:drawable="@drawable/ic_launcher_foreground" />
</adaptive-icon>
```

Keep colours in one `res/values/colors.xml` that mirrors the Compose colour object, and say so in
both files — two sources of truth for the palette drift otherwise.

## Dark-only theme (skip dynamic colour)

If the brand depends on a specific palette, do **not** use Material You / dynamic colour — the
system wallpaper colour will overwrite the identity. Pass a fixed `darkColorScheme(...)` and
ignore `isSystemInDarkTheme()`:

```kotlin
@Composable
fun AppTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = FixedDarkScheme, typography = AppTypography, shapes = AppShapes, content = content)
}
```

Also set the XML theme's `windowBackground` to the dark colour so there is no white flash before
Compose composes, and `enableEdgeToEdge()` in the activity.

## CI workflow (build off-box when the artifact is the deliverable)

```yaml
- uses: actions/setup-java@v4
  with: { distribution: temurin, java-version: '17' }
- uses: gradle/actions/setup-gradle@v4
- run: chmod +x ./gradlew
- run: ./gradlew assembleDebug --stacktrace
- uses: actions/upload-artifact@v4
  with: { name: apk, path: app/build/outputs/apk/debug/*.apk, if-no-files-found: error }
```

## Verification after a successful build

```bash
APK=app/build/outputs/apk/debug/app-debug.apk
$ANDROID_HOME/build-tools/35.0.1/aapt2 dump badging "$APK" | grep -E '^package|launchable-activity'
unzip -l "$APK" | grep -E 'classes.dex|res/font/'
find app/schemas -name '*.json'
```

`classes.dex` proves Kotlin compiled through to DEX; `res/font/*.ttf` proves the fonts were
bundled; a schema JSON proves Room processed. A bare "BUILD SUCCESSFUL" proves none of these.

## Measured timings (2 vCPU, 3.6 GB RAM, ~1 GB free)

| Build | Time |
|---|---|
| First (cold, downloads all dependencies) | ~7m 45s |
| Second (warm cache, code change only) | ~2m 26s |
| Minimal single-module app, cold | ~3m 29s |

Debug APK size for this stack: ~22 MB (not minified). Expect it to drop sharply with R8 in a
release build.
