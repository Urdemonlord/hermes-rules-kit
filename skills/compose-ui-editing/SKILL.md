---
name: compose-ui-editing
description: "Edit Compose UI: swap drawables, extract shared composables."
version: 1.0.0
author: Hermes Agent
license: CC0-1.0
metadata:
  hermes:
    tags: [android, jetpack-compose, ui, drawable, resources, refactoring]
---

# Compose UI Editing

Use when changing how an existing Compose screen looks or is built: replacing an
icon/placeholder/image, extracting a component duplicated across screens, editing a
drawable resource, or regenerating PNG assets at density buckets.

This is the class of work where the diff is tiny and the failure modes are not,
because the compiler is the only thing that knows whether a new composable helper
has a legal signature — and where the build host forbids Gradle, the compiler is
CI, one push away.

## 1. First decide: does this swap need a new composable, or only a new asset?

Answer before editing. The question is whether the change alters how the drawable is
*painted*, or only which drawable is painted.

| Before | After | Swap required |
|---|---|---|
| `Icon(painter = R.drawable.x, tint = …)` | `Icon(painter = R.drawable.y, tint = …)` | asset only |
| `Image(painter = R.drawable.x)` | `Image(painter = R.drawable.y)` | asset only |
| `Icon(painter = R.drawable.x, tint = …)` | full-colour raster (PNG / bitmap drawable) | **composable too** |

**`Icon` forces a `ColorFilter` across the painter — that is how a vector drawable
becomes one colour. A raster drawable passes through the same filter and loses every
colour it had, surviving as a flat silhouette.** `Image` has no `tint` parameter at
all, so the mistake is not expressible there. When a drawable stops being a tinted
vector, `Icon` must become `Image` in the same edit; leaving `Icon` ships a
plausible-looking screen with the artwork's colour silently destroyed.

## 2. A composable using a scope modifier must BE that scope's extension

`Modifier.align`, `Modifier.weight`, a scope-default `fillMaxWidth` inside a column,
`Modifier.animateItem()` in a lazy list — these resolve only inside the receiver scope
that owns them. A plain `@Composable fun` calling one fails with
`Unresolved reference 'align'`.

| Modifier | Required receiver |
|---|---|
| `.align(...)` | `BoxScope` |
| `.weight(...)` | `RowScope`, or `ColumnScope` inside a `Column` |
| `.fillMaxWidth(...)` as a scope default | `RowScope` / `ColumnScope` |
| `.animateItem()` | `LazyItemScope` |

```kotlin
@Composable
fun BoxScope.ArtworkPlaceholderImage(modifier: Modifier = Modifier) {
    Image(painter = …, modifier = modifier.align(Alignment.Center))
}
```

Declaring the extension is free when every caller already sits inside the right
container — the scope is in scope there anyway. Check each caller before widening a
helper's signature; widening a helper that has non-scope callers breaks all of them.

**This is the most common first-CI failure for a new composable on a host where
Gradle is forbidden** (see §8). The signature looks correct in a diff; only the
compiler knows `.align` resolves only inside `BoxScope`. When CI reports
`Unresolved reference 'align'`, fix the receiver type — do not remove `.align`
from the call site.

## 3. Imports follow package, not file location

A new composable in the SAME package needs no import. One in a different package
needs it, and the missing import surfaces as a compile error in a *different file*
than the one being reasoned about — the CALLER's file, not the definition you just
wrote. Verify, do not assume:

```bash
grep -H '^package' <helper>.kt <caller1>.kt <caller2>.kt …
```

Use `grep`, not `head` — `package` is not always line 1. File-level annotations and
`@file:OptIn` blocks sit above it.

## 4. Extract duplicated call sites before changing them

Three or more screens writing the same call shape is that many independent copies of
one decision. Changing the asset keeps them consistent by luck; changing *behaviour*
(size, framing, tint policy) needs one edit per copy, and the forgotten one is
indistinguishable from a bug.

