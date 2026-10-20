# Media3 playback service + local library (verified integration notes)

Integration depth for a Media3-backed music player: background service, controller pattern,
manifest, Room migration, and MediaStore scanning. Pairs with
`references/compose-hilt-project-scaffold.md` (project skeleton) — this file is the app layer.

## Verify the library API before writing against it

AndroidX ships API jars you can read directly. Do this instead of guessing at signatures — it
costs seconds and prevents a compile-fix-compile loop.

```bash
# The AAR's classes jar lives in the Gradle transform cache after one resolve.
find ~/.gradle/caches/*/transforms -name 'media3-session-*-api.jar'

JAR=<path from above>
# Nested classes use '$' in the class name — quote it.
javap -classpath "$JAR" 'androidx.media3.session.MediaLibraryService$MediaLibrarySession$Callback'
javap -classpath "$JAR" 'androidx.media3.session.MediaSession$Callback' | grep onAddMediaItems
```

Confirmed shapes (media3 1.5.1) — the two that bite:

| Symbol | Reality |
|---|---|
| `onAddMediaItems` | Declared on **`MediaSession.Callback`**, NOT `MediaLibrarySession.Callback`. Override it in the latter (it extends the former) or it silently never runs. |
| `onAddMediaItems` params | Java `java.util.List<MediaItem>` → Kotlin **`List<MediaItem>`**, and it returns `ListenableFuture<List<MediaItem>>`. Writing `MutableList` does not compile. |
| `MediaLibrarySession` | A **nested** class: `MediaLibraryService.MediaLibrarySession`. Same for `Builder` and `Callback`. |
| `onGetSession` | `MediaLibraryService.onGetSession(...)` returns `MediaLibrarySession?` (nullable). |

## Choose the service class

- `MediaSessionService` — playback only. Enough for a plain player.
- `MediaLibraryService` — adds a browsable library (`onGetChildren`/`onSearch`) for Android Auto /
  Wear. Pick this when the roadmap includes those, even if you leave the library callbacks
  unimplemented at first; the session callback you need (`onAddMediaItems`) still works.

## Manifest (all four are required)

```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

<service
    android:name=".playback.PlaybackService"
    android:exported="true"
    android:foregroundServiceType="mediaPlayback">
    <intent-filter>
        <action android:name="androidx.media3.session.MediaSessionService" />
        <action android:name="androidx.media3.session.MediaLibraryService" />
        <action android:name="android.media.browse.MediaBrowserService" />
    </intent-filter>
</service>
```

List **all three** actions, matching the production apps (Metrolist, ArchiveTune). The bind intent
from `MediaControllerImplBase` is explicit (`new Intent(SERVICE_INTERFACE)` + `setClassName(...)`),
so the action list is not what makes the primary bind succeed — but the extra actions are what let
other entry points (MediaBrowser / Android Auto) bind, and a missing one is a confusing dead end to
debug later. Verify the built artifact really carries them:

```bash
$ANDROID_HOME/build-tools/35.0.1/aapt2 dump xmltree \
  --file AndroidManifest.xml app/build/outputs/apk/debug/app-debug.apk | grep -A6 'E: service'

`foregroundServiceType="mediaPlayback"` is mandatory on Android 14+; omitting it throws at
playback start, not at build time. `exported="true"` is needed for Auto/assistant discovery.

## Controller pattern — the UI must never hold an ExoPlayer

Hold a `MediaController` built from a `SessionToken`, not the player itself. The service owns the
player, so playback survives the app going to background and the notification, headset buttons,
and app UI stay on one source of truth.

```kotlin
val token=<redacted> ComponentName(context, PlaybackService::class.java))
val future = MediaController.Builder(context, token).buildAsync()
future.addListener({ controller = future.get(); controller.addListener(listener) },
                   MoreExecutors.directExecutor())
