# Streaming extractor integration (NewPipe-style, verified headless)

Depth for adding an external media extractor to an Android app — YouTube Music / SoundCloud via a
library such as NewPipe Extractor — and for judging **what you can and cannot verify** from a
headless build host before you write the feature.

## Pre-flight: verify the API against the real artifact, not memory

Extractor APIs are unstable and poorly documented. Read the actual jar before writing a line
against it. This is the single highest-value step: one wrong signature costs a full
compile-fix-compile cycle.

```bash
# Grab the exact version the build will resolve (JitPack publishes the jar directly).
curl -sL -o /tmp/npe.jar "https://jitpack.io/com/github/TeamNewPipe/NewPipeExtractor/v<VER>/NewPipeExtractor-v<VER>.jar"
mkdir -p /tmp/npe && unzip -q -o /tmp/npe.jar -d /tmp/npe

# Enumerate the real class + method names. Nested classes use '$' — quote them.
javap -classpath /tmp/npe/x 'org.schabi.newpipe.extractor.services.youtube.extractors.YoutubeStreamExtractor'
javap -classpath /tmp/npe/x org.schabi.newpipe.extractor.NewPipe | grep -i service
```

Then compile and **run a throwaway probe** (a plain `main`, not app code) that exercises the two
halves separately — search, then stream resolution:

```bash
javac -cp "/tmp/npe/x:$(ls /tmp/npe/*.jar | tr '\n' ':')." -d /tmp/npe Probe.java
java  -cp "/tmp/npe:/tmp/npe/x:$(ls /tmp/npe/*.jar | tr '\n' ':')." Probe
```

Verified shapes worth not re-guessing (NewPipe Extractor 0.26.x):

| Thing | Reality |
|---|---|
| Music service | **No `YoutubeMusic` service exists.** Use the `YouTube` service with the content filter `music_songs`. |
| Search factory accessor | `getSearchQHFactory()` — capital `Q`, capital `H`. |
| Search call | `fromQuery(query, List filters, String sort)` — **three** args. |
| iOS-client toggle | `setFetchIosClient(boolean)` and `setPoTokenProvider(...)` exist on the stream extractor. |

### Search result types: one content filter per request

`YoutubeSearchQueryHandlerFactory.getUrl(...)` uses **only `contentFilters.get(0)`** — the first
 element. Passing `listOf("music_songs", "music_albums")` does NOT return a mix; issue one request
 per filter. (Verified from bytecode: the method reads index 0, then `lookupswitch`es on that single
 string.)

The parser is not the limit: `YoutubeMusicSearchExtractor` parses with a
`MultiInfoItemsCollector`, so one response genuinely can carry several item types — the filter you
send is what narrows it. So a screen that must show songs + albums + artists needs three requests,
and filtering everything to `StreamInfoItem` and discarding the rest is how albums and artists
silently vanish from search when songs are not all you asked for.

**Isolate failures per group — three requests means three ways to fail, and one must not blank the
screen.** Treat the songs request as primary (if it fails, the search genuinely failed: surface it),
but wrap the album and artist requests so their failure degrades to an empty list
(`runCatching { … }.getOrDefault(emptyList())`). A user who searched for a song and gets a full
error screen because the *album* call timed out has been shown a worse app than one that quietly
omitted the album section. This also keeps a transient failure in one group from being reported as
"search is broken".

| Filter constant | Value | Item class returned |
|---|---|---|
| `MUSIC_SONGS` | `music_songs` | `StreamInfoItem` |
| `MUSIC_ALBUMS` | `music_albums` | `PlaylistInfoItem` |
| `MUSIC_ARTISTS` | `music_artists` | `ChannelInfoItem` |

Making an album/artist result *openable* (not just listed):

- **Album** — albums are playlists: `PlaylistInfo.getInfo(service, albumUrl).relatedItems` yields
  `StreamInfoItem`.
- **Artist** — `ChannelInfo.getInfo(service, artistUrl)`, then pick the tab whose `contentFilters`
  contains `ChannelTabs.TRACKS` and call `ChannelTabInfo.getInfo(service, tab)`. The TRACKS tab does
  not exist for every channel — return an empty list, do not throw.