Introduce one composable in the package the majority of callers already live in, then
replace every call site. Record in the new composable's KDoc *why* the duplication
existed — otherwise the next reader "simplifies" it back to inline calls at the first
call site they touch.

## 5. Regenerating raster assets: framing is a decision, not a default

Full-bleed illustration and tinted placeholder are different compositions. Crop is
decided per surface, because the mask is what forces it:

- **Launcher icon** — the OEM mask (circle, squircle, rounded square) cuts the outer
  band on every side. Keep the subject inside the adaptive safe zone (~66.7% of the
  canvas) or the mask eats it.
- **In-app tile** (list-row artwork, ~48dp) — no mask crops it, so the subject can be
  deliberately tighter and larger than the launcher framing.

Render the candidates side by side, look at them, then pick. Rendering without looking
is how a head gets clipped at the crown and ships.

Fill ratio is a second decision. An illustration with its own opaque background
painted at 100% of the tile covers the surrounding gradient, so every row becomes the
same flat dark square and the gradient the design system paid for is invisible. Leave
margin — roughly 55% is a sane default for a tile sitting on a gradient.

Export one file per density bucket from the single source image at a fixed aspect
ratio. Vector→raster migration means the XML drawable is deleted **in the same
commit**; leaving both lets a stale reference keep compiling.

Crop math, export script, and mask-compositing recipe:
`references/artwork-and-drawables.md`.

## 6. Verify the render, not just the asset

Ship a preview compositing the real masks (circle / squircle / rounded square) and the
real tile size against the current state, and actually look at it. Asset diffs are
invisible in review; a clipped head or a drained palette is obvious in one glance and
survives every automated gate.

## 7. The design spec is code — edit the false rule in place

A spec claiming "the placeholder is a thin-line geometric icon" is a false claim the
moment the asset changes, and false claims in a spec are worse than no spec: the next
session trusts them. Rewrite the rule; never append an "UPDATE:" note underneath it.

Two traps specific to a spec edit after an asset swap:

- **Absolute prohibitions need a named exception, not deletion.** "Never bundle
  artwork into the APK" exists for a reason. Replacing the placeholder with an
  illustration does not falsify that rule — it adds a case the rule never
  anticipated. Write the exception ("…except the placeholder, §N") so the reason
  survives. Deleting the line destroys the reason along with it.
- **Cross-references outlive the thing they point at.** A sibling section saying
  "this uses the same style as the placeholder" is now false too, and it sits in a
  section that was never opened. Grep the docs for the old name/shape before
  finishing.

## 8. Where Gradle is forbidden, CI is the compiler — and the first run fails

On a host where the build must not run, the first CI after adding a new composable
*is* the type-check. Assume it fails on something written minutes earlier: the
signature rules in §2 and §3 are invisible in a diff.

- Read the actual errors out of the job log; do not infer them from the diff.
- A failed run on an open PR is the expected first iteration, not a blocker. Fix and
  push in the same cycle.
- Do not call the change working, merged, or released until that run is green.
  "The diff looks right" is not compile evidence.

**The most common first-CI failure for a new composable is a scope-modifier error
from §2.** `Unresolved reference 'align'` means the helper was declared as a
plain `@Composable fun` but uses `Modifier.align` — the fix is to make it a
`BoxScope` (or the matching scope) extension. This error is invisible in a diff
because the signature *looks* correct to a reader; the compiler is the only
thing that knows `.align` resolves only inside `BoxScope`. When CI reports this,
fix the receiver type, not the call site — every caller already sits inside the
right container, or it would not have been written that way.

Host build constraints and the CI-as-compiler mechanics live in
`android-kotlin-cli-build`.

## 9. Attaching Media3 system audio effects (EQ, bass boost, normalization)

When wiring an `Equalizer` / `BassBoost` / `LoudnessEnhancer` to a Media3 player, two things
dominate the design:

- **`audioSessionId` is not stable** — effects must be re-attached via
  `Player.Listener.onAudioSessionIdChanged`, not once in `onCreate`.
