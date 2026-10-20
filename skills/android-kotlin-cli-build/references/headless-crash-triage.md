# Triaging a user-reported Android crash with no device and no logcat

Depth for the case: a user says the app "force closes" on some screen, you have no device
attached, no stack trace, and the crash is intermittent. The goal is to **narrow or disprove
causes with evidence** — not to guess one and ship it as the fix.

## Step 0 — Is it a regression? Settle that first

`git diff v<previous-release>..HEAD -- <the files that screen uses>` (whole tree if unsure).
Byte-identical output on the screen's own files means your recent work did not touch that path:
stop hunting your last commit and treat it as a pre-existing bug never exercised on a device. It
also answers the user's real question — whether updating fixes it. (Same rule as the SKILL.md
pitfall of that name.)

## Step 1 — The deliverable may be "get the logcat", not a fix

With no stack trace, any root cause you name is a hypothesis. Do not close with "fixed", and do
not ship a speculative change labelled as the fix. The one command that ends the investigation:

```bash
adb logcat -c && adb logcat > /tmp/crash.log   # user reproduces, then send from FATAL EXCEPTION
```

Ask for the reproduction steps too (which action, which screen, always or sometimes, which build).
"Always vs sometimes" alone splits the candidate list below in half: intermittent points at a race,
an uncaught `Error`, or resource exhaustion, not a deterministic logic bug.

**Confirm which build variant the user is actually running before reasoning about build-time
tools.** `aapt2 dump badging <apk> | head -1` shows the package name; a `.debug` suffix means the
APK is the debug variant, so `isMinifyEnabled` / R8-obfuscation theories are moot and the debug
dex is the one to inspect. This session's R8-stripping hypothesis died exactly there — the
shipped artifact was `assembleDebug`. Check the artifact's variant, not the `release {}` block in
`build.gradle.kts`.

## Step 2 — Candidate causes for a force close with NO in-app error message

The absence of an error message is itself a signal: the app's own error handling did not fire.

- **An `Error`, not an `Exception`.** `NoClassDefFoundError`, `ExceptionInInitializerError`,
  `OutOfMemoryError`, `StackOverflowError` all bypass every `catch (Exception)` and `runCatching`
  in the call path and go straight to the crash handler. Grep whether ANYTHING catches them:
  ```bash
  grep -rn 'catch (.*Throwable\|catch (.*Error' app/src/main/kotlin/
  grep -rn 'CoroutineExceptionHandler\|setDefaultUncaughtExceptionHandler' app/src/main/kotlin/
  ```
  A `CoroutineScope(SupervisorJob())` with **no** `CoroutineExceptionHandler` turns any uncaught
  throwable in `scope.launch { ... }` into a process crash — `SupervisorJob` stops sibling
  cancellation, it does not install a handler.
- **Duplicate `key=` in a Compose lazy list.** `LazyColumn { items(list, key = { it.id }) }` throws
  `IllegalArgumentException` when two items yield the same key. Ask whether the source CAN emit
  duplicates (probe it, Step 3) — not whether it usually does. Resolution: Step 2b.
- **`stringResource(id, args)` format mismatch.** A string with the wrong number/kind of `%s`/`%d`
  throws `IllegalFormatException` at runtime, only on the branch that renders it.
- **Resource exhaustion.** A long list of remote thumbnails (Coil) or a large bitmap decode on a
  low-RAM device → `OutOfMemoryError` (again an `Error`). Intermittent by nature.

## Step 2b — Duplicate lazy-list keys: the bug is in the producer, not the UI

`IllegalArgumentException: Key "X" was already used` names the key value but not where the
duplicate came from, so the instinct is to inspect the screen — which is the one place the bug is
NOT. The key lambda on that screen is correct; the list it was handed genuinely contains a
duplicate. Fixing the key lambda (adding an index, hashing more fields) hides the symptom and
leaves the duplicate in the data.

Ask which layer owns identity, and whether that identity is unique **by construction**:

| Source of the list | Unique by construction? |
|---|---|
| Room query with `GROUP BY` or a `PRIMARY KEY` | Yes — `key = { it.name }` is safe here |
| `autoGenerate` primary key | Yes |
| Third-party API response | **No — assume not** |

