# Offline download of streamed tracks (WorkManager -> public Music folder)

Depth for making a streaming track playable offline: fetch the bytes once, park them somewhere the
user's other players can see, mark the row as downloaded, and make playback prefer the local file.
Assumes the app already has a stream resolver (see `references/streaming-extractor-integration.md`)
and a MediaStore scanner (see `references/media3-playback-service.md`).

## Pre-flight: verify the WorkManager / Hilt artifact BEFORE writing against it

Two assumptions that look obvious and are wrong, both caught only by reading the artifact:

| Assumption | Reality (verified from bytecode) |
|---|---|
| `CoroutineWorker` lives in `work-runtime-ktx` | It is in **`work-runtime`**. `work-ktx` is now a near-empty shim (one 199-byte `classes.jar`) — depending on it alone gives "unresolved reference: CoroutineWorker". |
| `EntryPointAccessors` is in `dagger.hilt` | It is in **`dagger.hilt.android`**. |
| `@HiltWorker` is available for a Worker with injected deps | Not present in the hilt-work artifact that was checked. Do not plan on it. |

Download the artifact and read it, exactly as for the extractor jar:

```bash
# androidx / WorkManager -> Google Maven; Hilt -> Maven Central (Hilt is NOT on Google Maven).
curl -sL -o /tmp/wm.aar "https://dl.google.com/dl/android/maven2/androidx/work/work-runtime/<VER>/work-runtime-<VER>.aar"
mkdir -p /tmp/wm && unzip -q -o /tmp/wm.aar -d /tmp/wm && unzip -q -o /tmp/wm/classes.jar -d /tmp/wmx
javap -classpath /tmp/wmx androidx.work.CoroutineWorker | head
```

**The Hilt-without-`@HiltWorker` route: `@EntryPoint` + `EntryPointAccessors.fromApplication`.**
Declare an `@EntryPoint` interface carrying the deps the Worker needs, read it from the
application context inside the Worker, and construct the Worker by hand. This needs no
`hilt-work`, no custom `WorkerFactory`, and no manifest change — the same result as the
`@HiltWorker` path with fewer moving parts. Prefer it whenever `@HiltWorker` is not provably present.
The gate that proves the entry point is wired is the **Hilt Java step**, not just the Kotlin compile:
`:app:hiltJavaCompileDebug` runs the annotation processor and fails if the `@EntryPoint` interface is
malformed, so include it in the local gate rather than waiting for CI.

## Where the file goes: the public Music folder, via MediaStore

The user's choice of "a folder other players also see" decides the mechanism: write through
`MediaStore`, not to app-private storage.

- **API 29+**: insert into `MediaStore.Audio.Media.EXTERNAL_CONTENT_URI` with
  `RELATIVE_PATH = Environment.DIRECTORY_MUSIC + "/<AppFolder>"` and
  `IS_PENDING = 1`, stream the bytes to the returned `openOutputStream(uri)`, then set
  `IS_PENDING = 0`. The pending flag is what keeps a half-written file out of the user's library.
- **API 26–28**: write the file into the public dir directly and then tell the system about it with
  `MediaScannerConnection.scanFile(context, arrayOf(path), null, null)` — without the scan the file
  exists but no player (including this app) sees it.
- **Permission**: `WRITE_EXTERNAL_STORAGE` is needed only up to API 28 (`maxSdkVersion="28"`); on
  29+ the MediaStore insert is the permission. Declaring it unconditionally trips lint.

**Ownership: a MediaStore row the app inserts is owned by that app (`owner_package_name`), and the
system deletes those files when the app is uninstalled (API 29+).** The file is visible to other
players and sits in the public Music folder, but it is not independent of the app — an uninstall
removes the downloads with it. So never write a user-facing claim that downloaded music survives an
uninstall without verifying it against the platform: this is a claim about data the user will plan
around, and stating it backwards loses their library with no warning. When the requirement really is
"survives uninstall", say plainly that this design does not provide it instead of implying it does.

## The filename rule is a pure function — unit-test it, never inline it

Sanitising "Artist - Title" into a legal filename is string logic with silent-failure edge cases
(path separators, control chars, reserved names, length caps), so it follows the repo's standing
pattern: extract it as a plain `internal fun` with no Android types and cover it with
`testDebugUnitTest`. Rules that need a test each: strip/replace `\ / : * ? " < > |`; replace
control characters (`< 0x20`, `0x7F`); collapse runs of whitespace; cap the stem length so the
result plus extension stays under the filesystem limit; never return an empty stem.

