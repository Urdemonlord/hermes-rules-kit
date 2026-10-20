#!/usr/bin/env python3
"""Consistency checks for release documentation. See SKILL.md.

Usage:
    python3 check-release-docs.py --readme README.md --changelog CHANGELOG.md \
        [--version-file app/build.gradle.kts | package.json] [--repo OWNER/REPO]

Checks:
    version match   build file version vs topmost released CHANGELOG heading
    asserted count  "seven bugs" must agree with the list length below it
                    ("six of seven" is understood and skipped)
    readme links    internal links must point at files that exist
    tag links       changelog tag/compare links must resolve (needs --repo + gh)

Exit 1 if any hard check fails. Tag-link checks need network and `gh`; they are
skipped with a notice when unavailable.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6,
    "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10,
}

LIST_NOUN = (
    r"(?:bug|bugs|item|items|hal|things|langkah|steps|perbaikan|aturan|rules|"
    r"fitur|features|masalah|problem|problems|perubahan|changes)"
)

ITEM_LINE = re.compile(r"^\s*(?:[-*+]\s+|\*\*)")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def build_version(path: Path) -> str | None:
    """Extract versionName (gradle) or version (package.json)."""
    if not path.is_file():
        return None
    text = read(path)
    for pattern in (
        r'versionName\s*=\s*["\']([^"\']+)["\']',
        r'"version"\s*:\s*"([^"]+)"',
        r'^version\s*=\s*["\']([^"\']+)["\']',
    ):
        m = re.search(pattern, text, re.M)
        if m:
            return m.group(1).strip()
    return None


def changelog_versions(text: str) -> list[str]:
    return re.findall(r"^##\s*\[([0-9]+\.[0-9]+[^\]]*)\]", text, re.M)


def count_list_after(text: str, start: int) -> int:
    """Count consecutive list items beginning at or after `start`."""
    lines = text[start:].splitlines()
    items = 0
    started = False
    for line in lines:
        if ITEM_LINE.match(line):
            items += 1
            started = True
        elif started:
            # blank or continuation lines belong to the current item
            if not line.strip():
                continue
            if line[:1] in " \t":
                continue
            break
        elif line.strip():
            # prose before the list: allow a short lead-in, then give up
            if len(line.split()) > 12:
                break
    return items


def check_asserted_counts(text: str) -> list[str]:
    issues: list[str] = []
    pattern = r"\b(" + "|".join(NUMBER_WORDS) + r")\b([^.\n]{0,40}?)\b" + LIST_NOUN + r"\b"
    for m in re.finditer(pattern, text, re.I):
        between = m.group(2).lower()
        # "six of seven" / "enam dari tujuh" is a subset claim, not a count.
        if re.search(r"\b(dari|of)\b", between):
            continue
        claimed = NUMBER_WORDS[m.group(1).lower()]
        items = count_list_after(text, m.end())
        if items and items != claimed:
            issues.append(
                f"asserted '{m.group(1)}' but the list below has {items} items"
            )
    return issues


def check_readme_links(readme: Path) -> list[str]:
    issues: list[str] = []
    base = readme.parent
    for target in re.findall(r"\]\(([^)\s]+)", read(readme)):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        clean = target.split("#", 1)[0]
        if not clean:
            continue
        if not (base / clean).exists():
            issues.append(f"README link points at missing file: {target}")
    return issues


def check_tag_links(changelog: Path, repo: str) -> list[str]:
    issues: list[str] = []
    links = re.findall(r"^\[([^\]]+)\]:\s*(\S+)", read(changelog), re.M)
    for name, url in links:
        if name.lower() == "unreleased":
            continue
        if "/releases/tag/" not in url and "/compare/" not in url:
            continue
        tag = url.rstrip("/").split("/")[-1]
        if not tag or tag == "HEAD":
            continue
        try:
            out = subprocess.run(
                ["gh", "api", f"repos/{repo}/git/ref/tags/{tag}"],
                capture_output=True, text=True, timeout=25,
            )
        except (OSError, subprocess.SubprocessError):
            print("  note: cannot reach gh; tag-link check skipped")
            return issues
        if out.returncode != 0:
            issues.append(f"changelog link [{name}] points at missing tag: {tag}")
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="Check release documentation consistency.")
    ap.add_argument("--readme", type=Path)
    ap.add_argument("--changelog", type=Path)
    ap.add_argument("--version-file", type=Path)
    ap.add_argument("--repo", help="OWNER/REPO, enables tag-link checks via gh")
    args = ap.parse_args()

    if not args.readme and not args.changelog:
        ap.error("give at least --readme or --changelog")

    issues: list[str] = []
    changelog_text = ""

    if args.changelog:
        if not args.changelog.is_file():
            print(f"x changelog not found: {args.changelog}")
            return 1
        changelog_text = read(args.changelog)
        versions = changelog_versions(changelog_text)
        print(f"CHANGELOG versions: {', '.join(versions) if versions else '(none)'}")
        if not versions:
            issues.append("CHANGELOG has no '## [x.y.z]' heading")
        issues += check_asserted_counts(changelog_text)

        if args.version_file:
            version = build_version(args.version_file)
            if version is None:
                print(f"note: no version found in {args.version_file}")
            elif version not in versions:
                issues.append(
                    f"build version {version!r} is not a CHANGELOG heading {versions}"
                )
            elif versions and version != versions[0]:
                print(
                    f"note: build version {version} is not the topmost changelog "
                    f"entry ({versions[0]}); expected if unreleased work exists"
                )

    if args.readme:
        if not args.readme.is_file():
            print(f"x readme not found: {args.readme}")
            return 1
        issues += check_readme_links(args.readme)

    if args.changelog and args.repo:
        issues += check_tag_links(args.changelog, args.repo)

    print()
    if issues:
        print(f"FAIL ({len(issues)})")
        for i in issues:
            print(f"  x {i}")
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