A media search endpoint is the classic offender: YouTube Music returns the same video twice in one
response (once as the "song" art track, once as the "video"), so `videoId` is not unique even
though it is the natural key. Two items, one key, crash — and it is intermittent, because whether
the API duplicates depends on the query.

**Fix at the producer, and keep a second belt at the state layer.** Dedupe where the list is built
(`distinctBy { it.videoId }` inside the search function), and dedupe again where the UI's state is
assembled. Two places is not redundancy for its own sake: the first keeps every consumer clean, the
second states the invariant exactly where the UI depends on it, so a producer added later cannot
silently reintroduce the crash.

**Audit the whole app in one grep, not just the crashing screen:**

```bash
grep -rn 'key = {' app/src/main/kotlin/ | grep -v 'it\.id'
```

Every hit is a key that is not the primary key. For each, find where that list is built and confirm
uniqueness there — a `GROUP BY` in the DAO is a valid answer, a raw API response is not.

**The same identity collision has a second, quieter symptom: over-counted writes.** When two
upstream items can map to one downstream row and the store dedupes on insert
(`OnConflictStrategy.IGNORE`, `INSERT OR IGNORE`, an upsert on a composite primary key), an import
loop that increments `imported++` after every successful save reports more items than the table
actually holds. The user then sees "50 imported" over a list of 48.

Handle it before the write, not after: keep the downstream ids in a set, branch to a separate
`duplicates` counter, and report that number separately — the count is then honest AND the duplicate
costs no network round-trip (which matters when each item is a search request). If the write does
fail after the id was claimed, remove it from the set again, or the next legitimate item with that id
is wrongly counted as a duplicate. Expose the new counter in the result UI, or the discrepancy the
user can see between the two numbers stays unexplained.

## Step 3 — Probes that settle a hypothesis instead of guessing

Each one converts a guess into a fact; run them before changing code.

**Is a suspect class loaded at all on this path?** A class that is *referenced* but never loaded is
not the cause — prove loading before adding R8 keep/dontwarn rules:

```bash
java -verbose:class -cp <probe-classpath> Probe 2>&1 | grep -iE '<suspect/package>|javax\.script'
# no output = this code path never touches that class -> rule it out
```

**Which JDK classes does the APK reference that Android does not ship?** Full set, not just the one
you suspect:

```bash
unzip -l $ANDROID_HOME/platforms/android-35/android.jar | grep '\.class$' \
  | awk '{print $4}' | sed 's#/#.#g; s#\.class$##' | sort -u > /tmp/available.txt
strings -a app/build/outputs/apk/**/classes*.dex \
  | grep -oE 'L(java|javax|sun|com/sun)/[A-Za-z0-9_/$]+;' | sed 's/^L//; s/;$//; s#/#.#g' \
  | sort -u > /tmp/referenced.txt
comm -23 /tmp/referenced.txt /tmp/available.txt   # referenced but absent -> Error on first load
```

**Does the data source actually produce the bad shape?** Write a throwaway `main` that calls the
real code path N times (a batch of real queries, a set of real files) and asserts the shape you
suspect (duplicates, nulls, empty). One call proves nothing about an intermittent case; sample
dozens. Run it against the library's real jar so signatures match the build.

## Step 4 — When you cannot get a logcat, make the app record it (and keep the investigation open)

The best deliverable for an intermittent, message-less crash is a **persistent crash log in the
app itself**. It is the only thing that turns "it force closes sometimes" into a named class and
line, and it survives the process death that destroys `logcat` when no cable is attached.

Install a handler as the first thing the app does:

```kotlin
// Application.onCreate(), before any other component runs
val previous = Thread.getDefaultUncaughtExceptionHandler()
Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
    runCatching { writeReportTo(filesDir, thread, throwable) }   // must not itself throw
    previous?.uncaughtException(thread, throwable)               // DO NOT swallow
}
```

Rules that matter, each with its reason:

- **Forward to `previous`, do not swallow.** A handler that absorbs the throwable converts a crash
  into a silent process death with no system dialog — strictly worse than the bug. Record, then
  delegate.