- **Band count and gain range are device-specific** — read them from the live `Equalizer` object
  at runtime, not hardcoded. Clamp every gain to the device's own `bandLevelRange` before calling
  `setBandLevel`.

Full recipe (singleton lifecycle, DataStore as the settings channel, band-gain persistence across
devices with different band counts):
`references/media3-audio-effects.md`.

## 10. XML resource: `--` inside a comment ends the comment early

Prose comments in Indonesian (or any language) habitually use `--` as a dash.
Inside an XML comment that is a parse error: the parser treats `--` as the
comment terminator, so the rest of the sentence is parsed as markup and the
resource build fails with an offset into a line that reads as plain prose.

```xml
<!-- salah: penutup komentar terdeteksi di tengah kalimat -->
     Bitmap -- RemoteViews tidak bisa memuat artwork.

<!-- benar: ganti dengan tanda baca biasa -->
     Bitmap. RemoteViews tidak bisa memuat artwork.
```

The failure is invisible in review because every word is a valid identifier in
a language that is not the file's language. Validate every XML resource before
committing — this needs no Gradle and catches the whole class:

```bash
python3 -c "
import sys, xml.etree.ElementTree as ET
for f in sys.argv[1:]:
    try: ET.parse(f)
    except Exception as e: print(f'{f}: {e}')
" $(git diff --cached --name-only | grep '\.xml$')
```

`aapt2` is not required for this, and the scan must cover `res/layout/`,
`res/xml/`, and `res/drawable/*.xml`, not just the Kotlin sources. An artefact
sweep that only globs `*.kt` leaves every resource file unchecked — that is the
common miss, because the prose-heavy files are the new ones.

## 11. Home-screen widget di app Compose: `RemoteViews` bukan View hierarchy

Widget adalah satu-satunya permukaan app yang hidup tanpa `Activity`, dan
itulah yang membuatnya berbeda dari semua bagian lain. Kalau project masih
Compose, ada tiga batasan yang langsung merusak hasil kalau diabaikan:

- **Compose `Icons.Filled.*` tidak bisa dipakai.** `RemoteViews` menerima
  drawable resource, bukan `ImageVector`. Ikon harus ada sebagai vektor XML;
  ambil path dari Material Symbols yang sama dengan ikon Compose supaya
  keduanya tidak terlihat seperti dua produk berbeda.
- **Coil/Glide tidak bisa dipakai.** `RemoteViews` hanya menerima `Bitmap`
  yang sudah jadi — tidak ada loader gambar di dalam widget. Artwork harus
  di-decode provider (`contentResolver.openInputStream` + `BitmapFactory`)
  lalu diteruskan sebagai nilai lewat `setImageViewBitmap`. Coil yang dipakai
  di app tidak akan pernah jalan di sini.
- **Tidak ada `stringResource`.** Semua teks lewat `getString`.

Widget **menyambung ke playback service lewat `MediaController` yang sama**,
bukan memegang player sendiri. Dua `ExoPlayer` untuk satu antrean akan saling
menimpa posisi.

### `updatePeriodMillis=0` hampir selalu benar

Widget tidak butuh siklus polling. State datang dari `Player.Listener`
(`onIsPlayingChanged`, `onMediaItemTransition`), jadi sistem tidak perlu
menjalankan provider yang tidak melakukan apa-apa. Yang **wajib** di-refresh
adalah **ikon tombol**: tanpa itu widget yang sudah lama menempel akan
menampilkan tombol play padahal sedang pausing.

### Lepas controller di `onDisabled`, bukan `onDeleted`

`onDeleted` tidak dijamin berjalan sebelum proses mati, dan `MediaController`
yang tertinggal menahan service tetap hidup tanpa alasan. `onDisabled`
dipanggil saat widget terakhir dilepas — itu titik lepasnya.

### `widgetFeatures="reconfigurable"` hanya kalau ada config activity