## The downloader: copy bytes, share the headers, delete the partial on failure

- **Reuse the SAME request headers the playback path uses.** A download is a fetch of the same
  `videoplayback` URL, so it hits the identical User-Agent-binding trap (403) described in
  `references/streaming-extractor-integration.md`. Extract the header map into one shared constant
  (e.g. `StreamRequestHeaders`) and reference it from both the resolver and the downloader — two
  separately-maintained header maps is the bug.
- **Resolve URL and file format in ONE call.** If the resolver exposes `resolveUrl()` and
  `resolveFormat()` separately, a download calls it twice and pays two network round-trips (and can
  get two different stream choices). Return URL + suffix + mime from a single `resolveAudio()`.
- **On any failure, delete the partial file.** A truncated audio file left in the public Music
  folder is indexed by the scanner and plays as a broken track forever. Wrap the copy so the
  failure path removes what it wrote.

## Which stream to DOWNLOAD is a different choice from which stream to PLAY

**Symptom:** the download fails and the menu shows a raw platform message naming a container —
`Unsupported MIME type audio/webm` (or any `audio/<container>`). The string exists nowhere in the
app's own source, because `MediaStore` throws it.

**Mechanism.** `MediaProvider` refuses a `MediaStore.Audio` insert whose MIME has no extension
mapping in Android's MIME table:

```java
// MediaProvider.java
if (mimeType != null &&
        MimeTypeMap.getSingleton().getExtensionFromMimeType(mimeType) == null) {
    throw new IllegalArgumentException("Unsupported MIME type " + mimeType);
}
```

The table maps `webm` only to `video/webm`; `audio/webm` has no extension at all, so
`MediaStore.Audio` rejects it. This is not a bug in the app's MIME handling — the platform is
refusing a container it cannot name.

**Why it hits MOST tracks, not an edge case.** The default quality picks the HIGHEST bitrate, and
the best audio track from YouTube is usually Opus in a WebM container. So the "best" choice is
exactly the one MediaStore rejects: the download path selected a stream that could never be
written. Read it as a design error (one selection rule used for two different jobs), not a typo.

**The rule: playback and download select on different criteria.** Playback takes any container
(ExoPlayer sniffs the bytes and plays WebM fine); download takes only containers MediaStore can
name, because the file is written as a `MediaStore.Audio` row. Keep the bitrate rule in ONE shared
selector and layer a storable-container filter on top, injecting the predicate so the decision
stays testable on the JVM:

```kotlin
object DownloadAudioSelector {
    fun chooseIndex(
        tracks: List<AudioTrackOption>,      // bitrate + mime
        maxBitrateBps: Int,
        isStorable: (String) -> Boolean,
    ): Int? {
        val storable = tracks.withIndex().filter { isStorable(it.value.mimeType) }
        if (storable.isEmpty()) return null
        val local = AudioStreamSelector.chooseIndex(   // same bitrate rule, NOT rewritten
            bitrates = storable.map { it.value.bitrateBps },
            maxBitrateBps = maxBitrateBps,
        ) ?: return null
        return storable[local].index                   // back to the ORIGINAL list
    }
}
```

The production predicate must MIRROR MediaProvider's own check — use the same API
(`android.webkit.MimeTypeMap`), not a hand-rolled allowlist that can drift from the platform:

```kotlin
fun isStorableAudioMime(mimeType: String): Boolean =
    mimeType.startsWith("audio/", ignoreCase = true) &&
        MimeTypeMap.getSingleton().getExtensionFromMimeType(mimeType) != null
```

Wire it through the resolver as a parameter with an accept-all default, so playback is untouched and
only the download path passes the filter:

```kotlin
fun resolveAudio(videoId, quality = DEFAULT, isStorable: (String) -> Boolean = { true })
// downloader:  resolveAudio(videoId, isStorable = storage::isStorableAudioMime)
// playback:    resolveAudio(videoId)   // unchanged
```

**Two traps that turn this fix into a NEW bug:**
- **Filter on the EFFECTIVE mime, not the raw one.** When the extractor reports no format, the code
  falls back to a default (`audio/mp4`) at write time — so an absent/blank mime must be treated as
  that fallback, not as "unstorable", or downloads that previously worked start failing.
- **Never surface the platform's message.** When a video genuinely offers only an unstorable
  container, throw your OWN message saying the track still plays with a connection but cannot be
  saved in that form. The platform's string names a container the user cannot act on.

