#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${ROOT_DIR}/services/ai-server"
VENV_DIR="${AI_SERVER_MODEL_VENV_DIR:-${SERVICE_DIR}/.venv-yolo}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"${PYTHON_BIN}" -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip wheel
"${VENV_DIR}/bin/python" -m pip install -r "${SERVICE_DIR}/requirements-model.txt"

cat <<MSG
AI Server model env ready: ${VENV_DIR}
Run with:
  AI_SERVER_VENV_DIR=${VENV_DIR} \\
  AI_SERVER_HOST=0.0.0.0 \\
  AI_SERVER_PORT=8100 \\
  VISION_MODEL_WORKER_ENABLED=true \\
  VISION_MODEL_PATH=yolov8n.pt \\
  VISION_MODEL_TASK=detect \\
  VISION_MODEL_CLASS_MAP_JSON='{"bottle":"box","person":"person"}' \\
  ./scripts/run_ai_server.sh
MSG