Menandainya tanpa activity konfigurasi membuat launcher menampilkan tombol
konfigurasi yang mengarah ke layar kosong.

### Receiver: `exported="false"` + aksi berawalan package sendiri

Hanya home screen yang boleh memanggil provider. Aksi di dalam
(`com.meowlab.app.widget.NEXT`) harus berawalan package sendiri, kalau tidak
intent dari app lain bisa menyuruh widget memutar atau menjeda.

## 12. Baris tombol: `Row` memotong, `FlowRow` membungkus

Tiga tombol dalam satu `Row` — "Putar semua", "Ubah nama", "Unduh playlist" — melebihi
lebar layar sempit. `Row` tidak membungkus: tombol ketiga keluar dari viewport dan
terpotong di tepi kanan. Yang dilihat pengguna bukan "tombol tidak muat" tapi **kotak
yang tidak beraturan**, karena sisa kotak yang terpotong masih menggantung di layar.

`FlowRow` memindahkan tombol yang tidak muat ke baris berikutnya:

```kotlin
@OptIn(ExperimentalLayoutApi::class)   // FlowRow masih experimental
@Composable
fun DetailScreen() {
    FlowRow(
        modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),   // tanpa ini, baris kedua menempel
    ) {
        Button(onClick = ::playAll) { /* … */ }
        TextButton(onClick = ::rename) { /* … */ }
        if (songs.any { it.canDownload() }) {
            OutlinedButton(onClick = { downloadAll(songs) }) { /* … */ }
        }
    }
}
```

Tiga bagian yang wajib berpasangan, dan ketiganya tidak terlihat di diff:

1. **`@OptIn(ExperimentalLayoutApi::class)`** pada fungsi yang memakainya, plus
   import `ExperimentalLayoutApi` dan `FlowRow`. Tanpa ini CI gagal di baris deklarasi.
2. **`verticalArrangement` diisi.** `FlowRow` tidak memberi jarak antar-baris secara
   default; tanpa itu baris kedua menempel pada baris pertama dan itu terlihat
   sama kumanya tidak beraturan — cacat yang berbeda dengan gejala aslinya.
3. **`verticalAlignment = Alignment.CenterVertically` DIHAPUS.** Properti itu milik
   `Row`; membiarkannya di `FlowRow` gagal compile.

**Cari cacat yang sama di file lain sebelum push.** Layout pola `Row` + tombol
bersyarat dipakai ulang lintas layar, jadi satu layar yang diperbaiki biasanya punya
saudara yang rusak identik. `grep -n 'Row(' app/src/main/kotlin/**/ui/screens/` lalu
baca masing-masing Row yang berisi lebih dari satu tombol aksi.

## 13. Refactoring a shared composable: the symbol, not the file

Widening or relocating a helper that already has callers breaks them in ways a
diff does not show. Two rules, both learned the hard way:

**Grep the tree for the SYMBOL before changing its signature.** Changing
`card: @Composable () -> Unit` to `card: @Composable (Format) -> Unit` breaks
every existing call site, and each break surfaces as an error in a *different*
file than the one being edited — so the diff of the file you changed looks
complete and correct.

```bash
grep -rn '\bYourHelperName\b' app/src/main --include=*.kt
```

**Widening a parameter is not a default-value edit.** A parameter with a
default is additive; a parameter whose *type* changes is a breaking change even
when the arity is identical. If old callers must keep working, add a new
overload rather than changing the existing signature.

**Moving a `private` composable to `internal` does NOT remove the old copy.**
Declaring the shared one in the new file while the `private` one still sits in
the old file is a redeclaration in the same package — CI fails on
"Conflicting overloads"/"redeclaration" pointing at BOTH files, and the real
cause (the leftover private copy) is not the line the error names. Delete the
old declaration in the same commit that adds the shared one; a grep for the
symbol lists both sites so you cannot miss either.

Corollary from §4: when a component becomes shared, move it to the file the
majority of callers live in, and grep the symbol first — the private copy in the
original file is the single most common thing to forget.