**Verification:** the selector is pure, so cover it with `testDebugUnitTest` (inject a fake
predicate). The cases that matter: highest-bitrate track is unstorable → pick the next storable one;
all unstorable → `null`; the returned index points into the ORIGINAL list; the bitrate cap is still
honoured among storable tracks. Cross-check the logic with a quick port before trusting the harness.

## Worker and scheduler

- **One song per work request**, with a unique work name derived from the song id so a re-tap does
  not enqueue a second download of the same track (`ExistingWorkPolicy.KEEP`). Album/playlist
  downloads are N enqueues, not one job that loops — that is what makes per-track progress
  observable and per-track cancellation possible.
- **`CoroutineWorker.setProgress` is a `suspend` function — a plain callback cannot call it, and the
  error lands on the lambda, not on the call site.** `javap androidx.work.CoroutineWorker` shows
  `setProgress(Data, Continuation)`; a normal `(Long, Long) -> Unit` progress callback then fails with
  "Suspension functions can only be called within coroutine body". Make the callback type
  `suspend (downloaded: Long, total: Long) -> Unit`, make the downloader `suspend`, and wrap the
  byte-copy in `withContext(Dispatchers.IO)` (which also moves the URL resolve and the MediaStore
  query off the caller's dispatcher). Then report progress with `setProgress(Data)` (`bytesRead` /
  `totalBytes`) and expose the state so the UI can show a per-row progress bar.
- **The `Flow` observation overloads are declared ON `WorkManager` itself**
  (`getWorkInfosByTagFlow(tag)`, `getWorkInfosForUniqueWorkFlow(name)` — verified by
  `javap androidx.work.WorkManager` on 2.10.x), **not** as extensions in a `WorkManagerKt` class.
  There is no `WorkManagerKt` in the artifact and its absence means nothing; do not rewrite the
  observation layer around an API you already have. Give each request a per-song tag
  (`download:<songId>`, readable back out of `WorkInfo.tags`) plus one shared batch tag, so a single
  `getWorkInfosByTagFlow(batchTag)` feeds the whole screen: map each `WorkInfo` to
  `songId -> DownloadState` and let a missing key mean `Idle`. Map the `WorkInfo.State` set
  explicitly — `CANCELLED` is user intent and belongs back at `Idle`, not at `Failed`, or cancelling
  shows an error for the very thing the user asked for.
- **Put the download-eligibility predicate in ONE place and use it for both the button and the
  enqueue guard.** "Has a `videoId`, is not already downloaded" as a pure `internal fun
  SongEntity.canDownload()` referenced by the enqueue path AND by the UI's show-the-button check —
  a second, hand-written version of the condition is how a button appears for a track that then
  silently does nothing, or an already-downloaded track gets a second copy.
- **Do not constrain to `UNMETERED`** unless the user asked for it — a user tapping "download" on
  cellular has consented; adding a network constraint makes the button look broken.

## The three integration points that decide whether the feature works AT ALL

These are the failure modes that compile, lint, and pass every unit test while the feature is
either useless or actively harmful. Each is a one-line mistake.

### 1. Playback must check `isDownloaded` FIRST, before building the stream URI

The whole point is that a downloaded track does not touch the network. If the `MediaItem` builder
checks the stream case first (or falls through to the `blossomstream://` placeholder), a downloaded
track still resolves over the network and "offline" mode silently does nothing. Put the local-file
branch at the TOP of the builder and return early. Verify by reading the order of the branches, not
by the presence of the field.

### 2. The MediaStore scanner must EXCLUDE the download folder

The downloaded file lives in the public Music folder *by design*, so the app's own scanner will find
it on the next scan and insert it as a **second row** — the same song twice, one a stream row and
one a local row, with different ids. Delete one and the other survives; play counts split across
them. Exclude the app's own download subfolder in the scanner's selection (or skip by path prefix)
whenever the destination is a folder the scanner also walks. This is inherent to "save where other
players can see it" — you cannot fix it by saving somewhere else without giving up the requirement.

### 3. The per-song menu must be handed the download callback at EVERY call site

