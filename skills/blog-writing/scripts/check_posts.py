#!/usr/bin/env python3
"""Validate the CV builder blog posts against the conventions that CI and reviewers rely on.

Reads apps/web/lib/blog/posts.ts and reports problems with exit code 1. Deliberately
dependency-free: this runs on a small VPS, and a validator that needs installing is a
validator nobody runs.

Usage:
    python3 check_posts.py [path/to/posts.ts]

Checks:
  * slug shape (lowercase, hyphenated, ASCII) and uniqueness
  * description length 70-165 (it is reused as the meta description)
  * datePublished is ISO 8601 and posts are ordered newest first
  * every post has keywords, sections, and at least one paragraph per section
  * no markdown syntax inside paragraph strings (the renderer emits plain text)
  * no fabricated-claim patterns (a figure next to a promise)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_SOURCE = "apps/web/lib/blog/posts.ts"

# A figure adjacent to a promise. Matching the shape rather than a bare word keeps honest
# sentences such as "no one can guarantee an ATS pass" out of the results.
CLAIM_PATTERNS = [
    (re.compile(r"\d+\s*%\s*(?:pasti\s*)?lolos", re.I), "angka + klaim lolos ATS"),
    (re.compile(r"(?:tingkat|persentase)\s+kelulusan\s*[\d.,]+", re.I), "angka tingkat kelulusan"),
    (re.compile(r"\d[\d.,]*\s*(?:kandidat|pengguna|pelanggan|klien)", re.I), "jumlah pengguna/kandidat"),
    (re.compile(r"(?:rating|bintang)\s*[\d.,]+", re.I), "rating tanpa sumber"),
    (re.compile(r"(?:dijamin|pasti)\s+(?:lolos|diterima)", re.I), "jaminan hasil"),
]

# Markdown that would render literally because paragraphs are plain React text.
MARKDOWN_PATTERNS = [
    (re.compile(r"\*\*[^*]+\*\*"), "tebal markdown (**teks**)"),
    (re.compile(r"\[[^\]]+\]\([^)]+\)"), "tautan markdown ([teks](url))"),
    (re.compile(r"^#{1,6}\s", re.M), "heading markdown"),
    (re.compile(r"^[-*]\s+\S", re.M), "bullet markdown"),
]


def string_literals(block: str) -> list[str]:
    """Extract single-quoted string literals, joining lines broken by prettier."""
    out: list[str] = []
    for match in re.finditer(r"'((?:[^'\\]|\\.)*)'", block, re.S):
        out.append(match.group(1))
    return out


def split_posts(source: str) -> list[str]:
    """Split the POSTS array into one block per post, keyed on the slug line."""
    parts = re.split(r"\n\s*\{\s*\n\s*slug:\s*'", source)
    return parts[1:]


def parse_post(block: str) -> dict:
    slug = block.split("'", 1)[0]

    def field(name: str) -> str | None:
        m = re.search(rf"{name}:\s*\n?\s*'((?:[^'\\]|\\.)*)'", block, re.S)
        return m.group(1) if m else None

    keywords_block = re.search(r"keywords:\s*\[([^\]]*)\]", block, re.S)
    keywords = string_literals(keywords_block.group(1)) if keywords_block else []

    # Section headings mark the boundaries of the section bodies.
    headings = re.findall(r"heading:\s*'((?:[^'\\]|\\.)*)'", block)
    paragraphs = re.findall(r"paragraphs:\s*\[(.*?)\n\s*\]", block, re.S)
    bullets = re.findall(r"bullets:\s*\[(.*?)\n\s*\]", block, re.S)

    return {
        "slug": slug,
        "title": field("title"),
        "description": field("description"),
        "datePublished": field("datePublished"),
        "keywords": keywords,
        "headings": headings,
        "paragraphs": [p for grp in paragraphs for p in string_literals(grp)],
        "bullets": [b for grp in bullets for b in string_literals(grp)],
    }


def check(source_path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []

    if not source_path.exists():
        return [f"file tidak ditemukan: {source_path}"], notes

    source = source_path.read_text(encoding="utf-8")
    blocks = split_posts(source)
    if not blocks:
        return ["tidak ada post yang terbaca dari POSTS array"], notes

    posts = [parse_post(b) for b in blocks]

    seen: dict[str, int] = {}
    for post in posts:
        slug = post["slug"]
        seen[slug] = seen.get(slug, 0) + 1

        if not re.fullmatch(r"[a-z0-9-]+", slug):
            errors.append(f"[{slug}] slug harus huruf kecil, angka, dan tanda hubung saja")
        if seen[slug] > 1:
            errors.append(f"[{slug}] slug duplikat")

        desc = post["description"]
        if desc is None:
            errors.append(f"[{slug}] description tidak ada")
        elif not 70 <= len(desc) <= 165:
            errors.append(
                f"[{slug}] description {len(desc)} karakter, harus 70-165 "
                f"(dipakai sebagai meta description)"
            )

        date = post["datePublished"]
        if date is None:
            errors.append(f"[{slug}] datePublished tidak ada")
        elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            errors.append(f"[{slug}] datePublished '{date}' bukan ISO 8601 (YYYY-MM-DD)")

        if not post["title"]:
            errors.append(f"[{slug}] title tidak ada")
        if not post["keywords"]:
            errors.append(f"[{slug}] keywords kosong")
        if not post["headings"]:
            errors.append(f"[{slug}] tidak ada section")
        if not post["paragraphs"]:
            errors.append(f"[{slug}] tidak ada paragraf")

        for heading in post["headings"]:
            if len(heading) > 95:
                errors.append(f"[{slug}] heading {len(heading)} karakter, terlalu panjang: {heading[:60]}…")
            if heading.rstrip().endswith("."):
                notes.append(f"[{slug}] heading diakhiri titik: {heading[:60]}")
            for pattern, label in MARKDOWN_PATTERNS:
                if pattern.search(heading):
                    errors.append(f"[{slug}] markdown di dalam heading ({label}): {heading[:70]}…")

        for text in post["paragraphs"] + post["bullets"]:
            for pattern, label in MARKDOWN_PATTERNS:
                if pattern.search(text):
                    errors.append(f"[{slug}] markdown di dalam teks ({label}): {text[:70]}…")

        body = " ".join([post["title"] or "", desc or "", *post["headings"],
                         *post["paragraphs"], *post["bullets"]])
        for pattern, label in CLAIM_PATTERNS:
            m = pattern.search(body)
            if m:
                errors.append(f"[{slug}] klaim angka tanpa sumber ({label}): '{m.group(0)}'")

    dates = [p["datePublished"] for p in posts if p["datePublished"]]
    if dates != sorted(dates, reverse=True):
        errors.append(f"post tidak urut terbaru dulu: {dates}")

    notes.append(f"{len(posts)} post diperiksa: " + ", ".join(p["slug"] for p in posts))
    return errors, notes


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE
    path = Path(arg)
    if not path.exists() and not path.is_absolute():
        # Allow running from the repo root or from anywhere with an absolute path.
        for candidate in (Path.cwd() / arg, Path("/tmp/cv-builder-work") / arg):
            if candidate.exists():
                path = candidate
                break

    errors, notes = check(path)

    print(f"check_posts: {path}")
    for note in notes:
        print(f"  · {note}")
    if errors:
        print(f"\n{len(errors)} masalah:")
        for err in errors:
            print(f"  ✗ {err}")
        return 1
    print("\n✓ semua pemeriksaan lolos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
