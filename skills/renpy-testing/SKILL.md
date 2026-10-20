---
name: renpy-testing
description: Use when testing or debugging a Ren'Py game.
---

# Menguji Game Ren'Py

## Aturan utama

**Uji boot BUKAN uji fungsional.** Menjalankan game tanpa error tidak membuktikan
apa pun jika alur tidak pernah masuk ke `label start`. Bug interpolasi teks,
`NameError`, dan kesalahan runtime hanya muncul saat dialog benar-benar
dievaluasi.

Selalu mainkan alur sampai akhir dengan hook otomatis (lihat template di bawah)
sebelum menyatakan kode Ren'Py aman.

## Jebakan interpolasi teks (penyebab crash paling umum)

Ren'Py membaca `[ ... ]` sebagai ekspresi Python. **Kurung siku bersarang
merusak sintaks:**

```renpy
# SALAH - SyntaxError: invalid syntax saat dialog tampil
"[ Hari [day] dari [total] ]"

# BENAR - satu tingkat kurung saja
"Hari [day] dari [total]"

# BENAR - literal kurung siku ditulis dobel
"[[INFO]] Hari [day]"
```

Validasi statis semua string sebelum menjalankan game:

```python
import re
def find_interpolations(text):
    """Temukan [expr] dengan penyeimbangan kurung; [[ = literal."""
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i] == '[':
            if i + 1 < n and text[i+1] == '[':
                i += 2; continue
            depth, j = 1, i + 1
            while j < n and depth:
                if text[j] == '[': depth += 1
                elif text[j] == ']': depth -= 1
                j += 1
            out.append(text[i+1:j-1] if depth == 0 else None)
            i = j if depth == 0 else i + 1
        else:
            i += 1
    return out

# setiap ekspresi harus lolos compile(expr, '<i>', 'eval')
```

Selalu uji validatornya terhadap bentuk buggy yang diketahui - validator yang
selalu bilang "OK" lebih berbahaya daripada tidak ada validator.

## Hook untuk auto-play headless

Statement `menu:` dan `renpy.display_menu` adalah **dua jalur berbeda** - keduanya
harus di-hook:

| Jalur | Fungsi | Nilai balik |
|---|---|---|
| statement `menu:` | `renpy.store.menu(items)` | **indeks** pilihan |
| pemanggilan langsung | `renpy.display_menu(items)` | nilai pilihan |

`renpy.exports.menu` memanggil `renpy.store.menu(new_items)`, lalu `ast.Menu`
melakukan `self.items[choice][2][0]` - mengembalikan objek action (mis.
`ChoiceReturn`) menyebabkan `TypeError: list indices must be integers`.

```renpy
init python:
    def _auto_menu(items, *args, **kwargs):
        return 0            # INDEKS, bukan nilai
    def _auto_display_menu(items, *args, **kwargs):
        return items[0][1]  # nilai
    def _auto_input(prompt="", *args, **kwargs):
        return "1"
    def _install():
        renpy.store.menu = _auto_menu
        renpy.display_menu = _auto_display_menu
        renpy.input = _auto_input
        _preferences.skip_unseen = True
        _preferences.skip_after_choices = True
        config.skipping = "fast"

label splashscreen:
    $ _install()
    call start          # jalankan alur sungguhan
    $ renpy.quit()
    return
```

Hindari menu yang bisa berputar tanpa akhir (mis. "jelajah bebas") di hook menu.

## Perintah

```bash
# lint
cd /path/to/renpy-sdk && ./renpy.sh /path/to/project lint

# jalankan headless (wajib xvfb; SDL_VIDEODRIVER=dummy tidak cukup)
xvfb-run -a -s "-screen 0 1280x720x24" /path/to/renpy-sdk/renpy.sh . run

# screenshot dari dalam screen (timer), BUKAN dari callback interaksi
screen probe():
    timer 2.5 action [Function(renpy.screenshot, "/tmp/shot.png"), Function(renpy.quit)]
```

Catatan headless: `renpy.pause(hard=True)` menggantung. Callback interaksi berjalan
sebelum layar digambar, jadi screenshot dari sana akan kosong.

## Membuktikan uji benar-benar bekerja

Uji yang tidak pernah gagal tidak membuktikan apa pun. Setelah uji lolos:

1. Kembalikan bug yang diketahui: `git checkout <file>` (versi buggy).
2. Jalankan uji - **harus gagal** dengan gejala yang sama seperti laporan pemain.
3. Pulihkan versi perbaikan, jalankan lagi - harus lolos.

Baru setelah itu uji boleh dipercaya.
