#!/usr/bin/env python3
"""Local Server Manager Daemon for GitHub AI Video Generator.

Provides an out-of-band management HTTP service on port 8001 that can detect,
start, restart, and stop the primary Uvicorn/FastAPI process on port 8000.
"""
from __future__ import annotations

import json
import logging
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.server_control import ServerController  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("server_manager")

MANAGER_HOST = "0.0.0.0"
MANAGER_PORT = 8001
controller = ServerController(host="0.0.0.0", port=8000, repo_root=REPO_ROOT)


class ServerManagerHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data: dict, status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path in ("/api/server/status", "/status"):
            state = controller.get_status()
            self._send_json({"success": True, "data": state.to_dict()})
            return

        if path == "/health":
            self._send_json({"status": "ok", "service": "server_manager"})
            return

        # Fallback root: if port 8000 is running, redirect; else serve generate.html
        status = controller.get_status()
        if status.status == "Running":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "http://localhost:8000/")
            self.end_headers()
            return

        template_path = REPO_ROOT / "app" / "templates" / "generate.html"
        if template_path.exists():
            html = template_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(html)
            return

        self._send_json({"error": "Not Found"}, status=404)

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        if path == "/api/server/start":
            state = controller.start()
            self._send_json({"success": True, "data": state.to_dict()})
            return

        if path == "/api/server/restart":
            state = controller.restart()
            self._send_json({"success": True, "data": state.to_dict()})
            return

        if path == "/api/server/stop":
            state = controller.stop()
            self._send_json({"success": True, "data": state.to_dict()})
            return

        self._send_json({"error": "Unknown action"}, status=404)

    def log_message(self, format: str, *args: object) -> None:
        logger.debug(
            "%s - - [%s] %s",
            self.address_string(),
            self.log_date_time_string(),
            format % args,
        )


def main() -> None:
    logger.info("Initializing Local Server Manager on %s:%d...", MANAGER_HOST, MANAGER_PORT)
    # Check if primary server on 8000 is running; if not, initiate startup
    current = controller.get_status()
    if current.status == "Running":
        logger.info("Primary server already running on port 8000 (PID %s).", current.pids)
    else:
        logger.info("Primary server not running on port 8000. Launching Uvicorn...")
        started = controller.start()
        logger.info("Primary server launch status: %s", started.status)

    server = ThreadingHTTPServer((MANAGER_HOST, MANAGER_PORT), ServerManagerHandler)
    server.daemon_threads = True
    logger.info("Server Manager listening on http://%s:%d", MANAGER_HOST, MANAGER_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Server Manager...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