`InfoItem` gives `getName()` / `getUrl()` / `getThumbnails()`; `PlaylistInfoItem` adds
`getUploaderName()` / `getStreamCount()`; `ChannelInfoItem` adds `getSubscriberCount()`. Every
`*LHFactory.getId(url)` throws `ParsingException` — wrap in `runCatching{}.getOrNull()` and
`mapNotNull` so one odd URL does not kill the whole list. For "load more" (results stopping at the
first page of ~20), `ListInfo.hasNextPage()` / `getNextPage()` and `ListExtractor.InfoItemsPage`
are available.

## Android-compatibility check on any third-party jar

A jar that runs on the JVM may still fail D8/R8. Check before adding the dependency:

```bash
# Android toolchain accepts class-file major version <= 55 (Java 11).
javap -v -classpath /tmp/npe/x org.schabi.newpipe.extractor.NewPipe | grep -m1 'major version'
# Any desktop-only dependency? These do not exist on Android.
unzip -l /tmp/npe.jar | grep -Ei 'awt|swing|javax/imageio'
```

### The `javax.script` trap — the compat check that actually bites

Bytecode version and AWT are the easy checks; the killer is a **transitive** dependency that
implements a JDK API Android does not ship. `android.jar` contains **zero** classes from
`javax.script`, so such an artifact compiles fine and dies at runtime on device.

Concrete case: an extractor that deciphers YouTube signatures needs a JavaScript engine. NewPipe
depends on Rhino, and the Maven artifact drags in `rhino-engine` (the `javax.script` binding)
alongside `rhino` (the engine). Only `rhino` is Android-safe. Confirm, then exclude:

```bash
# 1. Does android.jar ship javax.script at all?
unzip -l $ANDROID_HOME/platforms/android-35/android.jar | grep -c 'javax/script'   # expect 0

# 2. Which packages do the extractor's script-using classes reference?
javap -v -classpath /tmp/npe/x org.schabi.newpipe.extractor.utils.JavaScript \
  | grep -oE 'org/mozilla/javascript/[A-Za-z]+|javax/script/[A-Za-z]+' | sort -u
#   org/mozilla/javascript/* only  -> safe (engine core, no javax.script)
#   any javax/script/*            -> that code path will crash on Android
```

```kotlin
implementation("com.github.TeamNewPipe:NewPipeExtractor:v0.26.5") {
    exclude(group = "org.mozilla", module = "rhino-engine")   // javax.script binding: not on Android
}
```

Generalise: for any third-party jar, `javap -v` a few classes and grep for `javax/script`,
`java/awt`, `javax/swing`, `java/sql`, `javax/xml/bind` — JDK-only packages that are absent or
stubbed on Android.

### Check the exact CLASS, not the package — and remember `Error` is not `Exception`

A package-level check gives a false "present": `android.jar` ships *some* `java.beans` classes but
**not** `java.beans.Introspector`, `BeanInfo`, or `PropertyDescriptor`. Rhino's
`JavaToJSONConverters` references exactly those, so the package grep is nonzero and reads as safe.
Diff the specific classes the dependency names, not the prefix:

```bash
# Which exact JDK classes does the suspect class reference?
javap -v -classpath /tmp/rhino.jar org.mozilla.javascript.JavaToJSONConverters \
  | grep -oE 'java/beans/[A-Za-z]+' | sort -u
# Then ask android.jar for those exact classes — not the package.
unzip -l $ANDROID_HOME/platforms/android-35/android.jar | grep 'java/beans/'
```

Two mechanisms make this class of gap reach users as a bare force close with no message:

- **A missing class throws `NoClassDefFoundError`, which is an `Error`, not an `Exception`.** Every
  `catch (Exception)` / `runCatching` in the call path lets it straight through to the crash handler.
- **A desktop-JVM probe cannot reproduce it.** The probe's JDK *has* `java.beans`, so the class
  resolves and the probe passes — the failure is Android-only and structurally invisible from the
  host. When code "works in my probe but crashes on device", suspect class availability, and check
  `android.jar` and the packaged dex rather than re-reading the logic. Find who references the
  missing type from the dex itself:
  `strings -a app/build/outputs/apk/debug/*/classes*.dex | grep -oE 'java/beans/[A-Za-z]+' | sort -u`
  then walk back to the owning jar with `for f in $(find /tmp/unpacked -name '*.class'); do strings -a "$f" | grep -q 'java/beans' && echo "$f"; done`.

