from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class HealthState:
    def __init__(self) -> None:
        self.ready = False
        self.live = True
        self.details: dict[str, Any] = {}

    def set_ready(self, ready: bool, **details: Any) -> None:
        self.ready = ready
        self.details.update(details)


health_state = HealthState()


class _HealthHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/live":
            self._send(200 if health_state.live else 503, {"status": "live"})
            return
        if self.path == "/ready":
            self._send(
                200 if health_state.ready else 503,
                {"status": "ready" if health_state.ready else "not_ready", **health_state.details},
            )
            return
        self._send(404, {"error": "not_found"})

    def log_message(self, format: str, *args: object) -> None:
        return


def start_health_server(port: int) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


def main() -> None:
    start_health_server(8080)
    threading.Event().wait()
