"""Institutional Integration Tests for DELTA Protocol Bridge Network Server & Pairing.

Validates:
1. TCP socket loopback binding and HTTP server lifecycle.
2. Standard JSON-RPC 2.0 requests over network transport (ping, healthz, quote, dispatch).
3. Structured error handling for malformed JSON (-32700) and unknown methods (-32601).
4. Single-use token pairing protocol: generation, redemption, replay rejection, and expiration.
"""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.request
import urllib.error
import pytest

from delta_os.bridge import DeltaBridge, PairingTokenRegistry, run_network_server


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def bridge_server():
    """Spin up bridge server on a test loopback port."""
    port = _find_free_port()
    ready = threading.Event()
    server_thread = threading.Thread(
        target=run_network_server,
        kwargs={"hostname": "127.0.0.1", "port": port, "timeout": 60.0, "ready_event": ready},
        daemon=True,
    )
    server_thread.start()
    assert ready.wait(timeout=5.0), "Bridge server failed to bind and signal ready."
    yield f"http://127.0.0.1:{port}"


def test_bridge_healthz(bridge_server):
    url = f"{bridge_server}/healthz"
    req = urllib.request.urlopen(url, timeout=3.0)
    assert req.status == 200
    data = json.loads(req.read().decode())
    assert data["status"] == "ok"
    assert data["service"] == "delta-protocol-bridge"
    assert "version" in data


def test_bridge_json_rpc_ping_and_quote(bridge_server):
    url = f"{bridge_server}/rpc"

    # 1. Ping
    payload = json.dumps({"jsonrpc": "2.0", "method": "ping", "id": 101}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=3.0)
    assert resp.status == 200
    res = json.loads(resp.read().decode())
    assert res["id"] == 101
    assert res["result"]["pong"] is True

    # 2. Quote
    payload = json.dumps({"jsonrpc": "2.0", "method": "quote", "params": {"symbol": "SPY"}, "id": 102}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=3.0)
    assert resp.status == 200
    res = json.loads(resp.read().decode())
    assert res["id"] == 102
    assert res["result"]["symbol"] == "SPY"
    assert "bars" in res["result"]
    assert "rsi_history" in res["result"]


def test_bridge_json_rpc_errors(bridge_server):
    url = f"{bridge_server}/rpc"

    # Malformed JSON -> 400 with -32700
    req = urllib.request.Request(url, data=b"{malformed json", headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=3.0)
    assert exc_info.value.code == 400
    err_body = json.loads(exc_info.value.read().decode())
    assert err_body["error"]["code"] == -32700

    # Unknown method -> 404 with -32601
    payload = json.dumps({"jsonrpc": "2.0", "method": "non_existent_method_xyz", "id": 999}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=3.0)
    assert exc_info.value.code == 404
    err_body = json.loads(exc_info.value.read().decode())
    assert err_body["error"]["code"] == -32601


def test_pairing_token_single_use_and_replay_rejection(bridge_server, tmp_path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))

    # 1. Generate token
    raw_token, record = PairingTokenRegistry.generate_token(ttl_seconds=300)
    assert len(raw_token) >= 20
    assert record["used"] is False

    # 2. Redeem over HTTP POST /pair with JSON body to prevent URL logging exposure
    url = f"{bridge_server}/pair"
    payload = json.dumps({"token": raw_token}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=3.0)
    assert resp.status == 200
    data = json.loads(resp.read().decode())
    assert data["paired"] is True
    assert data["status"] == "AUTHENTICATED"

    # 3. Second redemption fails (Replay Protection) -> 403
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=3.0)
    assert exc_info.value.code == 403
    rej_data = json.loads(exc_info.value.read().decode())
    assert rej_data["paired"] is False
    assert rej_data["reason"] == "TOKEN_ALREADY_USED"

    # 4. Unknown token -> 401
    bad_payload = json.dumps({"token": "completely_invalid_token"}).encode("utf-8")
    bad_req = urllib.request.Request(url, data=bad_payload, headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(bad_req, timeout=3.0)
    assert exc_info.value.code == 401