Note the fix is *not* automatic: a class referenced but never loaded on the failing path is not the
cause, so confirm the path actually loads it (or get a stack trace) before adding R8 keep/dontwarn
rules. Prove loading with `java -verbose:class -cp <probe> Probe 2>&1 | grep -i java.beans` — no
output means that path never touches the class, and the rule is not your fix. `-dontwarn` silences
the build warning; it does not make a genuinely missing class exist at runtime. Full crash-triage
procedure (regression check, candidate list, dex-vs-android.jar probe) in
`references/headless-crash-triage.md`.

## The verification wall: a datacenter IP cannot resolve anonymous streams

**Search works from a cloud host; anonymous stream resolution usually does not.** YouTube
bot-checks datacenter IP ranges for watch/stream access and returns
`SignInConfirmNotBotException: "Sign in to confirm that you're not a bot"` (`LOGIN_REQUIRED`). A
cloud VPS is a datacenter IP; a phone on home/mobile data is not.

Consequences, decide these up front rather than after a wasted build:

- **You cannot prove the playback path from the build host.** Search results, parse logic, and UI
  wiring are verifiable there; the actual audio URL fetch is not. Say this plainly to the user
  before writing the feature instead of shipping code you cannot test.
- **The user's device is the only real test environment.** Build so failures are visible on screen
  (a surfaced error message, not a swallowed exception) so a failed resolve is diagnosable from a
  screenshot.
- **Do not present an untested bypass as a fix.** Toggling the iOS client or adding a PoToken
  provider may or may not clear the check, and PoToken needs its own server — do not write either
  into the design as "the solution" without a working observation.
- Probe a handful of videos, not one. A single success (an old, popular upload) proves nothing about
the rest; sample ~10–15 and report the ratio.

## Resolve-at-playback: the `ResolvingDataSource` recipe

"Resolve the URL when playing, not when scanning" needs a concrete mechanism, because the
`MediaItem` must carry *something* durable across the binder. Use a private URI scheme as a
placeholder and swap it for the real URL inside a `ResolvingDataSource` wrapper:

1. Store only identity on the entity (`uri = null`, `videoId` set) — never the extractor URL.
2. Build the `MediaItem` URI as a placeholder, e.g. `blossomstream://audio/yt:<videoId>` (via
   `Uri.Builder`), and write it to **both** `setUri(...)` and `setRequestMetadata(mediaUri)` — the
   same double-write a local item needs, because `localConfiguration` is dropped over the binder
   (see `references/media3-playback-service.md`).
3. Wrap the data source so unknown schemes pass through untouched:

```kotlin
// UA is set per-request in the resolver below, NOT on the factory — see the 403 section
// for why a factory UA overrides the per-request one.
val base = DefaultDataSource.Factory(context,
    DefaultHttpDataSource.Factory().setAllowCrossProtocolRedirects(true))
return ResolvingDataSource.Factory(base) { spec ->
    val songId = songIdFromStreamUri(spec.uri) ?: return@Factory spec   // local files pass through
    val videoId = videoIdOf(songId)!!
    spec.buildUpon()
        .setUri(Uri.parse(extractor.resolveAudioUrl(videoId)))
        .setKey(videoId)          // stable cache identity, not the expiring URL
        .setHttpRequestHeaders(mapOf("User-Agent" to YOUTUBE_USER_AGENT) + TE_HEADER)
        .build()
}
```

4. Install it on the player: `DefaultMediaSourceFactory(streamDataSource.factory())`, then
   `ExoPlayer.Builder(ctx).setMediaSourceFactory(factory)`.
5. The resolver runs on the playback thread. **Throw `IOException`** for any failure — it is the
   only exception type a `DataSource` may propagate — and put the human-readable message inside
   it. Media3 surfaces it as a `PlaybackException` your UI can render.

Because the resolver runs per open, the URL is never stale and a stored row from months ago still
plays. Cost: one extra network round-trip before audio starts (~1–2 s); accept it.

Also: **do not fire a network search per keystroke.** Debounce (~500 ms) and set a minimum query
length (2 chars). Otherwise one typed word becomes five requests, results flicker, and YouTube
rate-limits you.

## HTTP 403 on a stream URL that is still valid (the UA-binding trap)

**Symptom:** streamed tracks intermittently fail with 403 from `videoplayback`; the same URL
sometimes plays and sometimes does not. It looks random, which is why it is easy to misdiagnose as
network flakiness.

Two causes, and you need both fixes:

1. **The data-fetching UA must match the UA of the client the extractor used to request the URL.**
   YouTube binds a `videoplayback` URL to the client that asked for it. Fetching it with a different
   UA (e.g. a Chrome-Mobile string while the URL was extracted with the extractor's own UA) returns
   403 even though the URL has not expired. A plausible-looking Android UA is the *cause*, not the
   fix.

   **The extractor library does NOT set a User-Agent — the host app does, at the Downloader
   layer.** NewPipe Extractor never writes a UA header itself; the NewPipe *app* adds it in
   `DownloaderImpl.USER_AGENT` (a plain desktop Firefox UA string) and its `YoutubeHttpDataSource`
   reuses that same constant for playback. So when you bridge the extractor with your own HTTP
   client (OkHttp, `HttpURLConnection`), **your bridge must add the UA itself** — nothing upstream
   will. A bridge that only forwards the extractor's own headers sends *no* UA at all, which is a
   real 403 cause on its own, independent of what playback sends.

   **Then make extraction and playback read the SAME constant.** Write the UA once (e.g. an
   internal `YOUTUBE_USER_AGENT` in the data layer) and reference it from both the Downloader
   bridge and the playback `DataSource`. Two separately-maintained UA strings are the bug: one side
   drifts and 403 returns.

   **Grepping the extractor jar for the UA value gives a FALSE NEGATIVE.** `DownloaderImpl` lives
   in the NewPipe app, not in the extractor library, so `grep`/`strings` over the extractor jar
   returns nothing even when the value is correct. Do not conclude "this UA is invented" from an
   extractor-jar search alone — check the app's `DownloaderImpl` source (or NewPipe's
   `YoutubeHttpDataSource`) before discarding a value. What the *extractor* jar does contain and is
   worth `javap`-ing: `YoutubeParsingHelper.isWebStreamingUrl`, `isVisionOsStreamingUrl`,
   `getAndroidUserAgent`, `getVisionOsUserAgent`.
2. **A 403 is worth exactly one retry**, not an immediate failure. The URL can be revoked earlier
   than its nominal expiry, and a fresh URL for the same videoId usually succeeds immediately — that
   is why the error is intermittent. Retry **only** 403: 404/410 mean the video is genuinely gone,
   and retrying just delays the same error.

**Wrapper ordering is critical — put the retry INSIDE the resolver, not outside it.**

```kotlin
val retrying = DataSource.Factory {
    ForbiddenRetryDataSource(base.createDataSource(), ::rebuildForRetry)
}
return ResolvingDataSource.Factory(retrying) { spec ->
    val songId = songIdFromStreamUri(spec.uri) ?: return@Factory spec
    spec.buildUpon().setUri(Uri.parse(resolve(videoId))).setKey(videoId).build()
}
```

The retry wrapper learns *which video* to re-resolve from `DataSpec.key`, which only the resolver
sets. Wrapped the other way round (resolver inside, retry outside) `key` is still empty when
`open()` fails, so the retry has nothing to act on. In the retry path, `close()` the failed
connection before reopening it — the delegate still holds the previous request's state otherwise.

**Set the UA per-request on `DataSpec`, and do NOT set one on the factory.** `DefaultHttpDataSource`
writes the factory's UA **after** the `DataSpec` headers, so a factory UA overrides a per-request
one — which silently kills any URL that needs its own UA (see the visionOS case below). Omit
`.setUserAgent(...)` on `DefaultHttpDataSource.Factory` and put `User-Agent` into
`DataSpec.httpRequestHeaders` instead:

```kotlin
val base = DefaultDataSource.Factory(
    context,
    DefaultHttpDataSource.Factory()          // no .setUserAgent() here
        .setAllowCrossProtocolRedirects(true),
)
// per request, inside the resolver:
spec.buildUpon()
    .setHttpRequestHeaders(mapOf("User-Agent" to YOUTUBE_USER_AGENT) + TE_HEADER)
    .build()
```

**Send `TE: trailers` on every URL.** NewPipe always sets it while playing; omitting it makes your
request differ from the one YouTube expects.

**visionOS URLs need a different UA — and only the per-request placement can supply it.**
`YoutubeParsingHelper.isVisionOsStreamingUrl(url)` marks them; the matching UA comes from
`getVisionOsUserAgent(null)` (safe to pass `null` — it falls back to `Localization.DEFAULT`). A
factory-level UA would override this and 403. Branch on the URL kind:

```kotlin
val userAgent = if (YoutubeParsingHelper.isVisionOsStreamingUrl(url))
    runCatching { YoutubeParsingHelper.getVisionOsUserAgent(null) }.getOrNull() ?: YOUTUBE_USER_AGENT
else YOUTUBE_USER_AGENT
```