```

Two behaviours worth building in from the start:

- **Queue the intent, don't drop it — and queue a LIST, not one slot.** A controller is not ready
  synchronously, so an action issued before it connects must be stored and replayed in the connect
  listener. Use `MutableList<() -> Unit>`, not `(() -> Unit)?`: with one slot, a second action
  issued before the connection lands **overwrites the first and it is silently lost**. The trigger
  is ordinary use, not an edge case — open the app, add two tracks to the queue before anything is
  playing, and the first one never arrives. Queue mutations are ordered and order-dependent, so
  dropping one corrupts the sequence, not just one item.

  ```kotlin
  private val pendingActions = mutableListOf<() -> Unit>()

  // in the connect listener, once controller != null:
  pendingActions.forEach { it() }
  pendingActions.clear()

  private fun withController(action: () -> Unit) {
      if (controller == null) { pendingActions += action; connect() } else action()
  }
  ```

- **Audit EVERY controller mutation for the null path — not just the one you first noticed.**
  `playQueue` is the action you think about, so it gets the queue. `enqueue`, `playNext`, and
  `playAt` are written later and reach for `controller?.` directly, which **no-ops silently** when
  the controller is null — no exception, no error, the track simply is not queued. Any method whose
  body is `controller?.something()` is a latent silent failure; route it through the shared helper
  above. Grep the connection class for `controller?.` and check each hit is inside a queued action.
- **Map `mediaId` back to your entity.** Media3 only carries `MediaMetadata`, not your Room row.
  Keep a `Map<String, Entity>` populated as you set the queue (the app always supplies it), so the
  current song is known without a DB round-trip.

## Error messages that lie: coroutine cancellation and transient failures

Three causes of "an error appeared but it played fine". None of them comes from the remote
service; all three are in the app.

### `CancellationException` swallowed by `catch (e: Exception)`

`CancellationException` is a subclass of `Exception` **and** `RuntimeException` — verified on the
JVM (`instanceof Exception == true`), so `catch (e: Exception)` catches it. Every cancelled job
throws it, so a debounce pattern (`job.cancel()` then `launch` again on input change) converts
normal cancellation into a visible error message whenever the cancel lands inside a `try` that is
awaiting the network. The user types quickly, and sees what reads as a search failure.

```kotlin
try {
    state = Success(repository.search(query))
} catch (e: CancellationException) {
    throw e              // REQUIRED: this is cancellation, not failure
} catch (e: Exception) {
    state = Error(e.message)
}
```

The `CancellationException` branch must be written **before** `catch (e: Exception)` and rethrow.
Apply it to every `try` inside a cancellable coroutine, not just search — save/insert paths have
the same exposure.

### A transient error is never cleared

ExoPlayer retries network hiccups itself. If `onPlayerError` writes `errorMessage` and nothing
ever removes it, the message sticks on screen while the track is audibly playing. Clear it the
moment playback actually runs:

```kotlin
override fun onIsPlayingChanged(isPlaying: Boolean) {
    if (isPlaying && _state.value.errorMessage != null) {
        _state.value = _state.value.copy(errorMessage = null)
    }
}
```

General rule: **an error message must not outlive the condition it reports.** The inverse also
holds — a routine `syncState` must preserve `errorMessage` only while `!player.isPlaying`, or its
periodic updates wipe the message before the user can read it.

### The same track plays twice

Two app-side causes.

1. **The queue is built from a list that just received that track.** Saving the selected track to
the DB *before* building the queue, then writing `listOf(song) + otherList`, duplicates it when
`otherList` comes from a reactive query: the query has already re-emitted and now contains it.

   ```kotlin
   // WRONG — the new track is already in libraryResults by this line
   player.play(song, listOf(song) + libraryResults)
   // RIGHT — drop it first; reactive persistence already added it
   player.play(song, listOf(song) + libraryResults.filterNot { it.id == song.id })
   ```

   Fix the caller, then add a backstop in the queue builder so other callers cannot repeat it:
   `val unique = queue.distinctBy { it.id }` (keeps the FIRST occurrence, so the chosen track
   keeps its position).

2. **Tapping the currently-playing track from the same queue.** `setMediaItems` always starts at
   position 0, so re-tapping restarts the track from the top — which feels exactly like a double
   play. Guard: if the queue is identical, do not re-set it.

   ```kotlin
   val sameQueue = mediaItemCount == items.size &&
       currentMediaItemIndex == index &&
       currentMediaItem?.mediaId == items[index].mediaId
   if (sameQueue) { if (!isPlaying) play(); return@apply }
   ```

   Only for an identical queue. Tapping the same track from a *different* list (search results,
   playlist) must install the new queue.

## Loading and error surfaces in the player UI

- **Use a skeleton, not a spinner-plus-text, for list loading.** A skeleton row shaped like the
  real row (artwork block + two text bars) tells the user what is coming and stops the layout from
  jumping when results land. A text line replaced by a list shifts the whole screen. Implement the
  shimmer with a translating gradient, not an alpha pulse — on a dark theme an alpha pulse reads as
  flickering.
- **Style status text differently from error text.** If "searching…" and "something failed" share
  the accent colour, normal progress reads as a problem. Give loading a muted colour.
- **Never leave a transient error on screen once it recovers** (see above). The user's complaint is
  not the error text; it is that the text contradicts what they can hear.

## Position has no continuous callback

Media3 gives no per-tick position callback. Poll it while playing:

```kotlin
scope.launch {
    while (true) {
        controller?.takeIf { it.isPlaying }?.let { /* read currentPosition */ }
        delay(500)
    }
}
```

In the seek bar, separate `scrubbing` state from playback state — otherwise the 500 ms poll fights
the user's thumb mid-drag. Only `seekTo` on `onValueChangeFinished`.

## Log play history on transition, not on queue-set

Record "played" in `onMediaItemTransition` (it fires when a track actually starts). Recording when
`setMediaItems` is called fills "Recently Played" with tracks the user queued but never heard.

Dedupe by id and time inside that callback — Media3 can invoke it twice for one listen (once as the
queue is installed, once when the track truly starts), which double-counts `playCount` and repeats
the entry in Recently Played:

```kotlin
val isRapidDuplicate = id != null && id == lastMarkedId &&
    now - lastMarkedAtMs < 1_500L
