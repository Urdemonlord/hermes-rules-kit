#!/usr/bin/env bash
# Cut a release: bump the version, tag it, build, and prove the artifact.
#
# Copy into the project root, set NAME to the tarball's basename, and adjust
# the changelog path. Every refusal below corresponds to a way a release can
# ship something nobody can identify afterwards.
#
# Usage:  ./release.sh 0.2.0
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

NAME="meowpay-panel"      # tarball basename, without version
CHANGELOG="CHANGELOG.md"

die() { printf '\033[31m[release] %s\033[0m\n' "$*" >&2; exit 1; }
say() { printf '\033[36m[release] %s\033[0m\n' "$*"; }

NEW="${1:-}"
[ -n "$NEW" ] || die "usage: ./release.sh <version>   (e.g. ./release.sh 0.2.0)"
printf '%s' "$NEW" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' \
  || die "version must be plain MAJOR.MINOR.PATCH -- '$NEW' is not"

CUR="$(node -p "require('./package.json').version")"
say "current version $CUR -> $NEW"

# The tag is the release's identity. A second tarball with the same filename is
# the one thing a buyer cannot distinguish after it reaches them.
git rev-parse -q --verify "refs/tags/v$NEW" >/dev/null \
  && die "tag v$NEW already exists -- pick a new version"
git rev-parse -q --verify "refs/tags/v$CUR" >/dev/null \
  || say "note: v$CUR was never tagged"

# An unstaged change is captured by nothing: the tag points at the commit, and
# the commit does not contain it. Ship that and tag and artifact disagree forever.
git diff --quiet && git diff --cached --quiet \
  || die "working tree is dirty -- commit or stash first, or the tag will not match the artifact"

[ -f "$CHANGELOG" ] || die "$CHANGELOG not found -- a buyer who reads only the changelog has to be able to tell what changed"
grep -qE "^## \[v?$NEW\]" "$CHANGELOG" \
  || die "$CHANGELOG has no entry for $NEW"

# Bump BEFORE the build: the build reads package.json for both the tarball name
# and the version the installer will write into the install directory.
node -e "
const fs = require('fs'), f = 'package.json'
const p = JSON.parse(fs.readFileSync(f, 'utf8'))
p.version = '$NEW'
fs.writeFileSync(f, JSON.stringify(p, null, 2) + '\n')
"
say "package.json -> $NEW"

bash build-pkg.sh "$NEW"          # also the leak gate; make it refuse loudly

# Read the version back OUT of the artifact. A build that names the file after
# its argument would otherwise succeed and tag 0.2.0 over a 0.1.0 archive.
TARBALL="dist/$NAME-$NEW.tar.gz"
[ -f "$TARBALL" ] || die "build produced no $TARBALL"
tar tzf "$TARBALL" >/dev/null || die "$TARBALL is not a readable archive"
tar xzOf "$TARBALL" "$NAME/package.json" | node -e "
let s = ''; process.stdin.on('data', d => s += d).on('end', () => {
  const v = JSON.parse(s).version
  if (v !== '$NEW') { console.error('[release] artifact says ' + v + ', expected $NEW'); process.exit(1) }
  console.log('[release] artifact package.json version:', v)
})
" || die "the artifact does not carry version $NEW"

git add package.json "$CHANGELOG"
git commit -m "Release $NEW" >/dev/null
git tag -a "v$NEW" -m "$NAME $NEW"
say "tagged v$NEW -> $(git rev-parse --short HEAD)"
say "upload $TARBALL as the release asset, then: git push --follow-tags"