- **The recorder must never throw.** Wrap the file write in `runCatching`; if it fails you lose the
  report, not the crash handling. This is the one place `runCatching` is correct — there is no
  coroutine cancellation to swallow here.
- **Write to `filesDir`, and capture build + device.** Version name/code, `Build.VERSION`, model,
  thread name, throwable class, message, and the full `printStackTrace` text. Cap the length
  (e.g. 12k chars) so it can still be copied off a phone screen.
- **Surface it in the UI, or it is not a deliverable.** A report written to disk that the user
  cannot reach is the same as no report. Add a settings section that reads the file at ViewModel
  construction and a "copy to clipboard" action; show it only when a report exists (an always-on
  empty section is a dead menu item).
- **Extract the format decisions into a pure function and unit-test them** (truncation, headline
  extraction) — the file I/O needs a `Context`, but those decisions do not.

**Then say what you did and did not establish.** A crash logger does not fix the crash. Report it
as "failures on this path now produce a message instead of a dead process, and the next occurrence
will name its class and line" — never as "the crash is fixed" when you could not reproduce it.

## Step 4.5 — The defensive layer to ship alongside the recorder

The recorder tells you what happened *next* time. This is what stops the current failure from being
a dead process, and it is shippable without knowing the root cause. Three changes, together:

**1. Widen the catch on the paths that can plausibly throw an `Error`, and rethrow cancellation.**
Only on the suspect paths — a repo-wide sweep is a different, larger change:

```kotlin
} catch (e: CancellationException) {
    throw e                      // MUST come first: it is an Exception subclass
} catch (t: Throwable) {         // not Exception — see Step 2
    _error.value = t.message?.takeIf { it.isNotBlank() }
        ?: "Fallback text (${t.javaClass.simpleName})"
}
```

The `javaClass.simpleName` in the fallback is what makes an unknown failure diagnosable from a
screenshot: `NoClassDefFoundError` and `OutOfMemoryError` have no message, so a bare fallback string
erases the only distinguishing information you had.

**This is not a cosmetic detail — when the user cannot send a logcat, the class name in the
error message IS the investigation.** A defensive fix that surfaces `simpleName` turns the
next user report from "app crashed" into "the message said NoClassDefFoundError" — and that
single word narrows the candidate list in a way no amount of static analysis could.

**2. Move initialization inside the `try`.** Any `ensureInitialized()` / `getService()` / registry
lookup sitting *above* the `try` block is an unguarded crash path — and it is the one most likely to
throw a class-loading `Error`, because that is where the class is first touched.

**3. Install a `CoroutineExceptionHandler` on the long-lived scope.**

```kotlin
private val crashGuard = CoroutineExceptionHandler { _, throwable ->
    Log.e(TAG, "Unhandled coroutine failure", throwable)
    _state.value = _state.value.copy(errorMessage = "Internal error: ${throwable.javaClass.simpleName}")
}
private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate + crashGuard)
```

`SupervisorJob` only stops sibling cancellation — it installs **no** handler, so an uncaught
throwable in `scope.launch { }` still kills the process. The handler is what converts "app vanished"
into a visible message.

**Then verify the message is actually rendered.** Grepping the write is not enough — confirm a
composable reads the field and that it renders on the screen the user is on when it fires:

```bash
grep -rn 'errorMessage' app/src/main/kotlin/     # find both the writes and the reads
```

If the only read is on a full-screen destination (a Now Playing screen), the failure that happens at
app start on the Home tab is still invisible. Put the surface where the failure occurs — a banner in
the always-visible `bottomBar` slot, which also auto-hides on full-screen routes so it never doubles
up — and give it a dismiss action so a transient failure does not stick all session.

**Wrap a whole coroutine body, not just the call.** `try { ... } catch` around only the first
statement leaves the rest of the block unguarded; wrap the body and use `try/finally` for flags that
must be reset, so a throw cannot leave a guard flag stuck on for the rest of the session.

## Step 5 — Report honestly

State which causes you disproved and how, which remain, and exactly what you need (the logcat line
range, the repro steps). An investigation that ends in "here is the one command that will name it"
is a valid, complete result. Presenting an untested guess as the fix is not.