```

A 1.5 s window is loose enough for device-speed variation and far tighter than any deliberate
replay. This is separate from the queue-duplication causes above: that one repeats the *audio*,
this one only repeats the *record*.

### "Listening time" must be measured, not inferred from track duration

When the stats screen needs "minutes listened", do **not** derive it from the song's duration
(`SUM(songs.durationMs)` over the play history). That claims the full length of every track the
user started — skip a 4-minute track at 0:05 and it still reports 4 minutes. The number is then
unfalsifiable-looking but wrong, which is worse than no number.

Accumulate real listening time instead:

- **Sum poll intervals only while `isPlaying`.** Do NOT take the wall-clock difference between
  start and stop — that counts paused time too, and the total inflates with no audio playing. The
  existing 500 ms position poll is the natural place to add the interval.
- **Write on track change or `onIsPlayingChanged(false)`, not every poll.** Writing each 500 ms
  means thousands of DB writes per track. On a track change, flush the *previous* track's total
  BEFORE recording the new one, or the time lands on the wrong song.
- **Store into the latest history row for that songId and do NOT zero the accumulator after a
  flush.** The value written is the running total that overwrites the same row, so repeated flushes
  are idempotent; clearing the accumulator instead would erase the time accumulated before a pause.

This needs a `listenedMs` column on the history table, which means a new Room migration and its
registration in the DI module — budget for that, not just the UI.

## Persisting the queue and position across app restarts

ExoPlayer holds the queue only in memory, so a killed process loses the track, the order, and the
position. Persist them to DataStore and restore on start. Four decisions, each preventing a
specific failure.

**Restore PAUSED, never autoplay.** Restoring a queue is not a request to play. `prepare()` after
`setMediaItems` makes the track ready, and ExoPlayer's `playWhenReady` defaults to false, so it
stays paused with no explicit `pause()`. If the app already decided "do not autoplay on open",
honour it: restoring straight into playback overrides that decision and surprises the user with
sound.

**Store the current track's ID, not its index.** Indexes shift: delete one song from the library
and every song after it moves down one, so the saved index now points at the wrong track. An ID
does not move. Keep the index only as a fallback for data written by an older version:

```kotlin
internal fun resolveRestoreIndex(queueIds: List<String>, savedCurrentId: String?, savedIndex: Int): Int {
    if (queueIds.isEmpty()) return 0
    if (savedCurrentId != null) {
        val byId = queueIds.indexOf(savedCurrentId)
        if (byId >= 0) return byId
    }
    return savedIndex.coerceIn(0, queueIds.lastIndex)   // clamp: the saved index may exceed the filtered queue
}
```

Clamp the fallback. A saved index can exceed the length of the queue that survived filtering (many
songs deleted), and `setMediaItems` with an out-of-range index throws, so the restore fails
entirely instead of degrading.

**Persist the queue as ONE newline-joined string, not a `stringSet`.** A `Set` does not preserve
order, and here the order IS the data. `joinToString("\n")` / `split("\n")` round-trips a list in
order; `stringSet` silently reshuffles it.

**Debounce queue writes; throttle position writes separately.** One user action touches the queue
several times, so debounce the queue save (~400 ms). Position is different: it is updated by the
500 ms polling loop, and a debounce does nothing for a periodic trigger — it fires on every tick.
Throttle it instead (write at most once per ~5 s).

```kotlin
private const val QUEUE_SAVE_DEBOUNCE_MS = 400L
private const val POSITION_SAVE_INTERVAL_MS = 5_000L
```

### Restoring a queue must not count as a play

`setMediaItems` fires `onMediaItemTransition` for the item it installs, and that callback is where
"played" is recorded — so a naive restore logs the last track as played on **every app open**,
inflating `playCount` and filling Recently Played with a track the user never heard this session.
The `lastMarkedId`/`lastMarkedAtMs` dedupe window does NOT cover this: it is a fresh process, so
there is no previous mark to compare against.

Guard with an explicit flag held across the whole install, released in `finally` so an exception
cannot leave it on (a stuck flag silently disables history recording for the rest of the session,
harder to find than the bug it prevents):

```kotlin
private var isRestoringQueue = false

