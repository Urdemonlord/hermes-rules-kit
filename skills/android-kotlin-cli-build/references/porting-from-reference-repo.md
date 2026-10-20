# Porting a Feature or Client Module from Another Android/Kotlin Repo

Use when the user says "integrate X like repo Y does it", "port this from <repo>", or "add
<third-party service> support and check <other app> for how". The work is rarely "copy the module":
it is licence decision → version gate → seam mapping → logic port → per-layer compile.

## 1. Licence first, and get the user's DECISION, not their assumption

Read the source repo's `LICENSE` **before** reading code with intent to reuse it, and state the
consequence in plain terms: a GPL/AGPL source dropped into a permissive or unlicensed project
propagates that licence to the whole project, and the user carries the exposure.

Then offer the fork explicitly, because both answers are legitimate and only the user can pick:

| Choice | What it costs |
|---|---|
| **Re-implement the pattern** in your own words | Keeps the target project's licence; you keep the ideas (data shape, threshold values, query form, state model) and discard the expressions |
| **Adopt the copyleft licence and port the code** | Fastest and battle-tested, but the target repo becomes GPL — see step 1b |
| **Use the vendor's official API** | No licence question, but often needs credentials/OAuth the unofficial path avoids |

Do not silently pick for them. "Make X like repo Y" means *referenced from*, not *copied from*.

### 1b. If the user adopts the copyleft licence, the obligations are concrete work

Not a note for later — do it as part of the port:

1. Add `LICENSE` at the repo root with the full licence text (note if the project previously had none).
2. Put an attribution header on **every ported file**: source project, author, licence, and a pointer
to the root `LICENSE`. GPL §4/§5 require preserving notices, so a ported file that loses its
original header is a compliance gap, not a style issue.
3. Say it in `README.md` so a reader learns it without opening source files.

Leave files you wrote from scratch unheadered — a blanket header on the whole tree is wrong and
muddies which code is actually derived.

## 2. Version-compatibility gate — run this before writing any file

A module that compiles in its home repo can be un-portable into yours. Diff the version catalogs
**first**:

```bash
# target
grep -E '^(kotlin|agp|ksp|hilt|composeBom) ' gradle/libs.versions.toml
# source (from a local clone)
grep -E '^(kotlin|agp|ksp) ' <source>/gradle/libs.versions.toml
grep -n -i 'ktor\|<other-transitive-lib>' <source>/gradle/libs.versions.toml
```

The trap: the source module depends on a library that requires a **newer Kotlin** than the target
is pinned to. Concretely, Ktor 3.x requires Kotlin 2.1+, so a Ktor-based client cannot be dropped
into a Kotlin 2.0.x project. Bumping Kotlin is not a one-line change — it drags KSP, Hilt, and the
Compose compiler plugin with it, on a project that currently builds and ships.

**Prefer porting the LOGIC and rewriting only the transport onto a dependency the target already
has.** Swapping a Ktor client for OkHttp + kotlinx.serialization keeps the port faithful (same
endpoints, same persisted-query hashes, same match scoring), leaves the version catalog untouched,
and adds nothing new to justify or to break. Say so in the report — it is a deliberate deviation
from "port verbatim", and the user should know it happened.

## 2b. Verify what the reference repo ACTUALLY does before building to the user's description of it

A user asking "make X like repo Y" usually has a partial mental model of Y, and it is often wrong in
a way that changes the whole design. Before writing code, check the load-bearing claim in Y's own
source. Worked example: the user believed the reference app streamed audio from the vendor because
it showed the vendor's artwork and metadata; the code showed it resolved every track to a *different*
backend to play it, so "add real vendor streaming" would have been building the wrong feature.

```bash
# does the reference actually ship the vendor's playback stack?
grep -riE '<vendor-sdk>|<playback-lib>' <source>/gradle/libs.versions.toml <source>/*/build.gradle.kts
grep -rn -iE 'audio|playback|stream|cdn|decrypt' <source>/<vendor-core-module>/src/
```

Read the function that is supposed to do the disputed thing and follow where its data comes from
(`resolveToMetadata` → whose search API?). Then correct the premise in the report **before**
implementing, with the evidence: the user is about to spend a session on an assumption, and "the part
you got right is A; the part that is not true is B, here is the line" is worth more than a silent
redesign. Do not implement the user's stated mechanism just because they stated it.

