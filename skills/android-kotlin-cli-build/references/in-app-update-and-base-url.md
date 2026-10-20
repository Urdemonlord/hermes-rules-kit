# Shipping a change to the API base URL an installed app already uses

Use when the app's server address changes (wrong host, migrated backend, new subdomain) or when a
release must be pushed to users who already have an older build installed.

## Bump `versionCode`, or the fix never reaches anyone

An in-app updater compares `versionCode`, not `versionName`. Republishing the same code with new
content produces a file nobody is offered, because the app believes it is already current:

```kotlin
android { defaultConfig { versionCode = 2; versionName = "0.1.1" } }
```

**A shipped build pointing at the wrong host is a live defect, not a cosmetic one.** If the old
constant pointed at a host owned by another service, every user's login is being posted to a third
party. Bumping the code is the only way that installed copy learns it must update — state the reason
in the commit message so a later reader does not "tidy" the number back down.

Keep `versionCode`/`versionName` in exactly one place (the Gradle file) and have the publish script
read them from there. Two sources drift, and the manifest then advertises a version whose APK does
not exist.

## Verify the new address is actually inside the built APK

A green build does not mean the constant changed — a stale string resource, an untouched generated
file, or a build that silently reused a cached artifact all produce a plausible APK. Read the string
out of the dex and assert the old host is gone:

```bash
unzip -o -q app-release.apk 'classes*.dex'
strings classes*.dex | grep -oE 'https://[a-z.-]*<domain>[a-z./-]*' | sort -u
strings classes*.dex | grep -c '<old-host>'      # must be 0
```

`strings` on the dex is enough because R8 keeps string constants; you do not need a decompiler for
this. Do it on the artifact you are about to publish, and again on the bytes downloaded over HTTPS.

**Identical file size to the previous release is not proof the build is stale** — a one-string change
can land on the same byte count. Check the string, not the size, before concluding anything either
way.

## Serve the API from a path when the subdomain is not available yet

Waiting on DNS blocks the whole release. If a domain already resolves to the host and has a valid
certificate, serve the API under a path on it and strip the prefix in the proxy, so the paths inside
the app stay exactly as they were:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:3010/;   # trailing slash strips /api/ before forwarding
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

```kotlin
const val BASE_URL = "https://<domain>/api"   // -> /auth/login, /sales/create unchanged
```

This keeps the migration to a real subdomain later a one-line change in the client. Do not instead
rewrite the in-app paths to carry a prefix — that breaks the frozen contract the backend must match.

## The publish script must refuse a mismatched variant

With a demo build and a real build sharing a pipeline, the expensive mistake is publishing the wrong
one. Read the `applicationId` back out of the artifact you are about to serve and compare it against
the variant that was requested:

```bash
PKG=$("$AAPT" dump badging "$APK" | grep -oP "^package: name='\K[^']+")
case "$VARIANT" in
  release) EXPECTED="id.<app>"      ;;
  demo)    EXPECTED="id.<app>.demo" ;;
esac
[[ "$PKG" == "$EXPECTED" ]] || { echo "Varian tidak cocok: $PKG"; exit 1; }
```

Check it on the **downloaded** copy, not the local file — the local file proves what you built, the
served bytes prove what users receive.

## A release `applicationId` with a `.debug` suffix may be deliberate — do not "fix" it

A release build whose package is `com.<app>.debug` looks like a leaked debug config. It can be the
opposite: a deliberate way to keep one identity across every build type. Android treats a changed
`applicationId` as a **different app**, so "correcting" it forces every installed user to reinstall
from scratch and lose their data and their library scan.

```kotlin
buildTypes {
    debug   { applicationIdSuffix = ".debug" }
    release { applicationIdSuffix = ".debug" }   // same identity on purpose
}
```

The invariant that makes it work is the signing key: same package **and** same certificate means an
in-place update. Changing either alone breaks the update path. Before treating the suffix as a bug,
read the comment in `build.gradle.kts` and confirm the digests still match across releases:

```bash
"$BT"/aapt2 dump badging "$APK" | grep -oP "^package: name='\K[^']+"
"$BT"/apksigner verify --print-certs "$APK" | grep -i 'SHA-256'
# the SHA-256 must be IDENTICAL to the previously published release
```

## Close out honestly

A published APK that installs is not an APK that works. Until someone logs in on a real device
against the real backend, report it as "published, not yet exercised" — and if the client/server
contract has not been compared field by field, say the app is not expected to log in at all yet.
