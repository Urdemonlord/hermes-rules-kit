# Bank-notification payment detection (Android) in a KMP app

Use when a POS/wallet app must auto-detect an incoming QRIS/bank transfer by reading the bank app's
notification. This is the Android-only differentiating feature; iOS has **no** public API for it, so
the iOS side is a stub with `isSupported = false` (see the capability table in
`references/kotlin-multiplatform-scaffold.md`). Everything here is writable without a build; the
parser is the part you can actually prove headless.

## The three-part pattern (the service cannot be constructed from app code)

Android creates and binds a `NotificationListenerService` itself; the app cannot `new` it. So the
shape is always three pieces, never one:

1. **The service** (`androidMain`) — system calls `onNotificationPosted`; it parses and publishes.
2. **A shared bus** — a singleton `MutableSharedFlow<T>(extraBufferCapacity = 16)` with a
   `internal fun publish()` that uses `tryEmit` (never blocks the system notification thread).
3. **A UI-facing listener** (`androidMain`, exposed to `commonMain` via `expect`/`actual`
   `createPaymentListener()`) that subscribes to the bus and hands events to the screen.

## Manifest — the declaration that decides whether the feature exists at all

```xml
<service
    android:name=".core.notification.BankNotificationService"
    android:exported="true"
    android:label="… — Deteksi pembayaran"
    android:permission="android.permission.BIND_NOTIFICATION_LISTENER_SERVICE">
    <intent-filter>
        <action android:name="android.service.notification.NotificationListenerService" />
    </intent-filter>
</service>
```

- `BIND_NOTIFICATION_LISTENER_SERVICE` is **only** an `android:permission` attribute on the
  `<service>`. Declaring it as `<uses-permission>` is wrong — that permission is held by the system
  process that binds you, not by you.
- `android:exported="true"` is required: the caller is the system process.
- **Without this `<service>` block the feature fails silently** — no error, no log the user sees; the
  notifications simply never arrive. Treat it as part of the feature, not boilerplate.

## Permission: there is no runtime dialog

Notification access is granted only in Settings, so `requestPermission()` opens
`Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS` (with `FLAG_ACTIVITY_NEW_TASK`). Read the live
state from `Settings.Secure.getString(cr, "enabled_notification_listeners")` and compare
`ComponentName.unflattenFromString(...)` against your own `ComponentName` — do not cache a boolean,
because the user can revoke it any time.

**Show a banner when access is missing.** Without it the feature fails silently and the cashier
assumes auto-detection is on while no order ever settles. Surface it on the always-visible screen
(the cashier screen), driven by `listener.isSupported` + a `LaunchedEffect { hasPermission() }`
check — not on the payment screen, which the user has not reached yet.

## Parser design — pure, in `commonMain`, and fail-safe on ordering

Keep the parser a plain `fun parse(pkg: String, title: String, text: String): BankNotification?` with
no Android types, so it lives in `commonMain` and is unit-testable. Two rules that decide whether it
works in the field:

- **Order the keyword checks so CREDIT wins, and never list an ambiguous word as outflow-only.** A
  "money out" list containing `pembelian`, `tagihan`, or `debit` rejects the very notifications you
  want: an incoming QRIS credit reads *"Pembelian QRIS diterima Rp50.000"*. Check the incoming
  markers first and return on a match; only then reject on outflow markers, and keep those markers
  unambiguous (`transfer keluar`, `berhasil dibayar`, …). A filter that rejects legitimate payments is
  worse than no filter — it is the differentiating feature failing on its happy path.
- **Extract numbers only — never forward `rawText`.** Send
  `{sale_id, amount, package_name, bank_ref, device_timestamp}`. The raw notification can carry the
  sender's name, account number, balance, and private messages; the server needs the amount, the
  bank reference, and the time, and nothing else. (This is the concrete lesson from auditing an
  existing POS whose client shipped `{merchantId, rawText}` upstream.)

Amount parsing: prefer an explicit `Rp`-prefixed match, strip `.`/`,` thousands separators, and
return `null` rather than guessing when no amount is found.

## Package allowlist — verify each name, and expect it to rot

Keep the bank/e-wallet package names in one `commonMain` object. Verify each from the Play Store
listing (`site:play.google.com <app>`); a guessed name matches nothing and fails silently. Names
change on rebrand (e.g. BNI's app package moved when it became *wondr*), so a stale entry silently
drops one bank. Mitigations: keep the list server-updatable, or at minimum log the sender package of
any notification that passed the system filter but matched no allowlist entry, so a rebrand is
visible instead of invisible. **Count the list from the file when you quote its size** — an
"N packages" figure written from memory drifts.

## Wiring into Compose — one long-lived scope, not one per event

```kotlin
val scope = rememberCoroutineScope()          // NOT MainScope() inside the callback
DisposableEffect(controller) {
    val handle = listener.observe { note -> scope.launch { controller.onBankNotification(note) } }
    onDispose { handle.close() }
}
```

`MainScope()` created inside the notification callback is a **leak**: nothing cancels it, so every
notification parks a scope for the process lifetime. Use the composable's `rememberCoroutineScope`
(or a single application-lifetime scope) and close the subscription in `onDispose`.

## Server is the judge — the app never marks an order paid

Detection produces a *signal*, not a settlement. The app posts the signal; the server matches
`amount` + `device_timestamp` + the order's ownership and decides. This is what keeps a spoofed
notification (any app can post one) from settling an order.

## Headless verification (the part you CAN prove)

- Port the parser to Python and run the same assertions, including the ambiguous cases
  ("Pembelian QRIS diterima", "Pembayaran berhasil", a marketing push with no amount). Report it as
  "logic proven via Python port, Kotlin not compiled".
- Count the allowlist and any other number you will quote from the artifact itself.

## Pitfalls

- **A file rename/removal can leave a type used across the tree but never defined.** Deleting the old
  file and writing the new one under a different name drops the data class that several files still
  import — the tree no longer compiles, and nothing points at the cause. After any rename/removal,
  `grep -rn '<TypeName>' --include='*.kt' .` and confirm a definition still exists, not just uses.
- **`private lateinit var` in one package cannot serve another package.** A platform holder exposing
  `appContext` to sibling packages must be `internal` (or public), or the call site fails to compile.
  The `lateinit` holder must be initialized from a custom `Application` registered in the manifest
  (`android:name=".YourApplication"`); if it looks uncalled, trace the chain — class →
  `onCreate()` → `android:name` in the manifest — before reporting a startup crash. A `lateinit`
  holder IS a crash (`UninitializedPropertyAccessException`) if the chain is genuinely broken, so the
  check is worth doing, but only after confirming the manifest does not already wire it.