## 2c. When the target persists before it can play, the port needs a save-bridge

The target's architecture can make the source's flow impossible to copy verbatim. Example: the
source app could queue a vendor track directly from its resolved metadata, but the target could only
queue a row that already exists in its database (`SongEntity.id` is the queue/lyrics/stats key).
Mirroring "browse the whole account library live" then means: show the live list from the vendor,
and on tap run *resolve → save → play* through the target's existing save path.

Decide the persistence policy with the user explicitly (cache live lists in memory, persist only
what is played, versus mirror everything) — the two are very different products and the source repo
picked for its own reasons, not the target's. Then reuse the target's single save path rather than
growing a second one beside it.

**Any per-account in-memory cache you add for the live list must be cleared on BOTH sign-in and
sign-out.** A cache keyed to nothing (a plain field on a singleton repository) survives an account
switch, so the next user sees the previous user's library until the app is killed. Clearing on
logout alone is not enough — a user can sign in to a second account without the first having
logged out cleanly. Wire the invalidation into both paths, and into the token-refresh failure path
that drops the session, at the same time you introduce the cache. This is a privacy leak, not a
stale-data bug: the failure mode is one user reading another's data.

## 3. Map the target project's EXISTING SEAMS before writing anything

The port is usually far smaller than the source module suggests, because the target already has the
hard parts. Spend a few reads finding them; each one you find deletes a file from the plan.

Ask: does the target already have a data model for the thing being imported, a repository entry
point, and a place to resolve the external identity?

Worked example (importing a Spotify playlist into a YouTube-backed player):

| Needed | Already present in target | Consequence |
|---|---|---|
| A row for a streamed track | `SongEntity(source = STREAM, videoId, thumbnailUrl)` | Spotify tracks become ordinary rows; **no schema change, no migration** |
| A save path | `MusicRepository.saveStreamSong(StreamSearchResult)` | The import writes through the existing API |
| Metadata enrichment | `StreamSource.resolveMetadata(videoId)` | No new fetch path |
| Playback | `ResolvingDataSource` resolving URLs at play time | **The entire source repo's playback layer is irrelevant** |

That last row is the big one: the reference app resolved its tracks to a *different* backend to play
them at all. The target already had that pipeline, so the port reduced to *import + search*, and the
playback half of the source repo was never read. Report the reduction — "this is an importer, not a
second player" is the finding the user needs.

## 4. Extract as a pure module, not into the app package

Put ported third-party client code in its own module with a narrow, checkable boundary:

Wiring a new module takes **three** files, and the one people forget is the root one — omit it and
the module's plugin alias fails to resolve:

```kotlin
// settings.gradle.kts
include(":spotifycore")   // pure JVM: HTTP + JSON only
```

```kotlin
// build.gradle.kts (ROOT) — declare the plugin once, for the whole build
alias(libs.plugins.kotlin.jvm) apply false
```

```kotlin
// <module>/build.gradle.kts
plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
}
kotlin { jvmToolchain(17) }   // match the app's JVM target

dependencies {
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    // Coroutines must be EXPLICIT here even though the app already has it — see below.
    implementation(libs.kotlinx.coroutines.core)
    testImplementation(libs.junit)
}
```

**Declare every dependency the ported code uses, even ones the app already has.** In an Android app
`kotlinx-coroutines-core` arrives transitively (via lifecycle/Compose), so the source compiles without
a direct declaration and you never think about it. A JVM-pure module has no such transitive chain: the
moment the ported client touches `Dispatchers.IO` or a `Mutex`, the module fails to compile while the
identical source builds fine inside `:app`. Add the catalog entry and the `implementation(...)` line.
Do **not** "fix" it by folding the module back into the app package — that trades an explicit
dependency for the unverifiable boundary the module existed to create.

A JVM-pure module cannot touch Android or the database, which means (a) the boundary is enforced by
the compiler rather than by discipline, and (b) its parsing and scoring logic is unit-testable on
the headless host — the one part of an Android feature you can actually assert on without a device.
Do not pull `:spotifycore`-style modules into the app package "to keep it simple"; that is what
makes the port unverifiable.

