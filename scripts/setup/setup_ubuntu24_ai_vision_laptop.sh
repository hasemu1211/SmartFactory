#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVICE_DIR="${ROOT_DIR}/services/ai-server"
ROS_DISTRO="${ROS_DISTRO:-jazzy}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

WITH_SYSTEM=false
WITH_ROS=false
WITH_CUDA=false
WITH_GOPRO=false
WITH_MODEL=false
DRY_RUN=false
GIT_PULL=false
PACK_VENV=false

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--install-system] [--with-ros] [--with-cuda] [--with-gopro] [--with-model] [--git-pull] [--pack-venv] [--dry-run]

Prepare a Ubuntu 24.04 AI/Vision laptop to run the SmartFactory AI Server
and GoPro global-camera adapter.

Default behavior is intentionally project-local only:
  - create/update services/ai-server/.venv
  - install AI Server Python requirements
  - print verification commands

System-level installation is opt-in:
  --install-system  install common apt packages
  --with-ros        install ROS 2 Jazzy deb packages (requires --install-system)
  --with-cuda       install NVIDIA driver + CUDA toolkit via Ubuntu packages (requires --install-system)
  --with-gopro      install OpenGoPro optional Python deps
  --with-model      install Ultralytics/PyTorch model deps into the AI Server venv
  --git-pull        update the current repo with git pull --ff-only before setup
  --pack-venv       create a best-effort .venv tarball after setup (recreate from requirements is preferred)
  --dry-run         print commands without executing them
USAGE
}

run() {
  if [ "${DRY_RUN}" = "true" ]; then
    printf '[dry-run] %q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

require_ubuntu24() {
  if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    if [ "${ID:-}" != "ubuntu" ] || [ "${VERSION_ID:-}" != "24.04" ]; then
      echo "WARN: expected Ubuntu 24.04, found ${PRETTY_NAME:-unknown}; continuing because this script is operator-invoked." >&2
    fi
  fi
}

update_repo() {
  if [ ! -d "${ROOT_DIR}/.git" ]; then
    echo "WARN: ${ROOT_DIR} is not a git checkout; skipping --git-pull" >&2
    return 0
  fi
  run git -C "${ROOT_DIR}" pull --ff-only
}

install_system_packages() {
  run sudo apt-get update
  run sudo apt-get install -y \
    ca-certificates curl gnupg lsb-release software-properties-common \
    git build-essential cmake pkg-config \
    python3 python3-dev python3-pip python3-venv \
    ffmpeg v4l-utils usbutils net-tools iproute2 avahi-daemon \
    libgl1 libglib2.0-0
}

install_ros_jazzy() {
  if [ ! -f /etc/apt/sources.list.d/ros2.list ]; then
    run sudo install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/ros-archive-keyring.gpg ]; then
      run bash -c "curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | sudo gpg --dearmor -o /etc/apt/keyrings/ros-archive-keyring.gpg"
    fi
    run bash -c "echo 'deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main' | sudo tee /etc/apt/sources.list.d/ros2.list >/dev/null"
  fi
  run sudo apt-get update
  run sudo apt-get install -y ros-dev-tools "ros-${ROS_DISTRO}-desktop"
}

install_cuda_stack() {
  echo "INFO: installing Ubuntu-packaged NVIDIA driver/CUDA. For exact CUDA pinning, use NVIDIA's current CUDA network repo package for Ubuntu 24.04."
  run sudo apt-get install -y ubuntu-drivers-common
  if command -v ubuntu-drivers >/dev/null 2>&1; then
    run sudo ubuntu-drivers install
  fi
  run sudo apt-get install -y nvidia-cuda-toolkit
}

setup_python_env() {
  run "${ROOT_DIR}/scripts/ai/setup_ai_server_env.sh"
  if [ "${WITH_MODEL}" = "true" ]; then
    run "${SERVICE_DIR}/.venv/bin/python" -m pip install -r "${SERVICE_DIR}/requirements-model.txt"
  fi
  if [ "${WITH_GOPRO}" = "true" ]; then
    run "${SERVICE_DIR}/.venv/bin/python" -m pip install -r "${SERVICE_DIR}/requirements-gopro.txt"
  fi
  run "${SERVICE_DIR}/.venv/bin/python" -m pip freeze --exclude-editable
  if [ "${DRY_RUN}" = "false" ]; then
    "${SERVICE_DIR}/.venv/bin/python" -m pip freeze --exclude-editable > "${SERVICE_DIR}/requirements.local.lock"
  fi
}