// in the mark-played callback:
if (id != null && !isRapidDuplicate && !isRestoringQueue) { /* record */ }

// in restore:
isRestoringQueue = true
try {
    c.setMediaItems(items, index, savedPosition.coerceAtLeast(0L))
    c.prepare()
} finally {
    isRestoringQueue = false
}
```

Use a flag, not call ordering. Whether the transition callback arrives synchronously or on the
player's looper is not something to rely on, and "set the guard after `setMediaItems`" is a race.
Also seed `lastMarkedId`/`lastMarkedAtMs` with the restored track so an immediate real play of that
same track is not swallowed by the dedupe window.

## Sleep timer

Expire to **pause**, not stop. A pause keeps the queue and the position, so the user resumes exactly
where the timer caught them; `stop()` clears the queue and forces them to find the track again.
`pause()` is the whole feature.

**Count down from an end timestamp, not by decrementing a counter.** Compute
`sleepTimerEndsAtMs = now + durationMs` once, then let the ~1 s UI tick read `endsAt - now`. A tick
that subtracts a fixed amount per iteration drifts whenever the coroutine is delayed (the UI tick
is best-effort), so the timer fires late by however much the loop was starved.

**Carry the field through `syncState` explicitly.** A UiState rebuilt from a fresh constructor on
every player event drops any field not sourced from the player — the remaining-time value vanishes
on the next sync. Preserve it the same way `errorMessage` is preserved. The general rule: **every
field in the playback UiState that does not come from the player must be carried forward by hand in
`syncState`, or the periodic sync will erase it.**

## A listening-stats screen: the decisions that make the numbers honest

The stats screen is where a wrong decision is invisible — it renders fine and the numbers look
plausible. Each rule below exists because the alternative produces a number nobody can trust.

**Exclude skip-throughs with a minimum-listen threshold, applied in the STATS QUERIES ONLY.**
Insert the history row as the track starts (Recently Played depends on it), but filter
`listenedMs >= :minListenedMs` in every aggregate. Pass the threshold as a query parameter with a
default, not as a literal buried in the SQL — it makes the threshold testable and changeable without
touching the query. Browsing the library and skipping through a dozen tracks otherwise fills "top
songs" with tracks nobody heard. State the accepted cost: a track shorter than the threshold never
enters the statistics at all.

If the threshold becomes user-configurable, keep the default in ONE place and read it from both the
UI and the DAO. Two literals (a UI default and a DAO default) drift apart, and the settings screen
then displays a value the query does not actually use.

**Bucket by hour-of-day and day-of-week, not "the last N days".** The range selector may be set to a
year, where a "last 7 days" chart means nothing. Hour/weekday buckets answer the same question at
every range.

**`'localtime'` in the `strftime` call is mandatory.**

```sql
SELECT CAST(strftime('%H', datetime(playedAt / 1000, 'unixepoch', 'localtime')) AS INTEGER) AS slot,
       COALESCE(SUM(listenedMs), 0) AS listenedMs
