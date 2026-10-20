# User-Settable API Key via OS Keychain

Replacing "set an environment variable" with an in-app key entry backed by the OS
credential store, so a double-click installer is actually usable by a non-developer.
Companion to the parent skill; the installer reference flags this as the required
follow-up, this one implements it.

## Why this is not optional for a shipped desktop app

An env-var-only credential makes the installer a lie: the app opens, reports the key
is missing, and offers no way to supply one. Non-developers cannot fix that. The
in-app entry is what turns "installed" into "usable".

## Crate: `keyring` v4 with the `v1` feature

One dependency covers all three platforms — Keychain (macOS), Credential Manager
(Windows), Secret Service (Linux) — with no per-platform code:

```toml
keyring = { version = "4", features = ["v1"] }
```

The **v4 API differs from v3**. The simple all-in-one surface lives under the `v1`
module and is reached as `keyring::v1::{Entry, Error}`; a bare `keyring::Entry` is not
the type you want. Verify the surface against docs.rs for the exact version before
writing code — this crate reshuffles its module layout between majors:

```rust
use keyring::v1::{Entry, Error as KeyringError};

let e = Entry::new("id.meowlabs.ryn", "meowlabs-api-key")?;  // (service, account)
e.set_password(key)?;
let key = e.get_password()?;
let _ = e.delete_credential()?;
```

`Entry::new` failing at construction is how you detect "no usable store on this
platform" (see the headless note below) — it is not only an error path.

## Read priority: credential store first, env var as fallback

Keep the env var working. Dev machines, CI, and scripts rely on it; the UI is for
everyone else. Store wins so a key entered in the UI is never silently shadowed by a
stale exported variable:

1. OS credential store → if present and non-empty, use it.
2. `MEOWLABS_API_KEY` → fallback.
3. Neither → `None`, and the UI must drive the user to the entry dialog.

Report which one is active so the user is never confused about why a change did not
take effect. Expose it as a `key_source` command returning `"keychain" | "env" | null`.

## Command surface

Five commands, all thin wrappers so the logic stays testable:

| Command | Purpose |
|---|---|
| `keychain_available` | Is there a usable store on this platform? Drives the "set the env var instead" hint. |
| `key_source` | Which source is active — shown in the status line. |
| `get_api_key` | The read used by the LLM client. |
| `set_api_key` | Write. Reject empty/whitespace before touching the store. |
| `clear_api_key` | Delete. |

Treat `NoEntry` on delete as success: deleting something that was never there reaches
the same end state, and surfacing it as an error makes the UI show a scary failure for
a no-op.

## Make the priority logic testable without the real store

Do not unit-test against the live credential store — tests would clobber the
developer's actual key and behave differently per machine. Extract the decision logic
as pure functions over `Option<String>` and test those:

```rust
fn pick(store: Option<String>, env: Option<String>) -> Option<String> {
    normalize(store).or(env)          // store wins; blank store falls through to env
}
```

That single seam covers every branch worth asserting: store wins, env used when store
is empty, blank/whitespace store is not a key, values are trimmed, and the reported
source matches. The I/O wrappers stay untested but trivial.

## Frontend: cache invalidation is the trap

**The LLM client caches the key in a module-level variable, so saving a new key does
nothing until that cache is cleared.** The user pastes a valid key, the app still
says "not set" — because the first `get_api_key` returned `null` and was remembered.

Export a `resetApiKeyCache()` from the client and call it from **both** save and
delete. This is the single highest-value line in the feature.

Dialog behaviour that matters:

- **Open it automatically on startup when no key exists.** A user with no key cannot
do anything else, so making them find a button is a dead end.
- **Never render the stored key back into the input.** Show it as "already saved — type
to replace". Displaying it needs no feature the user asked for and leaks it to
shoulder-surfing and screenshots.
- Use a real `<dialog>` + `showModal()`; the browser handles focus trapping and Esc.
- A show/hide toggle that just flips `input.type` between `password` and `text` is
  enough — do not build a custom reveal.

## Linux: a headless box has no Secret Service

On a VPS without a running Secret Service there is no store, so `Entry::new` fails.
That is expected, not a bug. Detect it and tell the user to use the env var instead of
presenting a dialog that can only fail. Do not report the feature as broken — it is
unavailable by design on that host, and the real target is the user's desktop.

**Do not infer this from the presence of a D-Bus session bus.** A session bus can be
running while nothing owns the Secret Service name, and then `Entry::new` still fails
with `No default store has been set, so cannot search or create entries`. The bus
existing is not the same as the store existing — check the name owner, not the bus:

```bash
echo "DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-<unset>}"
dbus-send --session --dest=org.freedesktop.DBus --type=method_call --print-reply \
  /org/freedesktop/DBus org.freedesktop.DBus.NameHasOwner string:org.freedesktop.secrets
# `boolean false` (or a missing bus) = no store; expect set_api_key to fail
pgrep -a gnome-keyring    # a running keyring daemon is the positive signal
```

**Probe the real behaviour before claiming either outcome.** A short throwaway test
that prints `keychain_available`, `Entry::new(...).is_ok()`, and the result of
`set_api_key` answers "does this host have a store" in one run, and confirms the
failure is honest (nothing written, a clear error returned) rather than a silent
no-op. On this kind of host `set_api_key` must return an `Err` naming the missing
store — if it returns `Ok` while nothing was stored, that is a real bug worth
chasing. Delete the probe test afterwards.