Browser-ish headers (`Origin`, `Referer`, `Sec-Fetch-*`) are only needed for URLs from the **WEB**
client — mirror the extractor, which distinguishes WEB from ANDROID/IOS clients, and do not add them
to every URL.

## Letting the user pick stream quality (and why only streams)

**A quality setting can only govern streamed tracks.** Local files are whatever the user owns —
there is nothing to re-encode — so offering a choice there is a lie the UI tells. Label the
setting so it says streamed-only, and let local playback ignore it.

**Model the choice as a bitrate CAP, not a named tier.** YouTube's available bitrates differ per
video (48/70/128/256 kbps), so "HD"/"Ultra" labels point at qualities the source may not have.
Store an enum whose payload is `maxBitrateBps` (`HIGH = Int.MAX_VALUE` as the default so existing
users keep today's behaviour, `MEDIUM = 128_000`, `LOW = 64_000`).

**Extract the selection rule into a pure function and unit-test it** — it is exactly the
silent-failure logic a build cannot check:

```kotlin
// 1. unknown bitrate (<= 0) must not be used for comparison
// 2. among those under the cap, take the HIGHEST (the cap is a ceiling, not a target)
// 3. if all known bitrates exceed the cap, take the LOWEST — play slightly over-budget
//    rather than refuse to play
// 4. if every bitrate is unknown, take the first entry
fun chooseIndex(bitrates: List<Int>, maxBitrateBps: Int): Int?
```

Rule 3 is the one people get wrong: refusing to play because "nothing matches the requested
quality" is a worse outcome than playing a track that is a little larger than asked.

**Read the preference where the resolve happens, not at UI level.** The `DataSource` resolver runs
on the playback thread and cannot suspend to read DataStore. Hold the current value in memory:
collect the preference flow into a `@Volatile`-backed field in the singleton from an
application-lifetime `CoroutineScope` (provide it as a DI singleton via a `@ApplicationScope`
qualifier — `SupervisorJob() + Dispatchers.Default`), and read that field inside the resolver.
Never block the playback thread on disk.

**Changing the setting must invalidate the in-memory URL cache.** The resolver caches resolved URLs
for a TTL; a cached URL was chosen under the OLD cap, so a preference change has to clear it or the
new quality does not take effect until the cache expires.

**Verify the extractor's bitrate accessors against the jar** before writing: `AudioStream` exposes
`getAverageBitrate()`, `getBitrate()`, `getQuality()`, and the constant `UNKNOWN_BITRATE`. Use
`averageBitrate` for selection; `getQuality()` is a free-form label, not a comparable number.

## Design rules that follow from the above

- **Never persist a stream URL.** Extractors return time-limited URLs (~6 h). Store only stable
  identity (video id, title, thumbnail) and resolve the playable URL at playback time. This forces
  the playback service, not the scanner, to own resolution — plan the `MediaItem` construction
  accordingly.
- **`INTERNET` permission is required and easy to forget** in a project that started local-only:
  `<uses-permission android:name="android.permission.INTERNET" />`. Its absence fails at runtime,
  not at build time.
- **Treat streamed and local tracks as one row type.** A `source` column on the existing song
  entity keeps one library, one queue, and one DAO path; do not fork the schema.

## Merging the two sources into one UI (the part that bites)

Once streamed tracks are saved into the same table, a naive merged search shows the **same track
twice**: the library query returns saved stream rows, and the network search returns those same
videos again. Rules that fall out of it:

- **Filter network results against what is already saved — but only the SONG group.** Collect
  `videoId` from the library rows and drop any song result whose id is in that set. Dedupe by stable
  identity, never by title — the library row and the search row carry different metadata for the
  same video. The filter keys on `videoId`, which only song results carry; album and artist results
  are keyed by playlist id / channel id and are not library entities at all, so there is nothing for
  them to collide with. Extending this filter to those groups is a category error: it reads as
  consistency while doing nothing, or hides a group the user explicitly asked for.
- **When three groups share one `LazyColumn`, namespace every key across ALL of them.** Song,
  album, and artist ids come from the same search and can overlap; keys `"stream-$videoId"`,
  `"artist-${id}"`, `"album-${id}"` (plus one per section header) keep them disjoint. Un-namespaced
  keys collide the moment an id repeats between groups, and a duplicate key in a `LazyColumn`
  throws — the app closes on a search that looks perfectly fine.
- **A "no results" message is only true if BOTH sources are empty.** If the local list is non-empty
  and the network half returns nothing, the right state is silence, not "tidak ditemukan". Gate
  every empty/loading message on the other source being empty too, or the screen lies.
- **Mark the source in the row itself.** A streamed track needs network and cannot play offline; a
  local one can. With no marker the two are visually identical and the difference only shows up as
  a mystery failure on a plane. One small label in the subtitle beats a section header.
- **Share the row menu by taking no-arg callbacks.** A per-row "play next / add to queue / add to
  playlist" menu needs to work for two different item types: rows already in the database, and
  search results that have no entity yet. If the composable's signature is `(SongEntity) -> Unit`,
  it cannot serve the second. Give it `onPlayNext: () -> Unit` etc. and let the caller close over
  whichever item it holds; one menu then serves both screens.
- **A streamed result must be persisted BEFORE any queue or playlist action.** Queue and playlist
  entries reference rows by `id`, so "play next" / "add to queue" / "add to playlist" on a search
  result each need the same save-then-act step the play button does. Route all four through one
  `saveStreamSong(result) { entity -> ... }` helper rather than four save paths.
- **Build the mixed queue from EVERYTHING on screen — the local results AND the network results
  below them.** This corrects an earlier, wrong form of this rule ("queue the picked track followed
  by the local results"): queueing only the local half means that when the search has no library
  match, the queue holds a single track, and `Player.seekToNextMediaItem()` on a one-item queue
  **does nothing and throws nothing** — a dead "next" button with no error anywhere. It reads as
  intermittent precisely because it only bites when the picked track is absent from the list you
  queued from. The cost objection is false: `StreamSearchResult.toEntity()` is a pure in-memory
  mapping (no save, no network — only `saveStreamSong` touches the DB), so mapping the on-screen
  network results into the queue is free.

  ```kotlin
  val visible = (librarySongs + streamResults.map { it.toEntity() }).distinctBy { it.id }
  val queue = if (visible.any { it.id == selected.id }) visible else listOf(selected) + visible
  ```

  Dedupe by `id` is what makes this safe: a saved stream track has id `yt:<videoId>`, exactly what
  `toEntity()` produces, so the same track arriving from both halves collapses to one. Keep the
  picked track guaranteed-present as a fallback — Room emits asynchronously, so it may not have
  appeared in either list yet. Caveat: only the picked track is persisted before play, so a queue
  restored after an app restart holds the saved rows and drops the un-saved network tail.
- **A queue built from an OPENED album/artist is a DIFFERENT list from the search queue, and its
  selected track must be the SAVED entity, not the raw search row.** When a grouped result opens
  into a stacked list (the album's tracks, the artist's tracks), a tap there queues *that album's
  track list*, not the search results behind it — keep it as its own pure function
  (`buildStreamQueue(selected, tracks)`) so the two rules cannot drift into one. Pass the track you
  just persisted as `selected` and map the rest through `toEntity()`: using the raw
  `StreamSearchResult` for the picked track loses the enriched title/artwork the row already shows,
  and the queue then renders worse metadata than the list the user tapped. Same dedupe-by-`id` and
  guaranteed-selected fallback as the mixed queue.
- **Put the queue-building rule in a pure top-level function and unit-test it.** "Which lists feed
  the queue" is silent-failure logic: cheap to test headless, invisible to the compiler. Cover the
  case that triggered the bug (the second list empty) plus "picked track appears exactly once" and
  "picked track never disappears from its own queue". Also cover the opened-album variant (empty
  track list still queues the picked track; a track appearing in both `selected` and `tracks`
  collapses to one).
- **Model only what you implement — a pagination field no code fills is a lie the next reader
  builds on.** The extractor exposes `ListInfo.hasNextPage()` / `getNextPage()`, and it is tempting
  to carry `hasMore`/`nextPage` in the result model "for later"; if nothing sets them, they read as
  "pagination is wired up" and a future session debugs a field that was never populated. Drop the
  field until the code that fills it exists.
- **Sweep every play call site, not just the one you found.** The "queue built from too narrow a
  list" shape usually exists on more than one screen: `grep -rn '\.play(\|playAll(\|playQueue('`
  and read which list each call passes.
- **Gate next/previous on state, never always-on.** `PlaybackUiState.hasNext` / `hasPrevious`
  already exist — bind `enabled` to them and dim the tint when false. A control that is always
  tappable but inert at the queue's end reads as "the button is broken", not "the queue ended".
