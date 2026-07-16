#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${SMARTFACTORY_REPO_URL:-https://github.com/hasemu1211/SmartFactory.git}"
REPO_DIR="${SMARTFACTORY_REPO_DIR:-${HOME}/SmartFactory}"
GIT_REF="${SMARTFACTORY_GIT_REF:-feature/ai-server-marker-detection}"
SETUP_ARGS=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--repo-url URL] [--repo-dir DIR] [--git-ref REF] [--] [setup args...]

Clone or update the SmartFactory repo, then run:
  scripts/setup/setup_ubuntu24_ai_vision_laptop.sh [setup args...]

Examples:
  $(basename "$0") -- --with-gopro --with-model
  $(basename "$0") --repo-dir ~/SmartFactory --git-ref feature/ai-server-marker-detection -- --install-system --with-ros --with-cuda --with-gopro --with-model
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --repo-url) REPO_URL="$2"; shift 2 ;;
    --repo-dir) REPO_DIR="$2"; shift 2 ;;
    --git-ref) GIT_REF="$2"; shift 2 ;;
    --) shift; SETUP_ARGS=("$@"); break ;;
    *) SETUP_ARGS+=("$1"); shift ;;
  esac
done

if ! command -v git >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y git ca-certificates
  else
    echo "ERROR: git is required" >&2
    exit 1
  fi
fi

if [ ! -d "${REPO_DIR}/.git" ]; then
  mkdir -p "$(dirname "${REPO_DIR}")"
  git clone "${REPO_URL}" "${REPO_DIR}"
fi

cd "${REPO_DIR}"
git fetch --all --prune
git checkout "${GIT_REF}"
git pull --ff-only || {
  echo "WARN: git pull --ff-only failed. If ${GIT_REF} is a detached SHA or local branch, continuing with checked-out files." >&2
}

exec ./scripts/setup/setup_ubuntu24_ai_vision_laptop.sh --git-pull "${SETUP_ARGS[@]}"
