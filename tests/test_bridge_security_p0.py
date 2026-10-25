"""Tests for P0-C: Bridge RPC route authentication, unauthorized access rejection, and CORS allowlist.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock
from delta_os.bridge import _BridgeHTTPRequestHandler, DeltaBridge


def test_cors_origin_filtering():
    handler = _BridgeHTTPRequestHandler.__new__(_BridgeHTTPRequestHandler)
    handler.headers = {"Origin": "http://evil-attacker.com"}
    # Allowed origin defaults to loopback
    origin = handler._get_cors_origin()
    assert origin in ("http://127.0.0.1", "http://localhost")
    assert origin != "http://evil-attacker.com"
    assert origin != "*"

    # When origin is localhost, it is accepted
    handler.headers = {"Origin": "http://127.0.0.1"}
    assert handler._get_cors_origin() == "http://127.0.0.1"


def test_sensitive_rpc_requires_auth_when_configured(monkeypatch):
    monkeypatch.setenv("DELTA_REQUIRE_RPC_AUTH", "1")
    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "SECRET_AUTH_999")

    handler = _BridgeHTTPRequestHandler.__new__(_BridgeHTTPRequestHandler)
    handler.client_address = ("127.0.0.1", 54321)
    handler.headers = {}
    handler.bridge = MagicMock(spec=DeltaBridge)
    handler.rfile = MagicMock()
    handler.wfile = MagicMock()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    # Request without auth token to sensitive method 'dispatch'
    post_payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "dispatch", "params": {"text": "/trade AAPL"}}).encode("utf-8")
    handler.headers = {"Content-Length": str(len(post_payload))}
    handler.rfile.read.return_value = post_payload
    handler.path = "/rpc"

    handler.do_POST()

    # Must be rejected with 401 Unauthorized
    handler.send_response.assert_called_with(401)
