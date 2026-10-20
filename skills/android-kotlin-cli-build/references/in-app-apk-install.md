# In-app APK download, verification, and install

The follow-on to `sideloaded-app-update-checker.md` once the user wants the update installed from
inside the app instead of handed to a browser. Split into three classes so each has one job:
download (network + progress), digest (verification), install (system hand-off). A combined class
cannot be unit tested without a device, and the verification is the part most worth testing.

## Two manifest facts make this path exist — the class alone is dead code

Nothing works until both are present, and their absence is invisible at compile time.

```xml
<uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />
...
<provider
    android:name="androidx.core.content.FileProvider"
    android:authorities="${applicationId}.fileprovider"
    android:exported="false"
    android:grantUriPermissions="true">
    <meta-data
        android:name="android.support.FILE_PROVIDER_PATHS"
        android:resource="@xml/file_paths" />
</provider>
```

`REQUEST_INSTALL_PACKAGES` has no runtime prompt — the system shows its own consent screen the
first time your intent fires, so nothing is requested while the user only reads the dialog. A build
that ships the permission without ever calling the installer asks for nothing, which is the point.

**`${applicationId}` in the authority, never the literal package name.** A debug build carrying
`applicationIdSuffix = ".debug"` resolves the authority to `…debug.fileprovider`, and `install()`
builds the string from `BuildConfig.APPLICATION_ID` — so the two match automatically. A literal
package in the manifest gives the release build the right authority and the debug build an
`IllegalArgumentException` from `FileProvider`.

## Scope `file_paths.xml` to the one file, not to storage

An APK in `cacheDir` cannot be installed by path: the installer is a different process with no
access to your app's private directory. `FileProvider` is the bridge, and its path config is the
place a shortcut becomes a vulnerability. Allow exactly the one filename:

```xml
<paths>
    <cache-path name="update_apk" path="update.apk" />
</paths>
```

No `<root-path>`, no `<external-path>` — those hand a read grant over the user's whole storage to
whichever process the intent reaches. Keep the download in `cacheDir` (not public Downloads) for
the same reason: the APK is an installer, not user content, and it should not be tappable in a file
manager if the install is abandoned. Delete the partial file on every failure path, including
cancellation — a half-written APK left behind can hash-match nothing but looks installable.

## Verify the digest, and make the success branch not carry a flag

Compute SHA-256 of the downloaded file and compare before handing it to the installer. Keep the
helper pure JVM (`java.security.MessageDigest` + `java.io.File`) so it runs in a plain unit test
with no device — that test is the only automated proof that your integrity check works:

```kotlin
fun matches(file: File, expectedSha256: String): Boolean {
    val expected = expectedSha256.trim()
    if (expected.isEmpty()) return false
    return of(file).equals(expected, ignoreCase = true)
}
```

Trim and ignore case: the value is copied out of `sha256sum` output or the generated manifest, and
a correct digest must not be rejected over formatting. Reject an empty expected value rather than
treating it as a match.

**Return the failure as its own state, not as a `verified = false` flag on a success result.** The
two cases need different handling — a bad digest means delete and retry, an unverified success
means "no manifest digest to check against" (an older `update.json`) — and a boolean merges them
into a branch every caller has to remember to handle. Once failure is its own result, a
`verified` field on the success type is dead weight: the value is constant. Drop it.

Report progress with `(downloaded, total)` and let `total == -1` mean the server sent no
`Content-Length`; a dialog with no progress on a slow link reads as a hang and gets dismissed
mid-download.

## The install hand-off

```kotlin
val uri = FileProvider.getUriForFile(context, "${BuildConfig.APPLICATION_ID}.fileprovider", apk)
context.startActivity(
    Intent(Intent.ACTION_INSTALL_PACKAGE).apply {
        setDataAndType(uri, "application/vnd.android.package-archive")
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)          // required: context is not an Activity
    }
)
```

`BuildConfig` needs its own import — a file that reaches for `BuildConfig.APPLICATION_ID` without
`import com.<app>.BuildConfig` is an unresolved reference the moment you compile, so check the
imports when you read in a class written in an earlier session.

Wrap the call site in `runCatching`: if no activity handles the intent, dismissing the dialog is
fine and crashing is not.

## Report progress as UI state, and delete the file when the ViewModel dies

Keep the download's state in a sealed interface next to (not merged into) the check state — the
check finishes in seconds, the download runs for tens of seconds, and a dialog the user can close
must not reset an in-flight download:

```kotlin
sealed interface DownloadState {
    data object Idle : DownloadState
    data class Downloading(val downloaded: Long, val total: Long) : DownloadState
    data class Ready(val file: File) : DownloadState
    data class Failed(val message: String) : DownloadState
}
```

One confirm button whose contents follow the state (Download → Cancel → Install) is clearer than
three buttons whose meanings shift. Delete the APK in `onCleared()`; cache eviction is not prompt
enough, and 5 MB sitting in cache forever is a real cost on a phone.

## What only a device can verify

The permission consent screen and the system installer dialog. Everything else — compile, unit
tests, `aapt2 dump badging` for the permission, `unzip -l app.apk` for `res/xml/file_paths.xml` —
runs headless. Say which of those you ran before describing the feature as working.