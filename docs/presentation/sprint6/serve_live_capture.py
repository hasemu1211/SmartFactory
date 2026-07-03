#!/usr/bin/env python3
"""Serve Sprint 6 capture assets plus a tiny AI Server JSON proxy.

Why this exists:
- The presentation page is served from this operator PC on :9876.
- AI Server JSON endpoints do not currently allow that origin via CORS.
- Browser iframes can show raw JSON with unreadable colors under some themes.

This helper keeps the page simple: `/proxy?path=/api/...` fetches from the
Vision laptop and returns readable JSON to same-origin JavaScript. It is only a
local lab presentation helper; it does not expose arbitrary shell execution or
mutate robot/Main state.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
DEFAULT_AI_SERVER = "http://smartfactory-vision.local:8100"


class CaptureHandler(SimpleHTTPRequestHandler):
    ai_server_base = DEFAULT_AI_SERVER

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        parsed = urlparse(self.path)
        if parsed.path == "/proxy":
            self._handle_proxy(parsed.query)
            return
        super().do_GET()

    def _handle_proxy(self, query: str) -> None:
        params = parse_qs(query)
        path = (params.get("path") or [""])[0]
        if not path.startswith("/api/"):
            self._send_json(400, {"error": "proxy path must start with /api/"})
            return

        target = urljoin(self.ai_server_base.rstrip("/") + "/", path.lstrip("/"))
        try:
            request = Request(target, headers={"Accept": "application/json"})
            with urlopen(request, timeout=5.0) as response:
                body = response.read()
                status = response.status
        except HTTPError as exc:
            self._send_json(exc.code, {"error": "upstream_http_error", "status": exc.code, "url": target})
            return
        except URLError as exc:
            self._send_json(502, {"error": "upstream_unreachable", "reason": str(exc.reason), "url": target})
            return
        except TimeoutError:
            self._send_json(504, {"error": "upstream_timeout", "url": target})
            return

        # Validate/pretty-stabilize JSON enough for browser rendering. If an
        # endpoint unexpectedly returns non-JSON, wrap it rather than serving a
        # white raw document.
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"raw": body.decode("utf-8", errors="replace"), "url": target}
        self._send_json(status, payload)

    def _send_json(self, status: int, payload: object) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Sprint 6 live capture page.")
    parser.add_argument("--host", default=os.environ.get("SPRINT6_CAPTURE_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SPRINT6_CAPTURE_PORT", "9876")))
    parser.add_argument("--ai-server", default=os.environ.get("AI_SERVER_URL", DEFAULT_AI_SERVER))
    args = parser.parse_args()

    CaptureHandler.ai_server_base = args.ai_server
    handler = functools.partial(CaptureHandler, directory=str(ROOT))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Sprint 6 capture page: http://127.0.0.1:{args.port}/live-capture.html")
    print(f"Proxy upstream AI Server: {args.ai_server}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
