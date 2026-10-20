# Compose loading / empty / error state: never let a default value stand in for "not yet read"

Why list screens lie on the first frame, how to model the three states, and how to build the
skeleton that covers them. Applies to every screen backed by Room/network — not just playback.

## The bug class

A `Flow` from Room (or a network call) emits **nothing** until its first query completes. So
`stateIn(scope, WhileSubscribed(5_000), <default>)` hands the UI the default for the first frame(s)
— typically 50–200 ms on a warm device, longer on a cold start. During that window the screen
cannot tell **"not finished reading"** from **"the value really is that"**, and it renders a
conclusion that is not true. Then the content snaps in.

The user-visible symptom is always a **false statement**, not a spinner or a blank:

| Initial value | Field | False conclusion rendered |
|---|---|---|
| `emptyList()` | song list | "No music yet — scan your storage" |
| `emptyList()` | playlist list in a picker dialog | "You have no playlists" |
| `0` | song count | "0 songs indexed" |
| `0` | total play count | "No history yet" (instead of "nothing in this range") |
| `false` | history-paused flag | a Switch rendered OFF = "history is recording" |
| `null` | listen threshold | — `null` is a *valid* value here, so wrap it, do not replace it |

The worst variant is when the default **selects between two messages**. If `totalPlayCount == 0`
chooses "you have never played anything" over "nothing in this date range", then an unread `0`
picks the wrong one and the screen confidently says the wrong thing.

### What is NOT a violation

`_message` (`null` = genuinely no message), `_isScanning` (`false` = genuinely not started), and any
value held only in memory that was never read from disk. The test is not the *type* of the
default — it is **whether that value is used to conclude something about data that has not been
read yet.** If it feeds a `when`, an `enabled =`, a `checked =`, or a message, it is a violation.

## Model three states, not two

```kotlin
sealed interface Loadable<out T> {
    data object Loading : Loadable<Nothing>
    data class Ready<T>(val value: T) : Loadable<T>
    data class Failed(val message: String) : Loadable<Nothing>
}

val <T> Loadable<T>.valueOrNull: T? get() = (this as? Loadable.Ready)?.value
```

`Failed` **must** stay separate from `Ready` holding an empty value. Both produce an empty list, but
one means "there is nothing" and the other means "there should be something and we could not get
it". Collapsing them makes a broken query look like missing data — and a fault that looks like
missing data is never reported.

`Loadable` wraps **any** value, not only lists: `Loadable<Int>`, `Loadable<Boolean>`,
`Loadable<Long?>`. What is wrapped is "do we know the value yet", not the value's type.

```kotlin
when (val state = songs) {
    Loadable.Loading -> SkeletonSongList(rows = 8)
    is Loadable.Failed -> LoadErrorState(state.message, onRetry = vm::retry)
    is Loadable.Ready -> { val list = state.value /* … */ }
}
```

If the same three-way shape already exists somewhere in the app (a screen-state enum that
distinguishes empty from failed), reuse that pattern rather than inventing a second one — and check
whether the code that *inspired* the pattern is itself still violating it.

## The wrapper: operator order is load-bearing

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
fun <T> Flow<T>.asLoadable(
    scope: CoroutineScope,
    retryTrigger: Flow<*>? = null,
    stopTimeoutMs: Long = 5_000L,
): StateFlow<Loadable<T>> {
    val pipeline: () -> Flow<Loadable<T>> = {
        map<T, Loadable<T>> { Loadable.Ready(it) }
            .onStart { emit(Loadable.Loading) }
            .catch { t ->
                if (t is CancellationException) throw t
                emit(Loadable.Failed(t.message ?: t.javaClass.simpleName))
            }
    }
    val source = if (retryTrigger == null) pipeline()
                 else retryTrigger.flatMapLatest { pipeline() }
    return source.stateIn(scope, SharingStarted.WhileSubscribed(stopTimeoutMs), Loadable.Loading)
}
```

Four details, each of which fails quietly if you get it wrong:

- **`.map` → `.onStart` → `.catch`, in that order.** Put `.onStart` before `.map` and its `Loading`
  emission flows through `map` and becomes `Ready(Loading)`.
- **Write the type parameter on `.map` explicitly** (`map<T, Loadable<T>>`). On `Flow.map` the first
type parameter is the **input** type; letting it infer yields `Flow<Loadable.Ready<T>>`, which is not
assignable to `StateFlow<Loadable<T>>` and produces a confusing "cannot infer" cascade.
- **`catch` takes `Throwable`, and rethrows `CancellationException` first.** A Room query can fail
  with an `Error` (e.g. `OutOfMemoryError` on a large database), and `Error` is not an `Exception` —
  it escapes `catch (e: Exception)`, kills the process, and leaves no message. Note `runCatching {}`
  has the same `CancellationException`-swallowing bug with no `catch` keyword to grep for.
- **The pipeline is a lambda, re-invoked per retry.** The Room flow is cold, so re-subscribing
  genuinely re-runs the query. Without that, a failed flow never emits again and the retry button is
  decorative.

`initialValue = Loadable.Loading` only applies until the first emission; afterwards `StateFlow`
holds the last value, so navigating away and back does not re-show the skeleton.

## Retry needs re-subscription, and the trigger must be incremented

```kotlin
private val retryTrigger = MutableStateFlow(0)

