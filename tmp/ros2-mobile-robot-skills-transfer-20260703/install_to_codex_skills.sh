#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE="$SCRIPT_DIR/ros2-mobile-robot-skills-20260703.tar.gz"
SHA_FILE="$SCRIPT_DIR/SHA256SUMS"
DEST_ROOT="${CODEX_HOME:-$HOME/.codex}/skills"
EXTRACT_DIR="${TMPDIR:-/tmp}/ros2-mobile-robot-skills-install"

cd "$SCRIPT_DIR"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum -c "$SHA_FILE"
else
  echo "sha256sum not found; skipping checksum validation" >&2
fi

rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR" "$DEST_ROOT"
tar -xzf "$ARCHIVE" -C "$EXTRACT_DIR"

for skill in ros2-engineering-handbook narrow-space-robot-navigation; do
  if [ ! -f "$EXTRACT_DIR/$skill/SKILL.md" ]; then
    echo "missing extracted skill: $skill" >&2
    exit 1
  fi
  rm -rf "$DEST_ROOT/$skill"
  cp -a "$EXTRACT_DIR/$skill" "$DEST_ROOT/"
  echo "installed $skill -> $DEST_ROOT/$skill"
done

VALIDATOR="$DEST_ROOT/.system/skill-creator/scripts/quick_validate.py"
if [ -f "$VALIDATOR" ]; then
  python3 "$VALIDATOR" "$DEST_ROOT/ros2-engineering-handbook"
  python3 "$VALIDATOR" "$DEST_ROOT/narrow-space-robot-navigation"
else
  echo "quick_validate.py not found under $DEST_ROOT/.system; restart Codex/OMX and verify via skill discovery." >&2
fi

echo "Done. Restart Codex/OMX on this machine to refresh available skills."