FROM play_history
WHERE playedAt >= :since AND listenedMs >= :minListenedMs
GROUP BY slot ORDER BY slot ASC
```

`'%w'` for weekday returns **0 = Sunday**, which the UI maps back
(`DayOfWeek.of(if (slot == 0) 7 else slot)`) rather than reordering in SQL. `CAST(... AS INTEGER)` is
required because `strftime` returns text. Without `'localtime'` the whole chart shifts by the
device's UTC offset — a 21:00 listen in WITA buckets as 13:00, wrong for every user in that zone and
indistinguishable from a broken query.

**Plot time listened, not play count, on the charts.** The question is "when do I listen most", and
one long track heard fully outweighs three short ones skipped. Keep play count as the ranking key for
the top-N lists — a short track played five times really is more frequent than a long one played once
— and show listened time as the secondary line.

**Model failed separately from empty.** `Loading | Ready(data) | Failed(message)`; `Ready` with zero
plays is the empty state, `Failed` gets its own message and a retry. Collapsing failure into empty
makes a broken query look like "you have not listened yet". Emit `Loading` on every range change
(`onStart`) so the previous range's numbers do not linger as if they were the new range's, and keep
the range selector visible in every state — a user stuck on an empty range needs a way out.

### Verify the analytics SQL against a real database, not by reading it

`SELECT` statements are the second thing you can fully verify headless (a Room migration is the
first). Build a throwaway SQLite database with the real table definitions, insert rows whose expected
buckets you already know, and run the **queries extracted from the DAO source** — not retyped by
hand, which would test a different query than the one that ships:

```bash
python3 scripts/verify-dao-queries.py \
  --dao app/src/main/kotlin/<pkg>/data/db/dao/PlayHistoryDao.kt \
  --db /tmp/stats.db --params since=0,minListenedMs=30000,limit=5
```

Seed rows that make the timezone and the threshold observable: a 21:30 local timestamp must bucket as
hour 21 (not 13), and a row just under the threshold must drop out. Run each query with the
threshold on and off and confirm the counts differ by exactly the skip-through rows — equal counts
mean the parameter never reached the `WHERE` clause.

#### Derive the fixture SCHEMA from the exported JSON, never from your own typing

`scripts/verify-dao-queries.py` runs the extracted SQL against a database you supply, so that
database's schema is the other half of the test — and a hand-typed `CREATE TABLE` is as untrustworthy
as a hand-typed query. If the fixture is missing a column the query selects, you get a SQL error and
fix it; if it has a column the real table does NOT, the test passes against a table that does not
ship, and you conclude a broken query is fine. Build the fixture from the artifact that is generated
from the entity:

```bash
# the exported schema is the same source of truth the migration validator uses
python3 - <<'PY'
import json, sqlite3
spec = json.load(open("app/schemas/<pkg>.data.db.BlossomDatabase/5.json"))
ent  = next(e for e in spec["database"]["entities"] if e["tableName"] == "songs")
conn = sqlite3.connect("/tmp/verify.db")
conn.execute(ent["createSql"].replace("${TABLE_NAME}", ent["tableName"]))
for idx in ent.get("indices", []):
    conn.execute(idx["createSql"].replace("${TABLE_NAME}", ent["tableName"]))