## 14. Share cards: fixed-density render, dual ratio, live-position excerpt

A share card renders off-screen at a fixed pixel size, is captured to a bitmap,
and goes to the OS share sheet. Four things that are invisible in a diff:

- **`AsyncImage` needs `allowHardware(false)`** on a share card. Hardware
  bitmaps cannot be drawn to a software canvas, so the preview looks correct and
  the failure appears only when share is pressed.
- **The share must capture the same graphics layer the preview drew.** A second
  render can differ from what the user approved; `graphicsLayer` +
  `drawWithContent { layer.record { … } }` guarantees one render.
- **Feed 4:5 vs story 9:16 is a decision, not a constant.** Readable content
  (a lyric, a quote) gets cropped in a feed if it is 9:16. Make the format a
  parameter of the shared dialog, default to whatever the card used before the
  selector existed, label the selector by destination ("Post"/"Story"), and show
  it only to cards whose content actually reshapes between formats.
- **Slice live content from the live position**, skipping empty entries, and
  backfill from before the cursor one-at-a-time-from-the-back so reading order
  never inverts. An empty slice disables the button rather than rendering a blank
  card.

Bitmap export, FileProvider grant details, QR correction level, and the pure
excerpt function's test cases:
`references/share-cards.md`.

## Verify before declaring done

```bash
# Symbol-level sweep: every call site of a signature you changed or moved.
grep -rn '\bYourHelperName\b' app/src/main --include=*.kt

# Garbled characters in comments you authored. Catches script substitution
# (a Chinese or Cyrillic token inside Indonesian prose), NOT word-salad like
# a mangled identifier — for that, read your own comment diff before pushing.
grep -nP '[\x{3000}-\x{9FFF}\x{AC00}-\x{D7AF}\x{0400}-\x{04FF}]' <changed .kt>

python3 scripts/kotlin_dead_imports.py <changed .kt files>
gh run view <RUN_ID> --log-failed | grep -E 'Unresolved reference|error:'
```

```bash
python3 scripts/kotlin_dead_imports.py <changed .kt files>
gh run view <RUN_ID> --log-failed | grep -E 'Unresolved reference|error:'
```

## Pitfalls

- `Icon(painter, tint)` on a full-colour raster drains the colour. Swap to `Image`
  in the same edit.
- A composable using `.align` / `.weight` / a scope-default `fillMax*` must be
  declared as the matching scope extension, or it does not compile.
- Same package means no import; a DIFFERENT package means the caller needs the
  import, and the error lands in the caller's file.
- Duplicated call sites drift silently; extract to one composable at three or more.
- Full-bleed raster at 100% of a gradient tile makes every row identical. Leave
  margin.
- Launcher framing is not tile framing; the adaptive mask is what forces the safe
  zone, and there is no mask on an in-app tile.
- Replacing a drawable does not update the spec. Rewrite the false rule in place,
  turn absolute prohibitions into named exceptions, grep for cross-references.
- Unverified composables fail CI. A green run is the only compile evidence.
- A `--` inside an XML comment terminates it early and breaks the resource build.
- Widget: Compose icons, Coil, and `stringResource` are all unavailable in
  `RemoteViews`; icons must be vector XML, artwork must be a decoded Bitmap.
- Two or more action buttons in one `Row` get clipped on narrow screens and read as a
  misaligned box. Use `FlowRow` with `@OptIn`, `verticalArrangement`, and no
  `verticalAlignment` — then check the sibling screens for the same Row.
- Changing a parameter's TYPE breaks every caller even with an arity-preserving
  default. Grep the symbol first; add an overload instead of reshaping a
  signature in place.
- Promoting a `private` composable to `internal` leaves the old copy behind unless
  you delete it — the error names both files, neither of which is the real cause.
- Long prose in comments can come out with substituted or scrambled characters.
  Grep for CJK/Hangul/Cyrillic in `.kt`, and read your own comment diff before pushing.
