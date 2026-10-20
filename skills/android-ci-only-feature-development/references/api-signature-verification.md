# Verifikasi signature API tanpa build lokal

Resep untuk repo yang Gradle-nya dilarang. Tujuannya satu: **jangan menebak
syntax lalu membayarnya dengan putaran CI.** Compiler tetap CI, tapi sebagian
besar tebakan bisa dibunuh lebih dulu di JVM.

## Ambil sumbernya dari Maven, baca signature aslinya

Sumber artefak Compose/AndroidX ada di `maven.google.com`. Unduh `-sources.jar`
dan baca deklarasi sebenarnya — bukan dokumentasi, bukan hafalan versi.

```bash
mkdir -p /tmp/m3 && cd /tmp/m3
curl -sL -o src.jar \
  'https://maven.google.com/androidx/compose/material3/material3-android/1.5.0-alpha12/material3-android-1.5.0-alpha12-sources.jar'
unzip -o -q src.jar -d src
```

Versi artefaknya diambil dari `gradle/libs.versions.toml` (untuk yang punya
`version.ref`) — jangan menebak. Kalau versinya datang dari BOM, baca POM BOM-nya:

```bash
curl -sL 'https://maven.google.com/androidx/compose/compose-bom/<versi>/compose-bom-<versi>.pom' \
  | grep -B3 '<artifactId>material-icons-extended</artifactId>'
```

Lalu cetak signature-nya utuh (parameter + default), bukan cuma namanya:

```python
import re
src = open('/tmp/m3/src/commonMain/androidx/compose/material3/ModalBottomSheet.kt', encoding='utf-8').read()
for m in re.finditer(r'fun (ModalBottomSheet|rememberModalBottomSheetState)\s*\(', src):
    i = src.index('(', m.end() - 1); depth = 0; j = i
    while j < len(src):
        if src[j] == '(': depth += 1
        elif src[j] == ')':
            depth -= 1
            if depth == 0: break
        j += 1
    print(src[m.start():j + 1])
```

Yang dicari dari hasil itu: **nama parameter**, **default**, dan **level opt-in**.

## Tiga hal yang selalu perlu dicek

| Yang dicek | Cara | Kalau terlewat |
|---|---|---|
| Anotasi opt-in | `grep -B3 'fun NamaApi(' <sumber>` → `@ExperimentalMaterial3Api` | `This declaration is experimental` di CI |
| Nama parameter | dari signature, bukan ingatan | `None of the following candidates can be called` |
| Nama ikon | `test -f <icons>/<Nama>.kt` | `Unresolved reference` |

Contoh nyata: `ModalBottomSheet` di material3 1.5.0-alpha12 butuh
`@OptIn(ExperimentalMaterial3Api::class)` dan parameternya `sheetState:`,
`containerColor:`, `contentColor:`, `onDismissRequest:` — plus
`rememberModalBottomSheetState(skipPartiallyExpanded = true)`. Semua itu
terbaca dari sumbernya dalam satu panggilan, tanpa satu pun run CI.

## Ikon: core vs extended, dan yang deprecated

`material-icons-core` dan `material-icons-extended` punya isi yang **berbeda**,
dan nama yang ada di satu belum tentu ada di yang lain. Cek keberadaan sebelum
memakai:

```bash
# extended
d=/tmp/m3/icons/commonMain/androidx/compose/material/icons/filled
# core
c=/tmp/m3/core/commonMain/androidx/compose/material/icons/filled
for n in Star Favorite Code Link OpenInNew VolunteerActivism BugReport; do
  printf '%-20s core:%s ext:%s\n' "$n" \
    "$(test -f $c/$n.kt && echo Y || echo -)" "$(test -f $d/$n.kt && echo Y || echo -)"
done
```

Yang terbukti dari pembagian itu: `Star` dan `Favorite` ada di **core**,
sementara `Code`, `Link`, `OpenInNew`, `VolunteerActivism`, `BugReport` hanya di
**extended**. Keduanya terpasang di repo ini, jadi impornya
`androidx.compose.material.icons.filled.<Nama>` — tapi jangan mengarang nama
yang tidak ada di salah satu daftar.

Ikon yang punya makna arah **dideprecate** di versi baru. Cek dengan grep, jangan
pakai yang lama:

```bash
grep -n 'Deprecated\|AutoMirrored' <icons>/KeyboardArrowRight.kt
# -> "Use the AutoMirrored version at Icons.AutoMirrored.Filled.KeyboardArrowRight"
```

Impor yang benar: `androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight`,
dipakai sebagai `Icons.AutoMirrored.Filled.KeyboardArrowRight`. Yang deprecated
masih compile — ia hanya mengotori build dengan warning, jadi ia tidak akan
pernah ketahuan dari CI merah.

## Batcher: satu panggilan, semua artefak

Unduhan Maven, unzip, dan pencetakan signature **semua di satu
`execute_code`**. Verifikasi satu artefak per tool call membakar iterasi yang
seharusnya dipakai untuk menulis kodenya — dan batas iterasi adalah runway yang
habis sebelum commit, bukan sesudah.

Kalau ada beberapa API yang diragukan, kumpulkan daftarnya dulu, lalu satu
panggilan yang mengunduh semuanya, mencetak semua signature, dan mencetak
keberadaan semua ikon.

## Yang tidak bisa dibuktikan dengan cara ini

- **Keberadaan API di classpath.** `-sources.jar` membuktikan deklarasinya ada
di versi itu, bukan bahwa dependency-nya benar-benar masuk ke modul ini. Cek
`implementation(libs.…)` di `build.gradle.kts` untuk itu.
- **Perilaku runtime.** Signature benar tidak berarti sheetnya terbuka. Ini tetap
batas bukti yang sama seperti "hijau bukan berfungsi".
- **Pemakaian yang sudah ada di repo.** Cari call site, bukan import
(lihat bagian "Pola yang dikira ada" di SKILL.md).