conn.commit()
PY
```

Then insert fixtures with explicit column names (`INSERT INTO songs (id, album, albumKey, …) VALUES
(…)`) rather than positional `VALUES` — a positional insert silently shifts every value the moment a
column is added to the entity, and the assertions then pass against misaligned data. After building
the fixture, `PRAGMA table_info(songs)` and confirm the column set matches the entity: that one
command is what distinguishes "the query is right" from "the query is right about a table I made up".

A fixture for a grouping query must contain the adversarial rows, not the easy ones: two DIFFERENT
artists sharing an album title, a compilation whose tracks have different artists, a row with no
album at all, and a legacy row whose key column is still empty. The plain happy path — three tracks
from one artist — passes against the broken `GROUP BY album` too, which is exactly why the bug
reached a device.

## Room: migrate, never destroy

When the user may already have scanned data, `fallbackToDestructiveMigration()` silently wipes it.
Write an explicit `Migration` and register it with `.addMigrations(...)`.

**Room compares the migrated schema STRUCTURALLY, not by SQL text** — so "byte-match the generated
`createSql`" is the wrong target. An `ALTER TABLE` result never contains the `IF NOT EXISTS` that
Room's `createSql` carries, so the two strings always differ even when the schema is correct; a
text comparison is permanently red and proves nothing. What Room actually checks is the column set
and per-column type/notnull/default plus the index set. Treat the generated
`app/schemas/<version>.json` as the source of truth for *what to write*, and validate the result
with `PRAGMA table_info` + `PRAGMA index_info` (see the validator below), never by diffing SQL text.

#### `ADD COLUMN … DEFAULT NULL` is rejected by Room — write it without the default

For a nullable column, `ALTER TABLE songs ADD COLUMN folderUri TEXT DEFAULT NULL` looks correct and
compiles, but it stores the **literal string `'NULL'`** as the column default. `PRAGMA table_info`
then reports `dflt_value='NULL'`, while Room's expected `TableInfo` has `defaultValue = null` (the
generated schema JSON has no `defaultValue` key). The mismatch makes Room throw
"Migration didn't properly handle" on the **first open of the upgraded database** — a crash that no
build or lint run can surface, because the SQL is only evaluated on the user's device.

```kotlin
// WRONG — leaves dflt_value = 'NULL', Room rejects the migration at runtime
db.execSQL("ALTER TABLE `songs` ADD COLUMN `folderUri` TEXT DEFAULT NULL")
// RIGHT — dflt_value stays empty, which is what Room expects for a nullable column
db.execSQL("ALTER TABLE `songs` ADD COLUMN `folderUri` TEXT")
```

#### Validate the migration without a device — build both schemas in SQLite

A migration is the one part of an Android app you can fully verify headless, because Room's check is
pure schema comparison. `scripts/validate-room-migration.py` replays it: it creates a database from
the **old** exported schema, runs your migration statements, then compares the result against the
**new** exported schema the same way Room does — including normalising `''` / `'NULL'` / `null`
defaults, which is the check that catches the trap above.

```bash
python3 scripts/validate-room-migration.py \
  --schemas app/schemas/com.example.data.db.AppDatabase \
  --from 2 --to 3 --sql /tmp/migration_2_3.sql
```

Write the migration's `execSQL` strings, one per line, into the `--sql` file first. Run it for every
hop (`1→2`, then `2→3`) — a user several versions behind replays them in order, so each individual
hop must be valid, not just the total. This turns "the migration SQL looks right" into a fact.

### Never upsert with `REPLACE` — it silently resets user-owned columns

`@Insert(onConflict = OnConflictStrategy.REPLACE)` deletes the existing row and inserts a new one, so
every column the scanner does not supply returns to its default. On a rescan that wipes
`playCount`, `lastPlayedAt`, `isDownloaded` — the columns a player accumulates over weeks of use.
The damage is invisible until the stats screen is built and every count reads zero.

Split the two concerns: `IGNORE` for genuinely new rows, a metadata-only `UPDATE` for existing ones,
both inside one `@Transaction` so an interrupted scan cannot leave the table half-written.

```kotlin
@Insert(onConflict = OnConflictStrategy.IGNORE)
suspend fun insertIgnore(songs: List<SongEntity>)

@Query("""UPDATE songs SET title = :title, artist = :artist, album = :album,
          durationMs = :durationMs, uri = :uri, videoId = :videoId,
          thumbnailUrl = :thumbnailUrl WHERE id = :id""")
suspend fun updateMetadata(id: String, title: String, /* … */)

@Transaction
suspend fun upsertAll(songs: List<SongEntity>) {
    insertIgnore(songs)
    songs.forEach { updateMetadata(/* … */) }   // stats columns omitted on purpose
}
```

Room accepts `@Transaction` on an interface default method — no abstract class required.

## Artwork: never hand an audio URI to an image loader

A song's playable URI (`content://media/external/audio/media/123`) is not an image, and Coil cannot
load it — the request fails and the placeholder shows forever, which reads to the user as a broken
feature rather than "this album has no cover". Build the album-art URI separately from `ALBUM_ID`:

```kotlin
ContentUris.withAppendedId(
    Uri.parse("content://media/external/audio/albumart"), albumId,
).toString()
```

Store that in a dedicated column (`thumbnailUrl`); for streamed tracks the same column carries the
thumbnail URL. Guard `albumId <= 0` → `null`.

