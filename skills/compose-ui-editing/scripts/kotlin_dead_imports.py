#!/usr/bin/env python3
"""Report imports whose simple name never appears in the body of a Kotlin file.

Extracting a shared composable, or swapping a component for an equivalent one,
leaves imports behind that the body no longer references. Those surface as lint
warnings rather than errors, so nothing blocks the change.

Usage:
    python3 kotlin_dead_imports.py app/src/main/kotlin/**/CoverImage.kt [...]
    python3 kotlin_dead_imports.py $(git diff --cached --name-only -- '*.kt')

Exits 1 when any dead import is found, so it works as a pre-commit gate.

Property-delegate operator imports (`getValue`, `setValue`, `provideDelegate`) are
excluded: `by` resolves them implicitly, so a plain body-name search always reports
them as dead and deleting them breaks the build.

Known limitation: references inside comments count as usages, so commented-out code
is not flagged. Each line is a candidate to eyeball, not an instruction to delete.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DELEGATE_IMPORTS = {"getValue", "setValue", "provideDelegate"}
IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+(?:\.\*)?)(?:\s+as\s+(\w+))?\s*$")
PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)")


def analyse(path: Path) -> tuple[str | None, list[tuple[int, str, str]]]:
    """Return (package, [(line, simple_name, fully_qualified), ...] dead imports)."""
    text = path.read_text(encoding="utf-8", errors="replace")

    package: str | None = None
    imports: list[tuple[int, str, str]] = []
    body: list[str] = []

    for number, line in enumerate(text.splitlines(), 1):
        package_match = PACKAGE_RE.match(line)
        if package_match:
            package = package_match.group(1)
            continue

        import_match = IMPORT_RE.match(line)
        if import_match:
            fqn, alias = import_match.group(1), import_match.group(2)
            simple = alias or fqn.rsplit(".", 1)[-1]
            imports.append((number, simple, fqn))
            continue

        body.append(line)

    body_text = "\n".join(body)

    dead: list[tuple[int, str, str]] = []
    for number, simple, fqn in imports:
        if simple in DELEGATE_IMPORTS:
            continue
        if fqn.endswith(".*"):
            continue
        if not re.search(rf"(?<![\w.]){re.escape(simple)}\b", body_text):
            dead.append((number, simple, fqn))

    return package, dead


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Kotlin files to inspect")
    args = parser.parse_args()

    missing = [f for f in args.files if not Path(f).is_file()]
    if missing:
        print("not a file:", ", ".join(missing), file=sys.stderr)
        return 2

    total = 0
    for name in args.files:
        path = Path(name)
        package, dead = analyse(path)
        if not dead:
            continue
        total += len(dead)
        print(f"{name}  (package {package or '?'})")
        for number, simple, fqn in dead:
            # Same-package imports are unnecessary rather than harmful; flag distinctly.
            same_package = package and fqn.rsplit(".", 1)[0] == package
            note = "  <- same package, import is unnecessary" if same_package else ""
            print(f"  line {number}: {simple}  (import {fqn}){note}")

    if total:
        print(f"\n{total} dead import(s). Remove, or confirm each is genuinely unused.")
        return 1

    print("no dead imports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
