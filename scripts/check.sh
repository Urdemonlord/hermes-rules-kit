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
  name=$(awk 'NR==1&&/^---/{f=1;next} f&&/^name:/{sub(/^name: */,"");print;exit} f&&/^---/{exit}' "$f")
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

# 5. relative markdown links resolve; absolute URLs are skipped
while IFS='|' read -r src target; do
  case "$target" in http://*|https://*|mailto:*|"#"*) continue;; esac
  case "$target" in *.md) ;; *) continue;; esac
  case "$target" in *[!A-Za-z0-9._/-]*) continue;; esac
  [ -e "$(dirname "$src")/$target" ] || err "$src links to missing '$target'"
done < <(grep -rHoE '\]\([^)]+\)' --include='*.md' . \
  | sed 's/\.md#.*)/.md)/' | sed 's/:](\(.*\))$/|\1/' | grep -v '/\.git/')

# 6. skills here must not ship project-specific reference files they cannot prove
grep -rHoE 'references/[A-Za-z0-9._-]+\.(md|sh|py)' --include='SKILL.md' skills/ | while IFS=: read -r f ref; do
  [ -e "$(dirname "$f")/$ref" ] || echo "WARN: $f links to unfiled $ref"
done

# 7. no credentials, personal data, or local paths in published text
scan() { # $1 = regex, $2 = description, $3 = extra exclusions
  local out extra="${3-}"
  out=$(grep -rInP "$1" --include='*.md' --include='*.sh' --include='*.yaml' --include='*.json' --include='*.html' . 2>/dev/null \
    | grep -v '^\./scripts/check\.sh' | grep -v '/\.git/' | grep -v '^\./\.ops-boundary\.md')
  [ -z "$extra" ] || out=$(printf '%s\n' "$out" | grep -vE "$extra")
  [ -z "$out" ] || { echo "$out" | head -5; err "found $2"; }
}
scan '(?<![A-Za-z0-9._-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' "email address" 'user@example\.com'
scan '/home/meowlabs' "operator home path"
scan '\b(sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16})\b' "API token"
scan '(?i)\b(TOKEN|API_KEY|SECRET|PASSWORD)\s*=\s*[^\s`<"\x27]+' "inline credential"
scan '([0-9]{1,3}\.){3}[0-9]{1,3}' "IP literal" \
  '127\.0\.0\.1|0\.0\.0\.0|1\.1\.1\.1|8\.8\.8\.8|169\.254\.|203\.0\.113\.|(^|[^0-9])10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.'

# 8. presets only reference skills that exist in this repo
for f in presets/*.list; do
  while IFS= read -r n; do
    case "$n" in ""|\#*) continue;; esac
    [ -d "skills/$n" ] || err "$f references missing skill '$n'"
  done < "$f"
done

[ $fail -eq 0 ] && echo "OK: checks passed"
exit $fail