Two consequences worth remembering:

- Aggregating covers with `MIN(uri)` over the songs table returns an *audio* URI, so the album card
  is permanently blank. Aggregate the artwork column (`MIN(thumbnailUrl)`) instead.
- `content://media/external/audio/albumart/<id>` is not guaranteed on every OEM/API level. Treat a
  failed load as "no cover" (placeholder), never as an error; `ContentResolver.loadThumbnail`
  (API 29+) is the more reliable fallback if placeholders turn out to be common in the field.

## Media3 `@UnstableApi` — opt in with `androidx.annotation.OptIn`

Some Media3 symbols are `@UnstableApi`, which is itself an
`androidx.annotation.RequiresOptIn(level = ERROR)`. Using one without opt-in fails **lint**
(`UnsafeOptInUsageError`) and therefore the build — a gate, not a warning.

The opt-in annotation must be `androidx.annotation.OptIn`. The Kotlin `kotlin.OptIn` does **not**
satisfy `androidx.annotation.RequiresOptIn` and the error persists. Confirm which one a marker wants
before writing:

```bash
javap -v -classpath "$MEDIA3_COMMON_API_JAR" androidx.media3.common.util.UnstableApi \
  | grep -i RequiresOptIn      # -> Landroidx/annotation/RequiresOptIn;
```

Confine the opt-in to a small helper instead of annotating a whole class:

```kotlin
@OptIn(UnstableApi::class)
private fun MediaItem.restoreUri(): MediaItem = /* … */ this
```

### Do NOT gate `onConnect` on `isTrusted` — it kills your own controller

