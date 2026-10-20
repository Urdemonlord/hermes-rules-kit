#!/usr/bin/env python3
"""Rebrand mekanis fork Android: pindah direktori paket, ganti token, rename berkas.

Urutan langkahnya yang penting:
  1. git mv direktori paket (tiap source set, tiap modul yang punya paket itu)
  2. ganti token di berkas teks (package/import + nama brand)
  3. rename berkas yang NAMANYA memuat brand

Langkah 3 bukan pelengkap: berkas resource seperti ic_<brand>_mark.xml dan
values-*/<brand>_strings.xml tidak punya referensi teks yang bisa diganti,
jadi tanpa rename berkas kode akan menunjuk R.drawable.ic_<baru>_mark yang
tidak ada.

Yang TIDAK dikerjakan skrip ini (kerjakan manual, lihat SKILL.md bagian 4):
  - direktori skema Room harus sama dengan FQCN kelas @Database
  - nama app berhuruf besar di res/values/app_name.xml dan varian flavor-nya
  - konstanta owner/repo updater dan URL github.com/<owner>/<repo>
  - versionCode/versionName dan rootProject.name

Pemakaian:
  python3 rebrand_fork.py --root ~/repo \
      --pkg-from com.example.lama --pkg-to com.meowlabs.baru \
      --brand-from lama --brand-to baru [--dry]

Asumsi: brand adalah satu kata huruf kecil ("musicfy"), dan brand_to tidak
memuat brand_from sebagai substring.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

TEXT_EXT = {".kt", ".kts", ".xml", ".pro", ".conf", ".sh", ".json", ".yml",
            ".yaml", ".properties", ".md", ".txt", ".toml", ".gradle", ".html",
            ".po", ".pot"}
SKIP_FILES = {"LICENSE"}
SOURCE_BASES = [
    "app/src/main/kotlin", "app/src/test/kotlin", "app/src/androidTest/kotlin",
    "app/src/debug/kotlin", "app/src/release/kotlin",
]


def git(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ! git {' '.join(args[:2])}: {r.stderr.strip()[:200]}", file=sys.stderr)
    return r


def tracked(root: pathlib.Path) -> list[str]:
    return subprocess.run(["git", "-C", str(root), "ls-files"],
                          capture_output=True, text=True).stdout.split()


def source_bases(root: pathlib.Path, pkg_from: str) -> list[str]:
    """Source set mana saja yang benar-benar punya direktori paket itu."""
    rel = pkg_from.replace(".", "/")
    bases = list(SOURCE_BASES)
    for group in ("modules", "providers"):
        for mod in sorted((root / group).glob("*")):
            if not mod.is_dir():
                continue
            for kind in ("main", "test", "androidTest"):
                bases.append(f"{group}/{mod.name}/src/{kind}/kotlin")
    return [b for b in bases if (root / b / rel).is_dir()]


def move_packages(root: pathlib.Path, pkg_from: str, pkg_to: str, dry: bool) -> int:
    moved = 0
    for base in source_bases(root, pkg_from):
        src = root / base / pkg_from.replace(".", "/")
        dst = root / base / pkg_to.replace(".", "/")
        print(f"  mv {src.relative_to(root)} -> {dst.relative_to(root)}")
        moved += 1
        if dry:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        git(root, "mv", str(src.relative_to(root)), str(dst.relative_to(root)))
        parent = src.parent  # bersihkan direktori induk yang jadi kosong (com/example)
        while parent != root / base and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return moved


def rewrite_tokens(root: pathlib.Path, pkg_from: str, pkg_to: str,
                   brand_from: str, brand_to: str, dry: bool) -> tuple[int, int]:
    n_pkg = n_brand = 0
    variants = (brand_from.capitalize(), brand_from, brand_from.upper())
    replacements = (brand_to.capitalize(), brand_to, brand_to.upper())
    for f in tracked(root):
        p = root / f
        if p.suffix.lower() not in TEXT_EXT or p.name in SKIP_FILES or not p.is_file():
            continue
        try:
            s = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        s2 = s.replace(pkg_from, pkg_to)
        if s2 != s:
            n_pkg += 1
        s3 = s2
        for old, new in zip(variants, replacements):
            s3 = s3.replace(old, new)
        if s3 != s2:
            n_brand += 1
        if s3 != s and not dry:
            p.write_text(s3, encoding="utf-8")
    return n_pkg, n_brand


def rename_files(root: pathlib.Path, brand_from: str, brand_to: str, dry: bool) -> int:
    n = 0
    for f in tracked(root):
        if brand_from not in f.lower():
            continue
        new = (f.replace(brand_from.capitalize(), brand_to.capitalize())
                .replace(brand_from.upper(), brand_to.upper())
                .replace(brand_from, brand_to))
        if new == f:
            continue
        n += 1
        print(f"  mv {f} -> {new}")
        if dry:
            continue
        (root / new).parent.mkdir(parents=True, exist_ok=True)
        git(root, "mv", f, new)
    return n


def report_leftovers(root: pathlib.Path, needles: list[str]) -> None:
    files = tracked(root)
    for needle in needles:
        hits = subprocess.run(["git", "-C", str(root), "grep", "-l", "-i", needle],
                              capture_output=True, text=True).stdout.split()
        hits += [f for f in files if needle.lower() in f.lower() and f not in hits]
        print(f"  sisa '{needle}': {len(hits)}")
        for f in hits[:10]:
            print("     ", f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pkg-from", required=True)
    ap.add_argument("--pkg-to", required=True)
    ap.add_argument("--brand-from", required=True)
    ap.add_argument("--brand-to", required=True)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    root = pathlib.Path(a.root).expanduser().resolve()
    if not (root / ".git").exists():
        sys.exit(f"bukan repo git: {root}")
    if a.brand_from in a.brand_to:
        sys.exit("brand-to memuat brand-from — penggantian akan berantai")
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    if dirty and not a.dry:
        sys.exit("working tree tidak bersih — commit atau stash dulu, atau pakai --dry")

    print("1. pindah direktori paket")
    print(f"   {move_packages(root, a.pkg_from, a.pkg_to, a.dry)} direktori")
    print("2. ganti token")
    n_pkg, n_brand = rewrite_tokens(root, a.pkg_from, a.pkg_to,
                                    a.brand_from, a.brand_to, a.dry)
    print(f"   paket di {n_pkg} berkas, brand di {n_brand} berkas")
    print("3. rename berkas")
    print(f"   {rename_files(root, a.brand_from, a.brand_to, a.dry)} berkas")
    print("4. sisa kata brand")
    report_leftovers(root, [a.brand_from, a.brand_from.upper()])
    print("   MANUAL: skema Room = FQCN kelas @Database, app_name huruf besar,")
    print("   owner/repo updater, versionCode/versionName, rootProject.name.")


if __name__ == "__main__":
    main()
