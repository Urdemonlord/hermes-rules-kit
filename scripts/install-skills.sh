#!/usr/bin/env bash
# Install a preset of skills into an agent skills directory.
# Copies only. Never deletes. Skips existing directories unless --force.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST="${SKILLS_DEST:-$HOME/.hermes/skills}"
PRESET=""
FORCE=0
DRY=0

usage() {
  cat <<'EOF'
Usage: scripts/install-skills.sh <preset> [options]

Options:
  --dest DIR   target skills directory (default $SKILLS_DEST or ~/.hermes/skills)
  --force      overwrite skill directories that already exist
  --dry-run    print the plan, copy nothing
  --list       list available presets
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DEST="$2"; shift 2;;
    --force) FORCE=1; shift;;
    --dry-run) DRY=1; shift;;
    --list)
      for f in "$ROOT"/presets/*.list; do
        n=$(basename "$f" .list)
        printf '%-16s %s skills\n' "$n" "$(grep -vcE '^\s*(#|$)' "$f")"
      done
      exit 0;;
    -h|--help) usage; exit 0;;
    -*) echo "unknown option: $1" >&2; usage; exit 2;;
    *) PRESET="$1"; shift;;
  esac
done

[ -n "$PRESET" ] || { usage; exit 2; }
LIST="$ROOT/presets/$PRESET.list"
[ -f "$LIST" ] || { echo "no such preset: $PRESET" >&2; echo "try --list" >&2; exit 2; }

mapfile -t NAMES < <(grep -vE '^\s*(#|$)' "$LIST" | tr -d '[:blank:]\r')

missing=()
for n in "${NAMES[@]}"; do
  [ -d "$ROOT/skills/$n" ] || missing+=("$n")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "preset references skills that are not in this repo:" >&2
  printf '  %s\n' "${missing[@]}" >&2
  exit 1
fi

[ "$DRY" = 1 ] || mkdir -p "$DEST"
copied=0; skipped=0; forced=0
manifest="$DEST/.installed-$PRESET"

for n in "${NAMES[@]}"; do
  src="$ROOT/skills/$n"; dst="$DEST/$n"
  if [ -d "$dst" ] && [ "$FORCE" = 0 ]; then
    echo "skip    $n (already installed; --force to overwrite)"
    skipped=$((skipped+1)); continue
  fi
  if [ -d "$dst" ]; then
    [ "$DRY" = 1 ] || rm -rf "$dst"
    forced=$((forced+1))
  fi
  if [ "$DRY" = 1 ]; then
    echo "would copy $n"
  else
    cp -r "$src" "$dst"
    echo "copied  $n"
  fi
  copied=$((copied+1))
done

if [ "$DRY" = 0 ]; then
  : > "$manifest"
  for n in "${NAMES[@]}"; do
    if [ -f "$DEST/$n/SKILL.md" ]; then
      printf '%s\t%s\n' "$n" "$(sha256sum "$DEST/$n/SKILL.md" | cut -d' ' -f1)" >> "$manifest"
    fi
  done
  echo
  echo "preset '$PRESET': $copied copied, $skipped skipped, $forced overwritten"
  echo "manifest: $manifest"
  echo "next: start a session and ask the agent to list its skills"
else
  echo
  echo "dry run: $copied would be copied, $skipped skipped (target $DEST)"
fi