pack_venv() {
  local archive_dir archive_path manifest_path
  archive_dir="${ROOT_DIR}/dist"
  archive_path="${archive_dir}/ai-server-venv-ubuntu24-$(date +%Y%m%d%H%M%S).tar.gz"
  manifest_path="${archive_dir}/ai-server-env-manifest-$(date +%Y%m%d%H%M%S).txt"
  run mkdir -p "${archive_dir}"
  if [ "${DRY_RUN}" = "false" ]; then
    {
      echo "created_at=$(date --iso-8601=seconds)"
      echo "repo=$(git -C "${ROOT_DIR}" rev-parse --show-toplevel 2>/dev/null || true)"
      echo "git_branch=$(git -C "${ROOT_DIR}" branch --show-current 2>/dev/null || true)"
      echo "git_commit=$(git -C "${ROOT_DIR}" rev-parse HEAD 2>/dev/null || true)"
      echo "python=$("${SERVICE_DIR}/.venv/bin/python" --version 2>&1)"
      echo "pip_freeze=${SERVICE_DIR}/requirements.local.lock"
      command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
      command -v ros2 >/dev/null 2>&1 && ros2 doctor --report || true
    } > "${manifest_path}"
  else
    run touch "${manifest_path}"
  fi
  # Venv archives are not the primary migration path because activation scripts
  # and compiled wheels can embed machine paths. This is for same-OS emergency
  # transfer only; requirements.local.lock remains the reproducible path.
  run tar -C "${SERVICE_DIR}" -czf "${archive_path}" .venv requirements.local.lock
  echo "Best-effort venv archive: ${archive_path}"
  echo "Environment manifest: ${manifest_path}"
}

print_next_steps() {
  cat <<MSG

Ubuntu 24.04 AI/Vision laptop setup step complete.

Recommended verification:
  ${SERVICE_DIR}/.venv/bin/python - <<'PY'
import cv2
print('opencv', cv2.__version__)
try:
    import torch
    print('torch', torch.__version__, 'cuda_available', torch.cuda.is_available())
except Exception as exc:
    print('torch check skipped/error:', exc)
PY
  ./scripts/vision/run_gopro_smart_roi_adapter.py --check
  ./scripts/vision/start_gopro_webcam_stream.py --test-read --exit-after-test
  VISION_MODEL_WORKER_ENABLED=false ./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh --check

Run on the map-side AI PC/laptop:
  AI_SERVER_HOST=0.0.0.0 ./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh

Then ingest GoPro/global camera frames, for example:
  ./scripts/vision/start_gopro_webcam_stream.py --test-read
  ./scripts/vision/run_gopro_smart_roi_adapter.py --input 'udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000' --source global_cam_01 --roi-view lift_roi --target-fps 5 --bufferless

If GoPro is exposed as OpenGoPro USB webcam/TS stream instead of /dev/video0,
start the GoPro webcam stream with OpenGoPro tools, then set --input to the
OpenCV-readable stream URL (for example a UDP/RTSP URL provided by that tool).

Headless GoPro USB stream command:
  ./scripts/vision/start_gopro_webcam_stream.py --test-read

Use this input with the ROI adapter:
  ./scripts/vision/run_gopro_smart_roi_adapter.py --input 'udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000' --source global_cam_01 --roi-view lift_roi --target-fps 5 --bufferless

Lift transition evidence example:
  mkdir -p evidence/lift_up evidence/pre_dropoff evidence/transit_roi
  ./scripts/vision/run_gopro_smart_roi_adapter.py --input 'udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000' --source global_cam_01 --roi-view lift_roi --target-fps 3 --max-frames 5 --evaluate-lift-roi --operation PICKUP --save-full-dir evidence/lift_up --save-full-every 1 --save-roi-dir evidence/lift_up --save-every 1 --evidence-label lift_up_proof
  ./scripts/vision/run_gopro_smart_roi_adapter.py --input 'udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000' --source global_cam_01 --roi-view lift_roi --target-fps 5 --evaluate-lift-roi --operation MONITOR --save-roi-dir evidence/transit_roi --save-every 15 --evidence-label transit_drop_watch
MSG
}

main() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --help|-h) usage; exit 0 ;;
      --install-system) WITH_SYSTEM=true ;;
      --with-ros) WITH_ROS=true ;;
      --with-cuda) WITH_CUDA=true ;;
      --with-gopro) WITH_GOPRO=true ;;
      --with-model) WITH_MODEL=true ;;
      --git-pull) GIT_PULL=true ;;
      --pack-venv) PACK_VENV=true ;;
      --dry-run) DRY_RUN=true ;;
      *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
  done

  require_ubuntu24
  if [ "${GIT_PULL}" = "true" ]; then
    update_repo
  fi
  if [ "${WITH_SYSTEM}" = "true" ]; then
    install_system_packages
    if [ "${WITH_ROS}" = "true" ]; then
      install_ros_jazzy
    fi
    if [ "${WITH_CUDA}" = "true" ]; then
      install_cuda_stack
    fi
  elif [ "${WITH_ROS}" = "true" ] || [ "${WITH_CUDA}" = "true" ]; then
    echo "ERROR: --with-ros/--with-cuda require --install-system" >&2
    exit 2
  fi

  setup_python_env
  if [ "${PACK_VENV}" = "true" ]; then
    pack_venv
  fi
  print_next_steps
}

main "$@"
