#!/usr/bin/env bash
# Shared, source-only helpers for SmartFactory Vision bundle entrypoint scripts.
# Keep this file side-effect free: no exports, no process starts, no filesystem mutation.

sf_repo_root_from_script() {
  local script_path="$1"
  local dir
  dir="$(cd "$(dirname "${script_path}")" && pwd)"
  while [ "${dir}" != "/" ]; do
    if [ -d "${dir}/services" ] && [ -d "${dir}/scripts" ]; then
      printf '%s\n' "${dir}"
      return 0
    fi
    dir="$(dirname "${dir}")"
  done
  return 1
}

sf_default_model_extra_pythonpath() {
  printf '%s\n' '/home/codelab/venv/venv/lib/python3.12/site-packages'
}

sf_is_private_ipv4() {
  local ip="${1:-}"
  [[ "${ip}" =~ ^10\. ]] \
    || [[ "${ip}" =~ ^192\.168\. ]] \
    || [[ "${ip}" =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\. ]]
}

sf_route_source_ip() {
  local target="${1:-}"
  [ -n "${target}" ] || return 1
  command -v ip >/dev/null 2>&1 || return 1
  ip route get "${target}" 2>/dev/null | awk '
    {
      for (i = 1; i <= NF; i++) {
        if ($i == "src" && (i + 1) <= NF) {
          print $(i + 1)
          exit
        }
      }
    }'
}

sf_lan_ip() {
  local route_target="${1:-}"
  local routed=""
  if [ -n "${route_target}" ]; then
    routed="$(sf_route_source_ip "${route_target}" || true)"
    if sf_is_private_ipv4 "${routed}"; then
      printf '%s\n' "${routed}"
      return 0
    fi
  fi
  hostname -I 2>/dev/null | tr ' ' '\n' \
    | grep -E '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' \
    | grep -v '^172\.17\.' \
    | head -n1 || true
}
