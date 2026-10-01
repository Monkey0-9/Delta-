"""Prometheus exporter for Telemetry — closes STUB_AUDIT #5.

Stdlib-only HTTP scrape endpoint. Usage:
    from observability.telemetry import Telemetry
    from observability.exporter import serve_forever
    tel = Telemetry(); ... ; serve_forever(tel, port=9108)
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any


def _render(tel: Any) -> bytes:
    try:
        body = tel.to_prometheus()
    except Exception as exc:  # fail-closed: expose error, never fake metrics
        body = f"# error rendering telemetry: {exc}"
    return body.encode("utf-8")


def make_handler(tel: Any):
    class _H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path not in ("/", "/metrics"):
                self.send_response(404); self.end_headers(); return
            payload = _render(tel)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):  # quiet
            pass
    return _H


def serve_forever(tel: Any, host: str = "127.0.0.1", port: int = 9108) -> HTTPServer:
    srv = HTTPServer((host, port), make_handler(tel))
    return srv


def serve_background(tel: Any, host: str = "127.0.0.1", port: int = 9108) -> tuple[HTTPServer, Thread]:
    srv = serve_forever(tel, host, port)
    th = Thread(target=srv.serve_forever, daemon=True, name="delta-prom-exporter")
    th.start()
    return srv, th


__all__ = ["serve_forever", "serve_background"]
