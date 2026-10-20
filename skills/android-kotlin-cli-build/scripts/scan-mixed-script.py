#!/usr/bin/env python3
"""Flag non-Latin garbage in Kotlin sources, docs and commit-message files.

Bulk-writing a long file can interleave stray CJK/Cyrillic/Arabic characters into
prose. Kotlin compiles it, lint stays green, and the damage is invisible to every
automated check -- it only reads as corruption to a human.

Legitimate non-ASCII that this must NOT flag:
  - Latin-1 punctuation used in Indonesian prose: -- en/em dash, curly quotes
  - Smart quotes and ellipsis
  - Anything in an emoji or pictograph range (icons, status glyphs)
  - User-facing translation strings that legitimately contain non-Latin scripts

Run it over the whole tree before pushing, and over a commit message before
committing.

Usage:
    scan-mixed-script.py app/src CHANGELOG.md README.md
    scan-mixed-script.py --all app/src/main/kotlin   # show every non-ASCII char

Exit 1 when a suspicious character is found.
"""
import os
import re
import sys

# CJK, kana, hangul, Cyrillic, Greek, Hebrew, Arabic, Devanagari, Thai.
# Deliberately excludes punctuation, symbols, emoji and pictographs.
SUSPECT = re.compile(
    '['
    '　-〿'      # CJK punctuation-ish
    '぀-ヿ'      # kana
    '㐀-䶿'      # CJK ext A
    '一-鿿'      # CJK unified
    '가-힯'      # hangul syllables
    '豈-﫿'      # CJK compat
    'Ѐ-ӿ'      # Cyrillic
    'Ͱ-Ͽ'      # Greek
    '֐-׿'      # Hebrew
    '؀-ۿ'      # Arabic
    'ऀ-ॿ'      # Devanagari
    '฀-๿'      # Thai
    ']+'
)

TEXT_EXT = {'.kt', '.kts', '.java', '.md', '.xml', '.json', '.txt', '.pro',
            '.gradle', '.yml', '.yaml', '.toml', '.sq'}


def scan_text(path, show_all, hits):
    try:
        with open(path, encoding='utf-8') as fh:
            for i, line in enumerate(fh, 1):
                for m in SUSPECT.finditer(line):
                    chars = ''.join(sorted(set(m.group(0))))
                    if show_all:
                        hits.append((path, i, chars, line.strip()[:90]))
                    else:
                        hits.append((path, i, chars, line.strip()[:90]))
                        break
    except (UnicodeDecodeError, OSError):
        pass


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    show_all = '--all' in sys.argv
    if not args:
        print(__doc__)
        return 2

    total = 0
    for target in args:
        if os.path.isfile(target):
            candidates = [target]
        else:
            candidates = []
            for dirpath, _, files in os.walk(target):
                for f in sorted(files):
                    if os.path.splitext(f)[1] in TEXT_EXT:
                        candidates.append(os.path.join(dirpath, f))
        for path in candidates:
            hits = []
            scan_text(path, show_all, hits)
            for _, line_no, chars, text in hits:
                print('%s:%d: non-Latin %r' % (path, line_no, chars))
                print('    %s' % text)
                total += 1

    if total:
        print('\n%d suspicious line(s). In Indonesian comments and commit '
              'messages these are corruption, not style.' % total)
        return 1
    print('OK: no non-Latin characters in the scanned text.')
    return 0


if __name__ == '__main__':
    sys.exit(main())