The download control lives inside a shared per-song overflow menu, so the feature exists only where
that menu is CONSTRUCTED with the new callback. A screen can build the same menu two or three times
(one per section, plus a nested list inside it) and wire only some of them, so the action shows up on
one screen and is simply absent on another — which the user reports as "the menu is missing",
pointing at a screen you believed you had already fixed. Making the callback optional so untouched
callers keep compiling is what hides it: no compile error, no lint, no failing test. After wiring,
grep the menu component's name and read every construction site
(`grep -rn 'SongMenu(' app/src/main/kotlin/`); each one must pass the callback, and a screen that
only reads a per-item state is not the same as a screen that can trigger the action. For rows whose
track is not yet in the database (search results), derive the id from the SAME source the worker uses
(`streamSongId(videoId)` must match what the download creates) or the per-row progress/state never
connects to the row that was written. And when you add a helper for a case the existing path cannot
express (a track with no DB row), grep that it has a caller before calling the feature done — a helper
with zero call sites is the dropped wiring, not spare code.

## The UI surface: ONE control per song that changes shape with state

The download control belongs in the existing per-song overflow menu, as a single row whose label and
action follow `DownloadState` — Undownload -> "Unduh"; `Waiting` -> disabled, "Menunggu...";
`Running` -> the percentage with a cancel action; `Done` -> "Sudah diunduh"; `Failed` -> "Gagal, coba
lagi" — not several rows that are always present. A menu permanently showing both "Download" and
"Cancel download" lies about what a tap will do. Album/playlist screens get one "download all"
button, rendered only when at least one track passes the eligibility predicate; a button that appears
and then does nothing is worse than an absent one. The per-song menu and the Downloaded tab are the
two places the state is read — a new state must be surfaced in both, or it exists only in the model.

**When a state carries a reason, render the reason — do not switch on the case and drop the field.**
A `Failed(message)` that the menu treats identically to `Idle` (just "Unduh" again) discards the one
thing that tells the user whether retrying can help: a deleted video and a dropped signal look the
same, so the user re-taps forever. Read the carried field in the branch that renders that state, and
keep a retry label on the action.

## Do not hold an import alive with a fake `@Suppress("unused")` property

When a helper is written before its caller exists, it is tempting to add a dummy property or
function annotated `@Suppress("unused")` purely so an import is not flagged. That is a hack that
survives into the committed tree and misleads the next reader. If an import is genuinely unused,
remove it; if the symbol is genuinely needed, the caller that uses it is the thing to write.

## What a headless host can and cannot verify here

Verifiable from the build host: the pure filename rule (unit test), the branch order in the
`MediaItem` builder (read the code), the scanner's exclusion (read the query), and — via CI — that
it all compiles.

**One thing IS verifiable on the release APK, and it is the failure CI cannot catch: whether R8 kept
the Worker class.** WorkManager constructs the worker from the class NAME stored in its own database,
so R8 must keep `DownloadWorker`'s name or every download fails on device with no build error. Grep
the release dex for the worker's fully-qualified name and for a runtime constant the feature adds (a
per-song/batch tag, the placeholder scheme):

```bash
unzip -oq app-release.apk 'classes*.dex' -d /tmp/dex
strings -a /tmp/dex/classes.dex | grep 'DownloadWorker'
```

The trap when reading the result: your OTHER new classes (`DownloadScheduler`, `AudioDownloader`, the
ViewModel) legitimately show **zero hits** because R8 renames internal classes — only the
name-referenced Worker survives verbatim. Reading those zeros as "R8 stripped my feature" sends you
chasing a keep rule that was never needed. Confirm the surviving class name plus at least one runtime
constant, and treat the rest as expected obfuscation.

**When the change you shipped is a fix inside an ordinary function (a composable, a menu builder),
there is no name to grep for and every string probe comes back empty — prove it landed by DIFFING
the dex against the previous release instead.** Unzip `classes*.dex` from the old published APK and
the new one and compare their hashes and sizes:

```bash
mkdir -p /tmp/old /tmp/new
unzip -oq app-release-old.apk 'classes*.dex' -d /tmp/old
unzip -oq app-release.apk     'classes*.dex' -d /tmp/new
sha256sum /tmp/old/classes.dex /tmp/new/classes.dex
stat -c '%s %n' /tmp/old/classes.dex /tmp/new/classes.dex
```

Different hashes and a non-zero size delta are positive evidence the new code is in the artifact —
which a compile-only claim cannot give you. Obfuscation is not a dead end for verification, it just
moves the question from "is the symbol there" to "is this a different binary than the one before".

**Not** verifiable headless: that MediaStore actually indexes the file on a device,
that the public-folder write succeeds under scoped storage, and that playback of the local copy
works. Say so plainly; do not report the feature as working on compile evidence alone.