## 5. Compile per layer

Port in this order and compile between layers (see the main SKILL.md section on
`compileDebugKotlin`):

1. **Models** (serialization-only) — no dependencies, no risk.
2. **Pure logic** (auth/TOTP, hash provider, match scoring) — testable without a device.
3. **HTTP client** — build the module alone (`./gradlew :<module>:build`) before the app ever
   references it.
4. **Repository + ViewModel** — session storage, token refresh.
5. **UI + import flow** — last, and the only layer needing a device to truly verify.

Steps 1–3 give a green signal with zero Android involvement. Landing all five before the first
compile is how a port ends with no usable code.

Run the app-level gate as **one background job, not a foreground call**. `./gradlew :app:lintDebug
:app:assembleDebug` on a Compose project routinely runs for minutes and will outlive the foreground
tool timeout; a killed foreground call leaves you unsure whether it finished or died. Redirect to a
log, run it in the background with completion notification, and read the tail. Then confirm the
artefacts rather than the exit banner: the APK's size and timestamp, and the lint report's **error**
count. "Lint passed with warnings" and "lint has zero errors" are different claims, and only the
error count is the gate.

## 5b. The target's seam carries a THREADING contract too, and a ported `catch` hides a breach

Step 3 finds the target's entry point; do not stop at its signature, read what the seam *does*. A
repository method that exists precisely to wrap a blocking call in `withContext(Dispatchers.IO)` is
not interchangeable with the raw source it wraps. Calling the raw source directly from a
`viewModelScope.launch` runs the blocking call on the **main thread**, which on Android throws
`NetworkOnMainThreadException`.

The result is the worst diagnostic shape there is: the operation reports **success** with **zero
output** and **no log line**. If the ported loop catches per-item failures so one bad track cannot
abort the import, that exception is swallowed into "no match found". The list itself loads (its own
fetch is wrapped), every item is silently skipped, and the UI says the work finished. Nothing in the
build, the lint report, or the screen distinguishes it from "none of these items exist upstream".

```kotlin
// WRONG, the seam is the IO wrapper; this bypasses it
matcher.match(track) { q -> streamSource.search(q) }

// RIGHT, go through the seam that owns the dispatcher
matcher.match(track) { q -> musicRepository.searchStreams(q) }
```

Two rules fall out, both cheap at port time:

1. **Route every call to a blocking source through the target's own IO-wrapped seam**, never the
   source underneath it. The seam exists to own the dispatcher; bypassing it deletes the only thing
   it was for. Do not "fix" this by adding your own `withContext` at the call site when the seam
   already exists, that is a second path beside the one the rest of the app uses.
