#!/usr/bin/env bash
# Scaffold a minimal, buildable Android (Kotlin) app from scratch on a headless host.
# Usage: scaffold-minimal-android-app.sh <outdir> <package.name> [compileSdk] [minSdk]
# Produces a project where `gradle :app:assembleDebug` yields a valid APK.
set -euo pipefail

OUT="${1:?usage: $0 <outdir> <package.name> [compileSdk] [minSdk]}"
PKG="${2:?usage: $0 <outdir> <package.name> [compileSdk] [minSdk]}"
COMPILE_SDK="${3:-35}"
MIN_SDK="${4:-26}"
AGP="8.7.3"
KOTLIN_PLUGIN="2.0.21"
PKG_PATH="${PKG//.//}"

mkdir -p "$OUT/app/src/main/kotlin/$PKG_PATH"

cat > "$OUT/settings.gradle.kts" <<'EOF'
pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "app"
include(":app")
EOF

cat > "$OUT/build.gradle.kts" <<EOF
plugins {
    id("com.android.application") version "$AGP" apply false
    id("org.jetbrains.kotlin.android") version "$KOTLIN_PLUGIN" apply false
}
EOF

# Low-RAM tuning is included by default; raise -Xmx only if the host has the RAM.
cat > "$OUT/gradle.properties" <<'EOF'
org.gradle.jvmargs=-Xmx1024m -XX:MaxMetaspaceSize=384m
org.gradle.daemon=false
org.gradle.parallel=false
kotlin.daemon.jvmargs=-Xmx768m
android.useAndroidX=true
android.nonTransitiveRClass=true
EOF

cat > "$OUT/app/build.gradle.kts" <<EOF
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "$PKG"
    compileSdk = $COMPILE_SDK
    defaultConfig {
        applicationId = "$PKG"
        minSdk = $MIN_SDK
        targetSdk = $COMPILE_SDK
        versionCode = 1
        versionName = "1.0"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
EOF

cat > "$OUT/app/src/main/AndroidManifest.xml" <<EOF
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application android:label="App">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
EOF

cat > "$OUT/app/src/main/kotlin/$PKG_PATH/MainActivity.kt" <<EOF
package $PKG

import android.app.Activity
import android.os.Bundle

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
    }
}
EOF

# sdk.dir must be absolute; ANDROID_HOME env is the fallback.
if [ -n "${ANDROID_HOME:-}" ]; then
  echo "sdk.dir=$ANDROID_HOME" > "$OUT/local.properties"
fi

echo "Scaffolded Android app at: $OUT"
echo "Build:  cd $OUT && ANDROID_HOME=\$ANDROID_HOME gradle :app:assembleDebug"
echo "Output: $OUT/app/build/outputs/apk/debug/app-debug.apk"