fun retry() { retryTrigger.value += 1 }
```

- **Increment, never set a boolean.** With `_retry = true`, a second tap changes nothing and fires
  no re-subscription — the button works exactly once.
- **Declare the trigger BEFORE every flow that consumes it.** Kotlin initializes properties in
declaration order, so a flow written above its trigger is a forward reference. One shared trigger
serving several `asLoadable` calls is fine; just keep it first.

## Shared composables that make decisions must take `Loadable`

A dialog that renders "You have no playlists" when the list is empty is **making a claim**, not
merely drawing a value. Such a component takes `Loadable<List<T>>` and branches internally:

```kotlin
@Composable
fun PlaylistPickerDialog(playlists: Loadable<List<PlaylistEntity>>, …) {
    text = {
        when (playlists) {
            Loadable.Loading -> Text(stringResource(R.string.generic_loading))
            is Loadable.Failed -> Text(stringResource(R.string.generic_load_error))
            is Loadable.Ready -> if (playlists.value.isEmpty()) { /* the real empty state */ }
                                else { /* rows */ }
        }
    }
}
```

The rule: **a component takes `Loadable` when it draws a conclusion; it takes the plain type when it
only draws the value.** `SongRow(song: SongEntity)` stays plain. Widening a shared component's
signature means every call site must be updated in the same pass — grep them all first, and prefer
passing the `Loadable` straight through over unwrapping with `.valueOrNull.orEmpty()` at the call
site, which reintroduces the very bug you are fixing.

## Skeletons

- **One animation clock per screen, hoisted.** A `rememberInfiniteTransition` inside the block
  composable means every block has its own clock, started when that block first composed. A list of
  8 rows x 3 blocks is 24 unsynchronised clocks, and the result reads as *random flickering* rather
  than one wave sweeping the screen. Hoist a single `rememberSkeletonProgress()` at the list level
  and pass the `Float` down.
- **Drive the gradient from the block's real width** (`drawBehind { }`, which knows `size`), not a
  fixed pixel offset. A hardcoded `600f` makes a 40 dp block shimmer far too fast and a
  full-width block far too slow.
- **A translating gradient, not an alpha pulse.** On a dark theme an alpha pulse reads as a
  flicker/broken render.
- **Shape the skeleton like the real content** and reserve the same space, so nothing jumps when
  the data lands. Provide a screen-level variant that covers the real layout (header + carousel +
  list), not just the rows.
- **One TalkBack label for the whole skeleton**, with the individual blocks decorative:
  `SkeletonSongList(contentDescription = stringResource(R.string.generic_loading))`. Defaulting it
  to `null` on a screen whose skeleton *replaces* a specific announced state silently regresses
  accessibility — when you add a default, check what the previous call site announced.
- **Add `contentType` to `items()`** so Compose can reuse slot instances across item types while
  scrolling. Cheap, and directly felt on long lists.

## Sweep the whole codebase for the rule — do not stop at the known instances

This is the part that matters most. The bug was found in three screens, fixed, and committed — then
four more instances turned up, including one in the screen that had been the *source* of the good
pattern. Each sweep found something the previous one missed.

The procedure that works:

1. Fix the known instances.
2. **Write the rule down** (in the project's canonical design/spec doc) as a rule, not as a
   changelog entry.
3. **Test the rule against the entire repo**, mechanically:

```bash
grep -rn 'stateIn(' app/src/main/kotlin/ -A3 | grep -E 'emptyList|emptySet|, 0\)|, false\)|, null\)|, 0L\)'
```

4. Classify each hit: real violation, or an allowed default (see the test above). Then check the
   consumers too — a `stateIn` whose default is fine is not the only place a false conclusion can
   be computed.
5. Repeat until the grep is clean, and re-run the sweep after any widening of the rule.

A rule stated too narrowly under-reports: an initial rule of "never use `emptyList()` for a list"
misses `0`, `false`, and `null`. State the rule by *mechanism* ("no default may stand in for not-yet-
read") so the sweep matches every shape of it.

Also update the canonical doc when the sweep teaches you something the rule did not say — the doc is
what the next session will trust, and a stale rule is worse than no rule.