`ControllerInfo.isTrusted` is **false for an ordinary app, including your own UI process**. Media3's
`MediaSessionManagerImplBase.isTrustedForMediaControl` returns true only for system-permission
holders (`MEDIA_CONTENT_CONTROL`, `STATUS_BAR_SERVICE`), uid 1000, or a notification listener.
`MediaSessionStub.connect()` guards only *trusted* controllers (its own comment: "Don't reject
connection for trusted app"); for an untrusted one `ConnectionResult.reject()` drops the connection
outright, so the `MediaController` never connects and **every play attempt fails with a connection
error** — a silent-looking dead end that the UI reports as "service connection failed".

The correct pattern (as in Metrolist and ArchiveTune) is to **not override `onConnect` at all** and
let `super` accept with the default commands. Silence lint's `ExportedService` warning with
`tools:ignore="ExportedService"` on the `<service>` — never with a runtime trust guard.
`exported="true"` itself is required for Android Auto / assistant discovery, so do not remove it.
Full mechanism and bytecode evidence: the `media3-session-uri` skill.

## MediaStore scanning

```kotlin
val selection = "${MediaStore.Audio.Media.IS_MUSIC} != 0 AND " +
                "${MediaStore.Audio.Media.DURATION} > 0"
```

`IS_MUSIC != 0` drops ringtones/notifications/recordings; `DURATION > 0` drops broken files.

**Normalise `MediaStore.UNKNOWN_STRING` (`"<unknown>"`) to null.** Empty tags come back as that
literal, and it then becomes a real artist/album name in `GROUP BY artist` — one junk row per
library instead of a null you can filter.

Derive albums/artists with `GROUP BY` over the songs table rather than separate tables until you
actually need album-level metadata; it keeps the scan idempotent and the schema small.

### Group by a stable IDENTITY KEY, never by the display name

A library's "album" is not its album title. Titles are not unique — `Greatest Hits` exists for every
artist — so `GROUP BY album` merges two different albums into one list holding both artists' tracks.
The screen still renders, which is why this survives review: it reads as "this album has the wrong
songs", not as a broken query. Give each song a stored key and group by that:

```sql
COALESCE(
    NULLIF(albumKey, ''),
    CASE
        WHEN album IS NULL OR album = '' THEN '__no_album__'
        ELSE 'tag:' || LOWER(COALESCE(albumArtist, artist, '')) || '|' || LOWER(album)
    END
) AS albumKey
```

Two key forms, in preference order: `ms:<albumId>` when MediaStore supplies a real album id (the
system already separates same-titled albums, so it is exact), otherwise `tag:<albumArtist>|<album>`
from the tags. Put the album ARTIST in the key, not the track artist: on a compilation every track
has a different artist, and keying on the track artist shatters one album into dozens of one-track
"albums". Use the album artist, falling back to the track artist only when the album-artist tag is
absent. Lower-case both parts so `Abbey Road` and `abbey road` stay one album.

### "No value" is a bucket, not a filter

`WHERE album IS NOT NULL AND album != ''` silently deletes every loose track — single downloads,
untagged files — from the Albums screen. Those are exactly the rows a user looks for. Keep them in
their own bucket under a sentinel key and sort that bucket last. Do not give the bucket a release
type label: a pile of unrelated loose tracks is not a "Single". Pick a sentinel that cannot collide
with a real key (real keys always start `ms:`/`tag:`).

### A key computed in TWO places must be byte-identical — test the parity

The write path (the scanner, Kotlin) and the read path (the aggregate, SQL) each compute the same
key. If the two formulas differ by a separator or a case fold, a scanned song is written under one
key and looked up under another — it vanishes from its album, or one release shows up twice. Review
cannot catch this: each formula looks reasonable alone. Prove it as a fact by building the key string
both ways and comparing (`tag:` + lower(albumArtist ?: artist) + `|` + lower(album)), and let the
same fixture that proves the grouping prove the parity.

On a library whose rows predate the key column, the SQL FALLBACK runs, not the stored column — so the
fallback formula is the one that must match Kotlin exactly. `COALESCE(NULLIF(albumKey, ''), <fallback>)`
is what lets old and new rows sit in one consistent grouping before the next rescan fills the column.

**Prefer a derived table over `GROUP BY <output alias>`.** SQLite accepts an output alias in
`GROUP BY`; standard SQL does not, and Room's query verifier is stricter than SQLite. Grouping over a
subquery that computes the key as a real column is unambiguous and portable:

```sql
SELECT albumKey, MAX(album) AS name, COUNT(*) AS songCount, MIN(thumbnailUrl) AS coverUri
FROM (
    SELECT album, albumArtist, artist, thumbnailUrl,
           COALESCE(NULLIF(albumKey, ''), CASE ... END) AS albumKey
    FROM songs
)
GROUP BY albumKey
```

Order tracks inside an album by track number, not title — and note a `trackNumber` tag is often
`"3/12"`, so take the digits before the slash. Songs with no track number sort last
(`CASE WHEN trackNumber IS NULL THEN 1 ELSE 0 END` first in the ORDER BY), and because the column is
an integer, `1, 2, 10` orders correctly where a text column gives `1, 10, 2`.

**Release type (single / EP / album) is an INFERENCE, not metadata.** Neither MediaStore nor file
tags record it reliably, so the only honest source is the track count — one track = single, a few =
EP, more = album — with the thresholds in ONE named constant so they can be corrected against a real
collection. Say in the comment that it is an estimate; never present it as read from the file.

### Scanning folders MediaStore does not index — SAF

MediaStore only exposes locations the system has indexed. Music in an excluded folder, or on some
SD cards, is invisible to it. Storage Access Framework access to a user-picked folder is the fix,
and it is a different mechanism with its own traps (persistable grants, recursive `DocumentFile`
walk, `MediaMetadataRetriever`, de-duplication against MediaStore, stable ids). See
`references/saf-custom-folder-scanning.md` before writing that code.

## Compose trap: a fixed-`size` composable cannot fill its parent

A component like `CoverImage(song, size: Dp)` that applies `.size(size)` internally locks the
caller out of responsive layouts — `size = 0.dp` renders nothing. Provide a second entry point
that takes size from the modifier instead:

```kotlin
@Composable fun CoverImage(song: SongEntity?, size: Dp, modifier: Modifier = Modifier) =
    CoverImageBox(song, modifier.size(size))

@Composable fun CoverImageBox(song: SongEntity?, modifier: Modifier = Modifier) { /* no .size() */ }
```

## Kotlin trap: `apply {}` returns the receiver, poisoning lambda inference

```kotlin
val action = { controller?.apply { play() } }   // type is () -> MediaController?, not () -> Unit
val pending: (() -> Unit)? = action            // compile error: assignment type mismatch
```

Annotate the lambda type (`val action: () -> Unit = { ...; Unit }`) or end it with `Unit`. Bites
whenever a stored-lambda slot meets an `apply`/`also`/`let` as the last expression.
