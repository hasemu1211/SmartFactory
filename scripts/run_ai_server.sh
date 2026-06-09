#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${ROOT_DIR}/services/ai-server"
VENV_DIR="${SERVICE_DIR}/.venv"

if [ ! -x "${VENV_DIR}/bin/uvicorn" ]; then
  echo "AI Server venv not found. Run ./scripts/setup_ai_server_env.sh first." >&2
  exit 1
fi

# Keep AI Server Python isolated from ROS2 PYTHONPATH if this shell sourced /opt/ros.
unset PYTHONPATH
export PYTHONNOUSERSITE=1

cd "${SERVICE_DIR}"
exec "${VENV_DIR}/bin/uvicorn" app.main:app \
  --host "${AI_SERVER_HOST:-127.0.0.1}" \
  --port "${AI_SERVER_PORT:-8100}" \
  "${@}"
