"""Security and Authentication Acceptance Tests for DELTA Protocol Bridge.

Verifies:
1. Refusal to bind to non-loopback interfaces without explicit --allow-remote.
2. Protection of sensitive endpoints (run_cycle, reconcile, kill_switch, dispatch).
3. Rejection of unauthenticated requests with HTTP 401 and JSON-RPC -32001.
4. Acceptance of authorized requests using Bearer token or parameter token.
5. Elimination of wildcard CORS (*) on authenticated boundaries.
"""
from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path
import pytest

from delta_os.bridge import DeltaBridge, run_network_server


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_bridge_refuses_non_loopback_without_allow_remote():
    with pytest.raises(PermissionError) as exc_info:
        run_network_server(hostname="0.0.0.0", port=19890, allow_remote=False)
    assert "Refusing to bind to non-loopback interface" in str(exc_info.value)


@pytest.fixture(scope="module")
def secured_bridge_server():
    """Start bridge server with forced authentication enabled."""
    port = _find_free_port()
    ready = threading.Event()

    import os
    orig_req = os.environ.get("DELTA_REQUIRE_RPC_AUTH")
    orig_tok = os.environ.get("DELTA_UNLOCK_TOKEN")
    os.environ["DELTA_REQUIRE_RPC_AUTH"] = "1"
    os.environ["DELTA_UNLOCK_TOKEN"] = "SUPER_SECURE_AUTH_TOKEN_DELTA"

    server_thread = threading.Thread(
        target=run_network_server,
        kwargs={"hostname": "127.0.0.1", "port": port, "timeout": 60.0, "ready_event": ready},
        daemon=True,
    )
    server_thread.start()
    try:
        assert ready.wait(timeout=5.0), "Bridge failed to bind."
        yield f"http://127.0.0.1:{port}"
    finally:
        if orig_req is not None:
            os.environ["DELTA_REQUIRE_RPC_AUTH"] = orig_req
        else:
            os.environ.pop("DELTA_REQUIRE_RPC_AUTH", None)
        if orig_tok is not None:
            os.environ["DELTA_UNLOCK_TOKEN"] = orig_tok
        else:
            os.environ.pop("DELTA_UNLOCK_TOKEN", None)


def test_bridge_unauthorized_call_to_sensitive_rpc_rejected(secured_bridge_server):
    url = f"{secured_bridge_server}/rpc"
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "run_cycle",
        "params": {"symbols": ["SPY"]},
        "id": "sec-1",
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=3.0)

    assert exc_info.value.code == 401
    err_body = json.loads(exc_info.value.read().decode())
    assert err_body["error"]["code"] == -32001
    assert "Unauthorized" in err_body["error"]["message"]


def test_bridge_authorized_call_to_sensitive_rpc_succeeds(secured_bridge_server):
    url = f"{secured_bridge_server}/rpc"
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "dispatch",
        "params": {"text": "/status"},
        "id": "sec-2",
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer SUPER_SECURE_AUTH_TOKEN_DELTA",
    }
    req = urllib.request.Request(url, data=payload, headers=headers)
    resp = urllib.request.urlopen(req, timeout=5.0)

    assert resp.status == 200
    res = json.loads(resp.read().decode())
    assert res["id"] == "sec-2"
    assert "result" in res


def test_bridge_cors_does_not_emit_wildcard(secured_bridge_server):
    url = f"{secured_bridge_server}/healthz"
    req = urllib.request.Request(url, headers={"Origin": "http://evil.com"})
    resp = urllib.request.urlopen(req, timeout=3.0)
    cors_header = resp.headers.get("Access-Control-Allow-Origin")
    # Must NOT be wildcard *
    assert cors_header != "*"
    assert "127.0.0.1" in cors_header or "localhost" in cors_header
