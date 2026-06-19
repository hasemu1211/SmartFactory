#!/usr/bin/env bash
set -euo pipefail

missing=0
for name in ATLASSIAN_EMAIL ATLASSIAN_API_TOKEN CONFLUENCE_BASE_URL; do
  if [[ -z "${!name:-}" ]]; then
    echo "MISSING: $name"
    missing=1
  else
    if [[ "$name" == "ATLASSIAN_API_TOKEN" ]]; then
      echo "OK: $name=(set, hidden)"
    else
      echo "OK: $name=${!name}"
    fi
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo
  echo "Copy .env.confluence.local.example to .env.confluence.local, fill it, then run: direnv allow"
  exit 1
fi

echo
base="${CONFLUENCE_BASE_URL%/}"
echo "Testing Confluence API access: ${base}/api/v2/pages?limit=1"
http_code=$(curl -sS -o /tmp/confluence-env-check.json -w '%{http_code}' \
  -u "${ATLASSIAN_EMAIL}:${ATLASSIAN_API_TOKEN}" \
  -H 'Accept: application/json' \
  "${base}/api/v2/pages?limit=1")

echo "HTTP: ${http_code}"
if [[ "$http_code" =~ ^2 ]]; then
  echo "Confluence API auth looks OK."
else
  echo "Confluence API check failed. Response preview:"
  head -c 1200 /tmp/confluence-env-check.json || true
  echo
  exit 2
fi
