# SAF custom-folder scanning (Storage Access Framework)

Why: MediaStore only exposes locations the system indexed. Music in an excluded folder, or on some
SD cards, never appears there even though the files exist. Letting the user pick a folder through
`OpenDocumentTree` reaches any of them, and the grant persists across reboots — so it is a *better*
permission than `READ_MEDIA_AUDIO`, not a workaround.

## Pick the folder and keep the grant

**Do NOT use `ActivityResultContracts.OpenDocumentTree()` as-is.** It sends
`ACTION_OPEN_DOCUMENT_TREE` *without* `FLAG_GRANT_PERSISTABLE_URI_PERMISSION`, so
`takePersistableUriPermission` throws `SecurityException` on some devices and the grant silently
fails to survive app close. Subclass the contract to add the flag:

```kotlin
class OpenDocumentTreeContract : ActivityResultContract<Unit?, Uri?>() {
    override fun createIntent(context: Context, input: Unit?) =
        Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).apply {
            addFlags(
                Intent.FLAG_GRANT_READ_URI_PERMISSION or
                    Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
            )
        }
    override fun parseResult(resultCode: Int, intent: Intent?) =
        if (resultCode == Activity.RESULT_OK) intent?.data else null
}

val pick = rememberLauncherForActivityResult(OpenDocumentTreeContract()) { uri ->
    if (uri != null) viewModel.addFolder(uri)
}
// …
pick.launch(null)
```

Treat `addFolder` as fallible: after `takePersistableUriPermission`, re-read
`contentResolver.persistedUriPermissions` and confirm the URI is present with read permission. A
`SecurityException` swallowed by `runCatching{}` looks identical to success until the user reopens
the app and every track from that folder is dead — surface the failure in the UI.

**`takePersistableUriPermission` is mandatory, immediately.** Without it the grant lives only as
long as the process: the folder works during the session and every track from it fails after the app
is closed, with no explanation. Store the URI too (DataStore is right for a short key-value list like
this — no relational query, and a partial write cannot corrupt it).

```kotlin
context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
```

On removal, `releasePersistableUriPermission` — Android caps how many persisted grants an app may
hold, so dead ones consume the budget.

## Walk it, and prune what the walk no longer sees

`DocumentFile.fromTreeUri` + a bounded recursive walk. Two rules that keep a scan from dying on one
bad file:

- **Never let one entry abort the scan.** `listFiles()` and `name` can throw on an unhealthy
  provider; wrap each in `runCatching` and skip. Cap recursion depth (~12) so a symlink loop or an
  absurd tree cannot spin forever.
- **Reconcile after each scan — but ONLY when the scan actually completed.** Compare the ids just
  found against the ids stored for that folder and delete the ones no longer present. Without it,
  moving or deleting a file leaves a permanent "ghost" row that shows in the library and fails to
  play. Compute this from the scan you already did — do not re-walk the folder to compare.
  **The completeness guard is mandatory.** A scan that fails part-way (SD card not mounted, grant
  revoked, provider error) returns an empty or partial list, and a naive reconcile then deletes
  EVERY song in that folder — plus its playlist membership via FK CASCADE and its play counts.
  Return a separate `isComplete: Boolean` alongside the results and delete only when it is true.
  "Folder is genuinely empty" and "folder could not be read" must never collapse to the same value.

## Read metadata with `MediaMetadataRetriever`

Files outside MediaStore have no database row, so there is nothing to query. The retriever is also
the only source of **duration** — without it the seek bar cannot work.

```kotlin
val r = MediaMetadataRetriever()
try {
    r.setDataSource(context, uri)
    val durationMs = r.extractMetadata(METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
    if (durationMs <= 0L) return null          // not playable audio
    val title = r.extractMetadata(METADATA_KEY_TITLE)?.takeIf { it.isNotBlank() }
        ?: fileName.substringBeforeLast('.')   // fall back to the file name
    // artist / album the same way; albumart via r.embeddedPicture
} catch (_: Exception) {
    null                                        // corrupt or unsupported — skip, keep scanning
} finally {
    runCatching { r.release() }
}
```

Embedded artwork (`embeddedPicture`, a `ByteArray`) must be written to a file in `cacheDir` and
stored as a URI string — the image loader takes a URI, not bytes. Writing it into the app's own
cache never touches the user's storage. No artwork → `null` → the vector placeholder, which is
correct behaviour, not an error.

## De-duplicate against MediaStore, or every song appears twice

This is the trap that bites first. MediaStore rows get an id like `ms:123`; SAF rows get `saf:<hash>`.
Add a folder that MediaStore already indexes (the common case — it is the user's `Music` folder) and
the same file is stored twice under two ids, both playable, both listed.

Compare a **fingerprint of file name + byte size**, gathered in **one** MediaStore query per scan
(not per file — that is pathologically slow on a large folder):

```kotlin
// once per scan
val indexed = buildSet {
    query(EXTERNAL_CONTENT_URI, arrayOf(DISPLAY_NAME, SIZE), "IS_MUSIC != 0") { c ->
        add("${c.getString(0).lowercase()}|${c.getLong(1)}")
    }
}
// per candidate file
if ("${name.lowercase()}|${child.length()}" in indexed) return   // already in the library
```

Name comes from the file, not the title tag — the user may have edited the tag. Be honest about the
limit: two *different* files with identical name and size collide, and one is skipped. In practice
that means copy-pasted duplicates, whose content is the same anyway.

## Ids must be stable across processes

Do **not** build the id from `String.hashCode()` — it is not guaranteed identical across JVM
versions or runs, and a changing id detaches a song from its play history and its playlist entries.
Use a content hash:

```kotlin
MessageDigest.getInstance("SHA-1").digest(uri.toString().toByteArray())
    .joinToString("") { "%02x".format(it) }.take(16)
```

Prefix the column so the two sources never collide: `"saf:" + hash`.

## Removing a folder: order matters, and the copy matters more

Delete the folder's songs **before** releasing the grant. Reversed, a crash in between leaves the
folder gone from the list while its rows remain — and nothing can find them again. The reverse order
is safe because row deletion only touches the database.

In the confirm dialog, state explicitly that the original files are **not** deleted. "Remove folder"
reads to a user as "delete my music"; say that it only leaves the library. Use a neutral icon
(close/x) rather than a trash can, for the same reason.

## Stale grants

A folder can vanish (deleted via Files, or the system revokes it). Drop entries whose URI no longer
appears in `contentResolver.persistedUriPermissions` with read permission — otherwise the same
folder fails on every scan with no visible cause.

**Guard this prune too.** If reading `persistedUriPermissions` itself fails or returns nothing
usable, do NOT treat that as "no folders are valid". Prune only when the permission list was
actually readable; otherwise a transient read failure silently drops every folder the user added.

## Schema addition this implies

A nullable `folderUri` column on the songs table, indexed, plus a migration. `NULL` means "not from a
custom folder" and needs no backfill. Validate that migration headless with
`scripts/validate-room-migration.py` — see `references/media3-playback-service.md`.

Do not put the folder list in Room. It is a handful of opaque strings with no relational queries
against them; a preferences store is the correct home, and Room would only add a migration to
maintain.