2. **A per-item `catch` in ported code must not be able to swallow a systemic failure.** A catch
   written for resilience ("one item failing must not kill the import") is exactly what makes a
   *total* failure (expired session, rotated query hash, main-thread violation) look like an empty
   result. Give the swallow a counter and a hook (`onSearchFailure`) so the caller can log and count,
   and **install the ported client's logger**. A ported HTTP client almost always has a pluggable
   logger (ArchiveTune's `Spotify.logger`) that the target never wires up, so every diagnostic the
   source repo emits is dropped on the floor; wire it to the platform log before device testing, or
   the next failure is equally invisible.

Symptom to recognise: *"it worked (login/load) but produced nothing, with no error"* is the signature
of a swallowed exception, not of empty upstream data. Reach for the swallow and the dispatcher before
you doubt the network.

## 6. Prove parity with the reference — sweep for what you did NOT mirror

When the user's instruction is "make it behave like <repo>, it's proven to work", the port is not
finished when it compiles: it is finished when you have swept the reference for mechanisms you left
out and can account for each one. Do this as two mechanical passes, not by re-reading the source.

**Pass 1 — constants and tuning values.** Extract every magic number the reference uses in the
ported code path and diff it against yours. This is the cheapest high-value check there is: a
dropped cache size or a different threshold changes behaviour invisibly, with no compile or lint
signal.

```bash
# every constant the reference declares in the ported area
grep -rnE 'const val|private val [A-Z_]+ *=' <source>/<module>/src/ | grep -iE 'cache|size|threshold|weight|batch|limit|max|timeout'
```

Then write the comparison into the report as a table (reference value | your value | same?). A row
that does not match is either a bug or a deliberate deviation — say which. A row you cannot fill in
means you did not find the constant, not that it does not exist.

**Pass 2 — mechanisms, not just values.** Grep the reference for the *structural* things a port
silently omits: caches, retry/backoff, dedup, concurrency limits, pagination guards, cancellation.

```bash
grep -rnE 'LinkedHashMap|LruCache|cache|retry|backoff|delay\(|Semaphore|chunked|distinctBy' <source>/<module>/src/
```

Worked example: the reference wrapped its resolve step in an LRU cache (512 entries, access-ordered)
so a repeated tap did not re-hit the network. The port had none — correct-looking code that simply
re-searched on every tap. Nothing in the compiler or the linter surfaces a missing cache; only this
sweep does. When you find one, mirror the mechanism *and* its constant, then recompile.

**Pass 3 — runtime view configuration.** Anything that configures how a platform component renders
or behaves at runtime is invisible to every build gate: it compiles, lints clean, and ships, then
does nothing on the device. If the ported flow uses a `WebView`, diff the reference's `WebSettings`
and its client classes line by line, not just the URL it loads:

```bash
grep -n -A 20 'settings.apply\|settings\.\|configureSpotifyLoginWebView' <source>/app/src/main/kotlin/<...>/BackupAndRestore.kt
grep -n 'userAgentString\|WebChromeClient\|onCreateWindow\|mixedContentMode' <source>/app/src/main/kotlin/<...>.kt
```

Worked example: the ported Spotify login `WebView` loaded the correct URL with JavaScript and DOM
storage enabled, so it looked complete. On the device the page was **solid black with no error text**.
Two things were missing, both runtime-only:

- **`userAgentString`.** The default WebView UA contains a `WebView` marker, and the login provider
  served an empty page for it — not an error, just nothing. The reference set a Chrome-like UA with
  no such marker. Any time a ported WebView loads a third-party auth page, assume the UA matters and
  copy the reference's value verbatim.
- **`WebChromeClient.onCreateWindow`.** The login page opened its "sign in with Google/Facebook"
  flow via `window.open`, so without an `onCreateWindow` override the popup is never created and the
  button silently does nothing. `setSupportMultipleWindows(true)` alone is not enough — it enables the
  request, it does not service it. The reference's chrome client creates a second `WebView` and
  attaches it to a shared `FrameLayout`, which is also why the reference's `factory` returns a
  container rather than a bare `WebView`; mirror that structure or the popup has nowhere to mount.

The general rule: when a ported feature works in the source and does nothing in the target, and the
build is green, stop reading the Kotlin and start diffing **configuration** — UA strings, client
overrides, manifest flags, theme attributes, permission grants. Those are the layers no compiler
checks, and a black screen with no error message is their signature.

Do this sweep before you report the port complete, and report what the sweep found — including the
honest "nothing was missing", which is itself the parity evidence.

## Pitfalls

- **Budget the reconnaissance, or you will spend the whole session reading and write no code.**
  A faithful port tempts you into reading the source client end-to-end first — a 1,500–2,000-line
  API client plus auth, hashes, models, repository, and UI is a large fraction of one session, and
  the file dumps are what actually drain it. Bound the read: capture the *shapes* you need
  (endpoint + variable payload + response field path for each call you will port) and the *values*
  you must reproduce (hashes, thresholds, weights), then stop and write. If a file is genuinely too
  big to read whole, hand it to a subagent with an extraction checklist and keep only the report.
  Read the one function you are porting immediately before porting it, not the whole file in advance.
  A session that ends with an accurate plan and zero compiled code is worth less than one that
  ported three layers.
- **Porting one feature does not license porting the neighbouring one unannounced.** A follow-up
  request ("now make the whole account library show up too") is a new scope with its own design
  questions — persistence policy, which lists exist, what tapping a row does. Do not extend the port
  silently because the modules are adjacent; surface the new decisions and let the user pick before
  writing. And when the port grows past the source's own model (the source had no "saved albums"
  list at all), say so and follow the source's structure rather than inventing one to fill the gap.
