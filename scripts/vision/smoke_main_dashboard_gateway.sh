#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT_DIR="${REPORT_DIR:-${ROOT_DIR}/.omx/reports}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_JSON="${REPORT_JSON:-${REPORT_DIR}/main-dashboard-gateway-smoke-${TIMESTAMP}.json}"
REPORT_MD="${REPORT_MD:-${REPORT_DIR}/main-dashboard-gateway-smoke-${TIMESTAMP}.md}"
RESULTS_JSONL="$(mktemp)"

VISION_PUBLIC_HOST="${VISION_PUBLIC_HOST:-smartfactory-vision.local}"
VISION_API_BASE_URL="${VISION_API_BASE_URL:-http://${VISION_PUBLIC_HOST}:8100}"
VISION_STREAM_BASE_URL="${VISION_STREAM_BASE_URL:-${LMS_VISION_STREAM_BASE_URL:-http://${VISION_PUBLIC_HOST}:8090}}"
VISION_API_FALLBACK_BASE_URL="${VISION_API_FALLBACK_BASE_URL:-}"
VISION_STREAM_FALLBACK_BASE_URL="${VISION_STREAM_FALLBACK_BASE_URL:-${LMS_VISION_STREAM_FALLBACK_BASE_URL:-}}"
VISION_SOURCES="${VISION_SOURCES:-tb3_1_picam,tb3_2_picam}"
MAIN_DASHBOARD_URL="${MAIN_DASHBOARD_URL:-}"
MAIN_PROXY_BASE_URL="${MAIN_PROXY_BASE_URL:-}"
CURL_TIMEOUT_SEC="${CURL_TIMEOUT_SEC:-3}"
STREAM_TIMEOUT_SEC="${STREAM_TIMEOUT_SEC:-3}"
SMOKE_STRICT="${SMOKE_STRICT:-false}"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--help]

Report-only Main/Vision endpoint smoke check.

Environment:
  VISION_PUBLIC_HOST                 default: smartfactory-vision.local
  VISION_API_BASE_URL                default: http://\${VISION_PUBLIC_HOST}:8100
  VISION_STREAM_BASE_URL             default: http://\${VISION_PUBLIC_HOST}:8090
  VISION_API_FALLBACK_BASE_URL       optional explicit fallback; never inferred
  VISION_STREAM_FALLBACK_BASE_URL    optional explicit fallback; never inferred
  MAIN_DASHBOARD_URL                 optional dashboard URL, e.g. http://<main>:8088/dashboard/overview
  MAIN_PROXY_BASE_URL                optional Main origin; derived from MAIN_DASHBOARD_URL when omitted
  VISION_SOURCES                     comma-separated sources; default tb3_1_picam,tb3_2_picam
  SMOKE_STRICT                       true exits non-zero on failed checks; default false

This script records hostname resolution, Vision health/status, explicit fallback
health/status, and optional Main dashboard/proxy evidence to .omx/reports.
It does not mutate IP, DNS, hosts, ROS, robot motion, or Main configuration.
USAGE
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi
if [ -n "${1:-}" ]; then
  echo "ERROR: unknown argument: $1" >&2
  usage >&2
  exit 2
fi

mkdir -p "${REPORT_DIR}"

if [ -z "${MAIN_PROXY_BASE_URL}" ] && [ -n "${MAIN_DASHBOARD_URL}" ]; then
  MAIN_PROXY_BASE_URL="$(printf '%s\n' "${MAIN_DASHBOARD_URL}" | sed -E 's#^(https?://[^/]+).*#\1#')"
fi

