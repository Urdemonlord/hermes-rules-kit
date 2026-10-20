# Release signing with the keystore held by CI, not the user

Use when a release APK must be installable but **the user has no keystore** — or when a project is
currently shipping `app-debug.apk` / `*-release-unsigned.apk` because nobody ever created one.

The goal is a signed release APK where the user never handles the keystore file at all: it lives in
CI secrets, the build reads it from the environment, and a verification step proves the artifact is
signed before anyone is told to install it.

## Why NOT to copy the "commit a debug keystore" shortcut

A personal media app can get away with committing a fixed `debug.keystore` and signing release with
it — it is the cheapest way to keep a stable signature so updates install over the old version. Do
NOT extend that pattern to an app that handles money, credentials, or merchant data:

| | debug keystore in repo | real release keystore |
|---|---|---|
| `debuggable` | **true** | false |
| password | `android` (public, default) | strong, generated |
| `run-as <pkg>` from a USB-connected host | works — reads stored tokens | denied |
| APK size | un-minified, much larger | R8/shrink applied |

`debuggable=true` is the disqualifier: anyone with adb can attach and read whatever the app stores.
Say this plainly when the user asks for "the same as <other app>" — the shape is worth copying, the
debug key is not.

## 1. Generate the keystore on the server, and never print the password

```bash
D=~/.<project>-release; mkdir -p "$D"; chmod 700 "$D"
PW=$(python3 -c 'import secrets,string;a=string.ascii_letters+string.digits;print("".join(secrets.choice(a) for _ in range(40)))')
printf '%s\n' "$PW" > "$D/password.txt"; chmod 600 "$D/password.txt"   # write BEFORE keytool, so a failure cannot lose it
keytool -genkeypair -v -keystore "$D/release.jks" -alias <alias> \
  -keyalg RSA -keysize 4096 -validity 10000 \
  -storepass "$(cat "$D/password.txt")" -keypass "$(cat "$D/password.txt")" \
  -dname "CN=<App>, OU=<Org>, O=<Org>, L=<City>, ST=<Prov>, C=ID"
chmod 600 "$D/release.jks"
```

- **Use an alphanumeric-only password.** `keytool`/Gradle/shell/GitHub Secrets all round-trip it;
symbols invite quoting bugs for zero benefit at this length.
- **`-validity 10000` days (~27 years).** A keystore that expires inside the app's life is a
problem you cannot fix later without changing the signature.
- **Write the password to a `chmod 600` file first**, then pass it by `$(cat …)`. If the password
exists only in a shell variable and the call fails, it is gone.
- **Never echo the password.** Verify by file size / `keytool -list` output, and redact the password
string from any output you print.
- The **SHA-256 fingerprint is not a secret** — print and keep it. It is what you match against Play
Integrity and API-key restrictions later.

## 2. Read the signing config from the ENVIRONMENT, not `gradle.properties`

`gradle.properties` is committed to git, so a password there is a password in the repo (and in every
fork and CI log that echoes the file). Use environment variables and tolerate their absence:

```kotlin
android {
    val keystorePath = System.getenv("<PROJ>_KEYSTORE_PATH")
    val keystorePassword = System.getenv("<PROJ>_KEYSTORE_PASSWORD")
    val keyAlias = System.getenv("<PROJ>_KEY_ALIAS")
    val keyPassword = System.getenv("<PROJ>_KEY_PASSWORD")

    signingConfigs {
        if (keystorePath != null && keystorePassword != null && keyAlias != null && keyPassword != null) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = keystorePassword
                this.keyAlias = keyAlias
                this.keyPassword = keyPassword
                // v2/v3 only — see the enableV1Signing note below.
                enableV2Signing = true
                enableV3Signing = true
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release")
        }
    }
}
```

**The build must NOT fail when the secrets are absent.** Guard the `create("release")` block and let
`signingConfig` be null: a contributor or a fork without the keystore can still compile, and the job
stays green for them. The guarantee that the SHIPPED artifact is signed comes from the verification
step, not from this config. Make that trade explicit in a comment so the next reader does not "fix"
the guard.

**`enableV1Signing = true` is a no-op when `minSdk >= 24`** — AGP disables v1 itself. `apksigner
verify` on the built APK reports `Verified using v1 scheme (JAR signing): false` even though you set
it. Do not write a comment claiming v1 covers old devices unless minSdk is actually below 24; a
comment that describes behaviour that never happens is worse than no comment.

## 3. Pass the keystore through CI secrets, and stage it OUTSIDE the workspace

