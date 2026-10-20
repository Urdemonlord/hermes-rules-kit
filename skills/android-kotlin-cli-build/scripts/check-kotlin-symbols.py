#!/usr/bin/env python3
"""Pre-push symbol checks for Kotlin code that cannot be compiled locally.

Two independent failure modes, both of which reach CI as a wasted cycle:

  DANGLING IMPORT   an internal import has no matching definition in the tree.
                    The compiler reports this as a cascade -- every use site,
                    plus `Unresolved reference` for the fields of the missing
                    type -- so one missing class looks like a dozen unrelated
                    errors.

  UNIMPORTED SYMBOL a type declared elsewhere in the project is USED in a file
                    that never imported it. Nothing points at the omission:
                    the file is internally consistent, the class exists, and
                    the only signal is the compiler naming a symbol the reader
                    has never seen before.

Usage:
    check-kotlin-symbols.py <src-root> <package-prefix>
    check-kotlin-symbols.py app/src/main/kotlin com.meowlabs.player

Exit 1 and list offenders when either check finds something.

PITFALL: extension functions (`fun Type.name(...)`) define a name that a plain
`class|fun|val` scan will miss, producing FALSE POSITIVES on every storage/helper
extension. Both declaration forms are collected below; if you hand-roll this
check, do the same before reporting anything.

PITFALL: a locally-declared name must never be reported as unimported. The
same-file declaration set is subtracted before the missing-import list is built,
otherwise every private helper in a file is flagged.

PITFALL: a bare identifier scan produces false positives from ordinary English
prose in comments and strings. Only candidates that are (a) declared under the
project prefix elsewhere in the tree, (b) used with a capital letter, and
(c) not declared in the current file are reported -- keep that filter if you
extend this.
"""
import collections
import os
import re
import sys

DECL = re.compile(r'\b(?:class|interface|object|fun|val|var)\s+([A-Za-z_]\w*)')
EXT = re.compile(r'\bfun\s+[A-Za-z_][\w<>., ?]*\.([A-Za-z_]\w*)')
IMPORT = re.compile(r'^\s*import\s+([\w.]+)(?:\s+as\s+\w+)?\s*$')


def collect_definitions(root):
    """Map simple name -> set of (package) declaring it."""
    defined = collections.defaultdict(set)
    pkg_re = re.compile(r'^\s*package\s+([\w.]+)', re.M)
    for dirpath, _, files in os.walk(root):
        for f in sorted(files):
            if not f.endswith('.kt'):
                continue
            fp = os.path.join(dirpath, f)
            with open(fp, encoding='utf-8') as fh:
                text = fh.read()
            m = pkg_re.search(text)
            pkg = m.group(1) if m else ''
            for name in DECL.findall(text) + EXT.findall(text):
                defined[name].add(pkg)
    return defined


def find_dangling(root, prefix, defined):
    """Internal imports naming a symbol nothing in the tree declares."""
    pat = re.compile(r'import\s+(' + re.escape(prefix) + r'[\w.]+)')
    missing = collections.defaultdict(list)
    for dirpath, _, files in os.walk(root):
        for f in sorted(files):
            if not f.endswith('.kt'):
                continue
            fp = os.path.join(dirpath, f)
            with open(fp, encoding='utf-8') as fh:
                for i, line in enumerate(fh, 1):
                    m = pat.match(line.strip())
                    if not m:
                        continue
                    name = m.group(1).split('.')[-1]
                    if name not in defined:
                        missing[name].append('%s:%d' % (os.path.relpath(fp, root), i))
    return missing


def strip_comments_and_strings(text):
    """Remove line comments, block comments and string literals."""
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', ' ', text)
    text = re.sub(r'"""(?:.|\n)*?"""', ' ', text)
    text = re.sub(r'"(?:\\.|[^"\\\n])*"', ' ', text)
    return text


def find_unimported(root, prefix, defined):
    """Project symbols used in a file that never imported them."""
    # A symbol counts as project-local when some file DECLARING it declares a
    # package under the prefix. Compare the declared package, not the file path
    # -- directory layout and package name rarely match.
    proj = {n for n, pkgs in defined.items() if any(p.startswith(prefix) for p in pkgs)}
    offenders = collections.defaultdict(list)
    for dirpath, _, files in os.walk(root):
        for f in sorted(files):
            if not f.endswith('.kt'):
                continue
            fp = os.path.join(dirpath, f)
            with open(fp, encoding='utf-8') as fh:
                raw = fh.read()
            code = strip_comments_and_strings(raw)
            if not prefix in raw:
                continue  # no imports from this project at all
            own = set(DECL.findall(code)) | set(EXT.findall(code))
            imported = set()
            for m in IMPORT.finditer(raw):
                imported.add(m.group(1).split('.')[-1])
            for name in sorted(proj - own - imported):
                # Capitalised identifiers only: prose is lowercase.
                if not name[:1].isupper():
                    continue
                if not re.search(r'\b' + re.escape(name) + r'\b', code):
                    continue
                line = next(
                    (i for i, l in enumerate(code.split('\n'), 1)
                     if re.search(r'\b' + re.escape(name) + r'\b', l)),
                    0,
                )
                offenders[name].append('%s:%d' % (os.path.relpath(fp, root), line))
    return offenders


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    root, prefix = sys.argv[1], sys.argv[2]
    defined = collect_definitions(root)
    bad = False

    dangling = find_dangling(root, prefix, defined)
    if dangling:
        bad = True
        print('DANGLING INTERNAL IMPORTS (no definition found):')
        for name in sorted(dangling):
            print('  %s  <- %s' % (name, dangling[name][0]))
            for extra in dangling[name][1:4]:
                print('       %s' % extra)
        print('\nDefine the symbol, or the compiler will fail on every use site.\n')

    unimported = find_unimported(root, prefix, defined)
    if unimported:
        bad = True
        print('USED BUT NEVER IMPORTED (declared elsewhere in the project):')
        for name in sorted(unimported):
            hits = unimported[name]
            print('  %s  <- %s  (%d site%s)'
                  % (name, hits[0], len(hits), '' if len(hits) == 1 else 's'))
            for extra in hits[1:4]:
                print('       %s' % extra)
        print('\nAdd the import. A type from another package needs one even when '
              'the file reads as if it were local.\n')

    if bad:
        return 1
    print('OK: internal imports resolve and project symbols are imported.')
    return 0


if __name__ == '__main__':
    sys.exit(main())