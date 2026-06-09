#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${ROOT_DIR}/services/ai-server"
VENV_DIR="${SERVICE_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Keep AI Server Python isolated from a sourced ROS2 shell.
unset PYTHONPATH
export PYTHONNOUSERSITE=1

if [ ! -d "${VENV_DIR}" ]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
"${VENV_DIR}/bin/python" -m pip install -r "${SERVICE_DIR}/requirements-dev.txt"
"${VENV_DIR}/bin/python" -m pip freeze --exclude-editable > "${SERVICE_DIR}/requirements.lock"

cat <<MSG
AI Server environment ready.

Activate:
  source ${VENV_DIR}/bin/activate

Run:
  cd ${SERVICE_DIR}
  uvicorn app.main:app --host 127.0.0.1 --port 8100 --reload

Test:
  ./scripts/test_ai_server.sh
MSG