```bash
# one-time: single-line base64 so `base64 -d` on the runner round-trips exactly
base64 -w0 ~/.<project>-release/release.jks > /tmp/ks.b64 && chmod 600 /tmp/ks.b64
gh secret set <PROJ>_KEYSTORE_B64      < /tmp/ks.b64
gh secret set <PROJ>_KEYSTORE_PASSWORD < ~/.<project>-release/password.txt
gh secret set <PROJ>_KEY_ALIAS         --body <alias>
gh secret set <PROJ>_KEY_PASSWORD      < ~/.<project>-release/password.txt
rm -f /tmp/ks.b64
gh secret list        # prints NAMES + timestamps only, never values
```

In the workflow, expose them as job-level `env:` from `secrets`, then write the keystore to
`$RUNNER_TEMP` — **not** into the checkout, so it can never be committed or picked up by an artifact
upload glob:

```yaml
env:
  <PROJ>_KEYSTORE_B64: ${{ secrets.<PROJ>_KEYSTORE_B64 }}
  <PROJ>_KEYSTORE_PASSWORD: ${{ secrets.<PROJ>_KEYSTORE_PASSWORD }}
  <PROJ>_KEY_ALIAS: ${{ secrets.<PROJ>_KEY_ALIAS }}
  <PROJ>_KEY_PASSWORD: ${{ secrets.<PROJ>_KEY_PASSWORD }}
steps:
  - name: Siapkan keystore dari Secrets
    run: |
      set -e
      if [ -z "$<PROJ>_KEYSTORE_B64" ]; then
        echo "::warning::Rahasia keystore tidak ada — APK akan TANPA tanda tangan."
        echo "HAS_KEYSTORE=false" >> $GITHUB_ENV
        exit 0
      fi
      echo "$<PROJ>_KEYSTORE_B64" | base64 -d > "$RUNNER_TEMP/release.jks"
      echo "<PROJ>_KEYSTORE_PATH=$RUNNER_TEMP/release.jks" >> $GITHUB_ENV
      echo "HAS_KEYSTORE=true" >> $GITHUB_ENV
```

The `HAS_KEYSTORE` flag is what the verification step branches on — a bare `if [ -z … ]` in a later
step cannot see the secret unless it was re-exported, so carry the boolean through `$GITHUB_ENV`.

Also confirm `.gitignore` already covers `*.jks` / `*.keystore`, and prove it after pushing:

```bash
git ls-files | grep -iE '\.jks$|\.keystore$|password'   # must be empty
```

## 4. Verify the signature — filename is NOT evidence

An unsigned release is named `*-release-unsigned.apk` and a signed one is `*-release.apk`, but
**glob `*.apk` for both** and assert on the signature itself. A missing secret otherwise produces a
job that is green and an artifact that cannot be installed:

```yaml
  - name: Verifikasi APK benar-benar tertandatangani
    run: |
      set -e
      APK=$(find composeApp/build/outputs/apk/release -name '*.apk' | head -1)
      AAPT=$(find "$ANDROID_HOME/build-tools" -name aapt | sort -V | tail -1)
      if [ -n "$AAPT" ] && "$AAPT" dump badging "$APK" | grep -q 'application-debuggable'; then
        echo "::error::APK rilis debuggable — tidak boleh untuk aplikasi yang menangani uang."; exit 1
      fi
      if [ "$HAS_KEYSTORE" != "true" ]; then
        echo "::warning::Keystore tidak tersedia — APK ini TIDAK BISA DIINSTAL."
        exit 0
      fi
      APKSIGNER=$(find "$ANDROID_HOME/build-tools" -name apksigner | sort -V | tail -1)
      "$APKSIGNER" verify --verbose "$APK" || { echo "::error::Tanda tangan TIDAK VALID."; exit 1; }
      "$APKSIGNER" verify --print-certs "$APK" | grep -i 'SHA-256 digest' | head -1 >> $GITHUB_STEP_SUMMARY
```

- **Warn, do not fail, when the keystore is absent** — otherwise every fork/PR is permanently red for
a reason its author cannot fix.
- **Fail hard on `application-debuggable`** — that check needs no secret and catches the
debug-signed-release mistake regardless.
- Print the fingerprint into the step summary: it is the value you later match against Play Integrity.

## 5. Close out — and say what is still unproven

- Verify the **published** artifact, not the local one: download it over HTTPS and run
  `apksigner verify --print-certs` on the downloaded bytes.
- **The keystore file is a single point of failure.** Losing it means this app can never be updated
  again — Android refuses an APK signed with a different key. Tell the user to keep a copy off the
  VPS, and state the consequence in the report rather than burying it in a comment.
- Signing proves the APK is *installable*. It does not prove R8 kept the reflection-reached paths,
  nor that any runtime path works. Those still need a device run — say so.