- **Report every deviation from "port verbatim" as it is made — but grep the source for the
  construct BEFORE calling it a deviation.** Faithful-port promises break the moment you adapt to the
  target (changing a transport, reshaping a type to a seam, persisting where the source did not).
  Each one is a real decision the user should hear, not a footnote discovered in review. If the user
  asks to be consulted per deviation, stop and ask at each one instead of batching them into a
  summary. The inverse error is worse and easier to make: announcing that you "deviated" by doing
  something the source also does. Naming a construct you half-remember as a deviation, when it is
  right there in the reference, is a false report the user cannot check without reading the source
  themselves — and it needlessly muddies a port that was in fact faithful. Before writing the word
  "deviation", run `grep -n '<construct>' <source>/<module>/src/` and quote the hit, or drop the
  claim. If you already told the user wrong, correct it in the open, first thing, with the line
  number — do not let it sit.
- **Do not report a port as done while the build config is unproven.** Editing
  `settings.gradle.kts`/`libs.versions.toml` and writing model files is not a working integration;
  say plainly that nothing has been compiled yet and what the next gate is. A handover that reads
  as "ported" when it has never built is the failure this whole recipe guards against.
- **Ported auth flows often depend on a third party's rotating secret.** A cookie → token flow that
  fetches a TOTP secret from a community gist, and persisted-query hashes that the vendor rotates,
  will break without any change on your side. Say this out loud when proposing the feature; it is a
  maintenance liability, not a one-time integration cost.
- **An unofficial-cookie integration is a ToS question as well as a technical one.** Reading a
  vendor's session cookie out of a WebView is not the same as using their documented API. Surface it
  with the licence question, before implementation, not in a postscript.
- **Shape your new types to the seam you found, not to a shape you invent.** Once step 3 identifies
  the existing entry point — say `saveStreamSong(StreamSearchResult)` — the ported code's matcher
  should return exactly that type. Returning the target's persistence entity (`SongEntity`) where the
  seam takes the transport result, or introducing an intermediate wrapper DTO, means you have quietly
  built a second path beside the existing one and the compiler will not warn you. An adapter class you
  added during the port and later deleted is the tell that you diverged from the seam.
- **`catch (e: Exception)` in ported coroutine code swallows `CancellationException`.** A
  retry/token-refresh helper written as a plain try/catch absorbs the cancellation its caller raised,
  so a cancelled scope keeps running and the coroutine never completes. Rethrow before the generic
  handler (`catch (e: CancellationException) { throw e }`). Cheap at port time, expensive to diagnose
  later.
- **Verify the port with the compiler, not with a partial grep.** `:module:compileKotlin`,
  `:app:compileDebugKotlin`, and successful dexing are the evidence that ported code exists and links.
  Do not try to confirm it by grepping a class name out of the APK: a modern app is multi-dex and
  `classes.dex` is only the first of N, so a zero-hit grep proves nothing and any "not found"
  conclusion drawn from it is wrong. If a claim cannot be verified, report the compile gate you did
  clear instead of a check that cannot fail correctly. If you do want the presence check as
  corroboration, sweep **every** dex and report the total, never one file:

  ```bash
  APK=app/build/outputs/apk/debug/app-debug.apk
  for d in $(unzip -l "$APK" | awk '/classes.*\.dex/{print $4}'); do
    echo "$d: $(unzip -p "$APK" "$d" | strings | grep -c 'meowlabs/player/spotify')"
  done
  ```

  A hit count spread across several dex files is the normal, correct result — classes land wherever
  the dexer puts them, so "absent from `classes.dex`" says nothing about whether the port shipped.
- **A new Gradle module is not covered by an anchored `.gitignore`, so `git add -A` stages its whole
  `build/` tree.** Patterns written as `/build` and `/app/build` are anchored to those two exact
  paths; the moment a module is added, `git status` lists hundreds of `.dex`, `.class`, Kotlin cache
  blobs, and the module jar as new files, and a careless `git add -A` commits all of it. Add a
  catch-all before the first commit that touches the module:

  ```gitignore
  **/build/
  ```

  Then confirm the staging area holds only source (`git status --short | wc -l`, and read the list)
  before committing. If it already went in, `git reset` and re-add — the artifacts are regenerable,
  the diff noise is not worth living with.
