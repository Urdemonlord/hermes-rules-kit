# Media3: attaching system audio effects (EQ, bass boost, normalization)

Adding an Android `Equalizer`, `BassBoost`, or `LoudnessEnhancer` to a Media3 player. The
effects are native objects, not Media3 ones, so their lifecycle is bound to the player by the
`audioSessionId` — not by DI, not by the ViewModel.

## The one thing that is easy to get wrong

`audioSessionId` is **not stable**. ExoPlayer allocates a new one whenever the player is rebuilt,
which happens when the `MediaLibraryService` process is recreated. Effects are bound to that id, so
effects created only once (in `onCreate`) silently stop applying after the first service
recreation — equalizer appears to "work once then do nothing".

Attach them from the player's session-id callback, not from `onCreate` alone:

```kotlin
exo.addListener(object : Player.Listener {
    override fun onAudioSessionIdChanged(audioSessionId: Int) {
        audioEffects.attach(audioSessionId)
    }
})
// and in onDestroy, before releasing the player:
audioEffects.detach()
```

`attach()` should be idempotent (return early when the id is unchanged) and should release the
previous effects before creating new ones for a new session.

## Why the controller is a @Singleton, not per-Composable

- The effects live in the **service** process (where ExoPlayer lives), not in the UI. A controller
  scoped to a ViewModel or created per-Composable would die when the UI goes away, killing the
  audio effects mid-playback.
- UI writes its settings to DataStore; the service-side controller reads from that same flow. No
  binder RPC is needed to apply a slider change — the flow is the channel.

## Reading the device's band config

The equalizer's band count and center frequencies are **device-specific**, not fixed:

```kotlin
val bands = (0 until equalizer.numberOfBands.toInt()).map { eq.getCenterFreq(it.toShort()).toInt() }
val (minGain, maxGain) = equalizer.bandLevelRange.let { it[0].toInt() to it[1].toInt() }
```

Do not hardcode 5 bands or a `-1500..1500` range for the UI; read both from the live
`Equalizer` object at runtime, with a fallback when the device has no equalizer at all
(`isAvailable = false` → show "not supported", not a non-functional slider).

## Gain clamping: the device rejects out-of-range values

`setBandLevel` throws `IllegalArgumentException` if the value is outside `bandLevelRange`. Always
clamp to the device's own reported range before calling:

```kotlin
val clamped = gainMillibels.toShort().coerceIn(minLevel, maxLevel)
eq.setBandLevel(bandIndex, clamped)
```

## Persist band gains as a list, not as a fixed-length array

Device band counts differ (some have 3, some 5, some 10). Persist the gains as a
comma-separated string (`"-300,600,0,0,0"`), not one preference key per band. On read, ignore
extra values (band doesn't exist on this device) and treat missing values as 0 (neutral). This
keeps a preference set on one device valid on a different one.

## `attach()` must not call a `suspend` function

If you cache "the last settings applied" in a field updated by the DataStore flow collector, then
`attach()` can apply it synchronously without a `suspend` call. Calling a suspend function from
the non-suspend `attach()` won't compile; the field-cache pattern avoids the problem cleanly.