append_record() {
  local name="$1"
  local kind="$2"
  local url="$3"
  local ok="$4"
  local status_code="$5"
  local curl_exit="$6"
  local detail="$7"
  python3 - "${RESULTS_JSONL}" "${name}" "${kind}" "${url}" "${ok}" "${status_code}" "${curl_exit}" "${detail}" <<'PY'
import json
import sys
path, name, kind, url, ok, status_code, curl_exit, detail = sys.argv[1:]
record = {
    "name": name,
    "kind": kind,
    "url": url or None,
    "ok": ok.lower() == "true",
    "status_code": int(status_code) if status_code.isdigit() else None,
    "curl_exit": int(curl_exit) if curl_exit.isdigit() else None,
    "detail": detail,
}
with open(path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
PY
}

http_ok() {
  local status_code="$1"
  [[ "${status_code}" =~ ^[0-9][0-9][0-9]$ ]] && [ "${status_code}" -ge 200 ] && [ "${status_code}" -lt 400 ]
}

probe_http() {
  local name="$1"
  local url="$2"
  local mode="${3:-http}"
  local timeout="${CURL_TIMEOUT_SEC}"
  if [ "${mode}" = "stream" ]; then
    timeout="${STREAM_TIMEOUT_SEC}"
  fi

  local headers body err status_code curl_exit content_type detail ok
  headers="$(mktemp)"
  body="$(mktemp)"
  err="$(mktemp)"
  curl_exit=0
  set +e
  status_code="$(curl -sS -L --max-time "${timeout}" -o "${body}" -D "${headers}" -w '%{http_code}' "${url}" 2>"${err}")"
  curl_exit=$?
  set -e
  content_type="$(grep -i '^content-type:' "${headers}" | tail -n1 | tr -d '\r' || true)"
  detail="${content_type:-$(tr '\n' ' ' <"${err}" | sed 's/[[:space:]]\+/ /g' | cut -c1-220)}"
  ok=false
  if [ "${mode}" = "stream" ]; then
    # Long-lived MJPEG streams commonly end by curl max-time after headers.
    if http_ok "${status_code}" && { [ "${curl_exit}" -eq 0 ] || [ "${curl_exit}" -eq 28 ]; }; then
      ok=true
    fi
  elif http_ok "${status_code}" && [ "${curl_exit}" -eq 0 ]; then
    ok=true
  fi
  append_record "${name}" "${mode}" "${url}" "${ok}" "${status_code}" "${curl_exit}" "${detail}"
  rm -f "${headers}" "${body}" "${err}"
}

resolve_host() {
  local host="$1"
  local out err ok detail exit_code
  out="$(mktemp)"
  err="$(mktemp)"
  exit_code=0
  set +e
  getent hosts "${host}" >"${out}" 2>"${err}"
  exit_code=$?
  set -e
  ok=false
  if [ "${exit_code}" -eq 0 ] && [ -s "${out}" ]; then
    ok=true
    detail="$(head -n1 "${out}" | tr '\t' ' ' | sed 's/[[:space:]]\+/ /g')"
  else
    detail="hostname_unresolved $(tr '\n' ' ' <"${err}" | sed 's/[[:space:]]\+/ /g')"
  fi
  append_record "vision_public_host_resolution" "dns" "${host}" "${ok}" "" "${exit_code}" "${detail}"
  rm -f "${out}" "${err}"
}

probe_vision_candidate() {
  local label="$1"
  local api_base="$2"
  local stream_base="$3"
  [ -n "${api_base}" ] && probe_http "vision_api_${label}_health" "${api_base%/}/api/v1/health" "http"
  [ -n "${stream_base}" ] && probe_http "vision_stream_${label}_status" "${stream_base%/}/api/v1/vision/bridge/status" "http"
}

probe_main_proxy() {
  local proxy_base="$1"
  [ -n "${proxy_base}" ] || return 0
  probe_http "main_proxy_bridge_status" "${proxy_base%/}/api/v1/vision/bridge/status" "http"

  local IFS=','
  local source
  for source in ${VISION_SOURCES}; do
    source="$(printf '%s' "${source}" | xargs)"
    [ -n "${source}" ] || continue
    probe_http "main_proxy_overlay_stream_${source}" "${proxy_base%/}/api/v1/vision/overlay/stream?source=${source}&max_fps=2" "stream"
  done
}

resolve_host "${VISION_PUBLIC_HOST}"
probe_vision_candidate "primary" "${VISION_API_BASE_URL}" "${VISION_STREAM_BASE_URL}"
if [ -n "${VISION_API_FALLBACK_BASE_URL}" ] || [ -n "${VISION_STREAM_FALLBACK_BASE_URL}" ]; then
  probe_vision_candidate "explicit_fallback" "${VISION_API_FALLBACK_BASE_URL}" "${VISION_STREAM_FALLBACK_BASE_URL}"
else
  append_record "vision_explicit_fallback_config" "config" "" "true" "" "" "not_configured; detected LAN IP is evidence only"
fi

if [ -n "${MAIN_DASHBOARD_URL}" ]; then
  probe_http "main_dashboard" "${MAIN_DASHBOARD_URL}" "http"
else
  append_record "main_dashboard" "http" "" "true" "" "" "skipped; MAIN_DASHBOARD_URL not set"
fi
probe_main_proxy "${MAIN_PROXY_BASE_URL}"

fail_count="$(python3 - "${RESULTS_JSONL}" "${REPORT_JSON}" "${REPORT_MD}" \
  "${VISION_PUBLIC_HOST}" "${VISION_API_BASE_URL}" "${VISION_STREAM_BASE_URL}" \
  "${VISION_API_FALLBACK_BASE_URL}" "${VISION_STREAM_FALLBACK_BASE_URL}" \
  "${MAIN_DASHBOARD_URL}" "${MAIN_PROXY_BASE_URL}" "${VISION_SOURCES}" "${SMOKE_STRICT}" <<'PY'
import json
import sys
from datetime import datetime, timezone
(
    jsonl_path,
    report_json,
    report_md,
    public_host,
    api_base,
    stream_base,
    api_fallback,
    stream_fallback,
    dashboard_url,
    proxy_base,
    sources,
    strict,
) = sys.argv[1:]
records = []
with open(jsonl_path, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line:
            records.append(json.loads(line))
failures = [r for r in records if not r.get("ok")]
report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "strict": strict.lower() == "true",
    "config": {
        "vision_public_host": public_host,
        "vision_api_base_url": api_base,
        "vision_stream_base_url": stream_base,
        "vision_api_fallback_base_url": api_fallback or None,
        "vision_stream_fallback_base_url": stream_fallback or None,
        "main_dashboard_url": dashboard_url or None,
        "main_proxy_base_url": proxy_base or None,
        "vision_sources": [s.strip() for s in sources.split(",") if s.strip()],
    },
    "summary": {
        "check_count": len(records),
        "failure_count": len(failures),
        "failed_checks": [r["name"] for r in failures],
    },
    "results": records,
}
with open(report_json, "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=2)
with open(report_md, "w", encoding="utf-8") as fh:
    fh.write("# Main Dashboard / Vision Gateway Smoke Report\n\n")
    fh.write(f"- generated_at: {report['generated_at']}\n")
    fh.write(f"- strict: {report['strict']}\n")
    fh.write(f"- vision_public_host: `{public_host}`\n")
    fh.write(f"- vision_api_base_url: `{api_base}`\n")
    fh.write(f"- vision_stream_base_url: `{stream_base}`\n")
    fh.write(f"- vision_api_fallback_base_url: `{api_fallback or 'not configured'}`\n")
    fh.write(f"- vision_stream_fallback_base_url: `{stream_fallback or 'not configured'}`\n")
    fh.write(f"- main_dashboard_url: `{dashboard_url or 'not set'}`\n")
    fh.write(f"- main_proxy_base_url: `{proxy_base or 'not set'}`\n")
    fh.write("\n## Results\n\n")
    fh.write("| Check | OK | Status | Curl exit | Detail | URL |\n")
    fh.write("|---|---:|---:|---:|---|---|\n")
    for r in records:
        detail = (r.get("detail") or "").replace("|", "\\|")
        url = r.get("url") or ""
        fh.write(
            f"| `{r['name']}` | {str(r['ok']).lower()} | "
            f"{r.get('status_code') or ''} | {r.get('curl_exit') if r.get('curl_exit') is not None else ''} | "
            f"{detail} | `{url}` |\n"
        )
    if failures:
        fh.write("\n## Failed checks\n\n")
        for r in failures:
            fh.write(f"- `{r['name']}`: {r.get('detail') or 'failed'}\n")
    else:
        fh.write("\nNo failed checks recorded.\n")
print(len(failures))
PY
)"

rm -f "${RESULTS_JSONL}"

echo "smoke report json: ${REPORT_JSON}"
echo "smoke report md:   ${REPORT_MD}"
echo "smoke failed checks: ${fail_count}"

if [ "${SMOKE_STRICT}" = "true" ] && [ "${fail_count}" -gt 0 ]; then
  exit 1
fi
