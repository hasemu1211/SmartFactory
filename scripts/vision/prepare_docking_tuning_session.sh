#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SESSION_ROOT="$ROOT_DIR/.omx/reports/docking-tuning"
CONFIG_TEMPLATE="$ROOT_DIR/config/perception/docking_tuning.example.yaml"
IMAGE_TOPIC="${IMAGE_TOPIC:-/camera/image_raw/compressed}"
RAW_TOPIC="${RAW_TOPIC:-/camera/image_raw}"
HZ_DURATION_S="${HZ_DURATION_S:-10}"
MODE="prepare"

usage() {
  cat <<USAGE
Usage: $0 [--print-commands] [--passive-check]

Creates a timestamped docking tuning session folder and copies the config template.

Options:
  --print-commands  Print safe passive ROS commands for the managed ROS CLI pane.
  --passive-check   Run safe passive ROS topic checks. Does not publish /cmd_vel.

Environment overrides:
  IMAGE_TOPIC       Default: /camera/image_raw/compressed
  RAW_TOPIC         Default: /camera/image_raw
  HZ_DURATION_S     Default: 10
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --print-commands)
      MODE="print"
      shift
      ;;
    --passive-check)
      MODE="passive"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$SESSION_ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
SESSION_DIR="$SESSION_ROOT/$STAMP"
mkdir -p "$SESSION_DIR"

if [[ ! -f "$CONFIG_TEMPLATE" ]]; then
  echo "Missing config template: $CONFIG_TEMPLATE" >&2
  exit 1
fi
cp "$CONFIG_TEMPLATE" "$SESSION_DIR/docking_tuning.yaml"

cat > "$SESSION_DIR/README.md" <<README
# Docking tuning session $STAMP

Mode prepared by: scripts/vision/prepare_docking_tuning_session.sh

Safety default: passive only; do not publish /cmd_vel without explicit user permission.

Config copy:
- docking_tuning.yaml

Recommended logs to save here:
- topic-list.txt
- image-topic-type.txt
- compressed-hz.txt
- raw-hz.txt
- marker-pose-jitter.csv
- notes.md
README

echo "Prepared docking tuning session: $SESSION_DIR"
echo "Copied config: $SESSION_DIR/docking_tuning.yaml"

print_commands() {
  cat <<COMMANDS

# Safe passive ROS commands for the managed ROS CLI pane only:
cd "$ROOT_DIR"
ros2 topic list | tee "$SESSION_DIR/topic-list.txt"
ros2 topic type "$IMAGE_TOPIC" | tee "$SESSION_DIR/image-topic-type.txt"
timeout ${HZ_DURATION_S}s ros2 topic hz "$IMAGE_TOPIC" | tee "$SESSION_DIR/compressed-hz.txt"
timeout ${HZ_DURATION_S}s ros2 topic hz "$RAW_TOPIC" | tee "$SESSION_DIR/raw-hz.txt"

# Robot camera launch, only when allowed/needed on robot SSH pane:
ros2 launch turtlebot3_bringup camera.launch.py
COMMANDS
}

if [[ "$MODE" == "print" || "$MODE" == "prepare" ]]; then
  print_commands
fi

if [[ "$MODE" == "passive" ]]; then
  if ! command -v ros2 >/dev/null 2>&1; then
    echo "ros2 command not found. Run from a ROS2-enabled direnv shell/pane." >&2
    exit 1
  fi
  echo "Running passive checks only. No /cmd_vel publishing."
  ros2 topic list | tee "$SESSION_DIR/topic-list.txt"
  ros2 topic type "$IMAGE_TOPIC" | tee "$SESSION_DIR/image-topic-type.txt" || true
  timeout "${HZ_DURATION_S}s" ros2 topic hz "$IMAGE_TOPIC" | tee "$SESSION_DIR/compressed-hz.txt" || true
  timeout "${HZ_DURATION_S}s" ros2 topic hz "$RAW_TOPIC" | tee "$SESSION_DIR/raw-hz.txt" || true
fi
