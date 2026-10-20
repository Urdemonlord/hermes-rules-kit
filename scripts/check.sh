#!/usr/bin/env bash
# Repo self-check: the rules this repo sells must hold in this repo.
# Run from repo root. Exit 1 on any violation.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
fail=0
err() { echo "FAIL: $*"; fail=1; }

# 1. every skill frontmatter name matches its directory
for f in skills/*/SKILL.md; do
  dir=$(basename "$(dirname "$f")")
  name=$(sed -n '2s/^name: *//p' "$f")
  [ "$name" = "$dir" ] || err "$f declares name '$name', dir is '$dir'"
done

# 2. closeout shape: one list of labels, used by template and examples
labels="changed verified unverified blocked assumption"
check_labels() {
  for l in $labels; do
    grep -qE "(^##+ +$l\b|^[[:space:]]*[-*][[:space:]]*\*\*$l\*\*)" "$1" || err "$1 missing closeout label '$l'"
  done
}
check_labels templates/closeout-template.md
check_labels examples/verification-closeout.md
check_labels examples/debugging-closeout.md
check_labels skills/hermes-agentic-coding-20-80/SKILL.md

# 3. README version claims agree with each other
badge=$(grep -oE 'status-v[0-9]+\.[0-9]+\.[0-9]+' README.md | head -1 | sed 's/status-//')
rel=$(sed -n '/^## Release/,/^## /p' README.md | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1)
[ -n "$badge" ] && [ "$badge" = "$rel" ] || err "README badge '$badge' != release section '$rel'"

# 4. derived copies must name the canonical file
for f in templates/AGENTS.template.md templates/paste-into-your-agent.md skills/hermes-agentic-coding-20-80/SKILL.md; do
  grep -q 'core-runtime-law.md' "$f" || err "$f does not name docs/core-runtime-law.md as canonical"
done

# 5. relative markdown links resolve; no dangling references/ links
while IFS='|' read -r src target; do
  [ -e "$(dirname "$src")/$target" ] || err "$src links to missing '$target'"
done < <(grep -rHoE '\]\([^)#]+\.md[^)]*\)' --include='*.md' . \
  | sed 's/:](\(.*\))$/|\1/' | sed 's/\.md#.*|/.md|/' | grep -v '^\./\.git')

# 6. skills here must not ship project-specific reference files they cannot prove
grep -rHoE 'references/[A-Za-z0-9._-]+' --include='SKILL.md' skills/ | while IFS=: read -r f ref; do
  [ -e "$(dirname "$f")/$ref" ] || echo "WARN: $f links to unfiled $ref"
done

[ $fail -eq 0 ] && echo "OK: checks passed"
exit $fail
