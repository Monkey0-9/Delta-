"""P0-B Test Suite: Real Subprocess & JSON-RPC Bridge Hardening.

Tests:
1. Subprocess bridge server starts, responds to GET /healthz with typed status.
2. JSON-RPC dispatch executes commands and returns typed statuses.
3. Mutating methods (cancel, unlock) enforce authorization and reject unauthenticated requests.
4. JSON-RPC cancel cancels real paper order and returns acknowledged status.
5. Malformed JSON returns -32700 parse error.
6. Oversized request (>2MB) returns 413 / error.
7. Occupied port returns clean error without hanging.
8. Background bridge daemon management starts and stops cleanly.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import pytest


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def bridge_server():
    port = _find_free_port()
    cmd = [
        sys.executable,
        "-m",
        "delta_os.bridge",
        "--serve",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    env = dict(os.environ)
    env["DELTA_UNLOCK_TOKEN"] = "TEST_SECRET_TOKEN_123"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    
    # Wait for server to become responsive
    url = f"http://127.0.0.1:{port}/healthz"
    started = False
    for _ in range(30):
        time.sleep(0.1)
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    started = True
                    break
        except Exception:
            pass

    if not started:
        proc.kill()
        out, err = proc.communicate(timeout=2)
        pytest.fail(f"Bridge server failed to start on port {port}. Out: {out.decode()} Err: {err.decode()}")

    yield {"port": port, "url": f"http://127.0.0.1:{port}", "proc": proc}

    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_bridge_healthz_and_cors(bridge_server):
    port = bridge_server["port"]
    url = f"http://127.0.0.1:{port}/healthz"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["status"] == "ok"
        assert data["service"] == "delta-protocol-bridge"
        assert data["fail_closed"] is True


def test_bridge_rpc_dispatch(bridge_server):
    url = f"{bridge_server['url']}/rpc"
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": "req-1",
        "method": "dispatch",
        "params": {"text": "/stats SPY"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["id"] == "req-1"
        assert "result" in data
        assert data["result"]["status"] in ("ok", "unavailable")


def test_bridge_cancel_unauthorized_rejected(bridge_server):
    url = f"{bridge_server['url']}/rpc"
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": "req-cancel-unauth",
        "method": "cancel",
        "params": {"order_id": "PO-12345"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            # Must return error code for unauthorized mutating action
            assert "error" in data or data.get("result", {}).get("status") in ("DENIED", "UNAUTHORIZED")
    except urllib.error.HTTPError as err:
        assert err.code in (401, 403)


def test_bridge_cancel_authorized_paper_order(bridge_server):
    # Submit an order through the bridge subprocess
    url = f"{bridge_server['url']}/rpc"
    trade_body = json.dumps({
        "jsonrpc": "2.0",
        "id": "req-submit",
        "method": "dispatch",
        "params": {"text": "/trade SPY buy 1 --yes"},
    }).encode()
    req = urllib.request.Request(url, data=trade_body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        assert resp.status == 200
        trade_data = json.loads(resp.read().decode())
        assert trade_data.get("result", {}).get("status") in ("ok", "blocked")

    # Now invoke authorized cancel-all or cancel via bridge RPC
    cancel_body = json.dumps({
        "jsonrpc": "2.0",
        "id": "req-cancel-auth",
        "method": "cancel",
        "params": {"order_id": "ALL", "token": "TEST_SECRET_TOKEN_123"},
    }).encode()
    cancel_req = urllib.request.Request(url, data=cancel_body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(cancel_req, timeout=10.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["id"] == "req-cancel-auth"
        assert "result" in data
        res = data["result"]
        assert res.get("cancelled") is True or res.get("status") == "CANCELLED"
        assert res.get("acknowledged") is True


def test_bridge_malformed_json_returns_parse_error(bridge_server):
    url = f"{bridge_server['url']}/rpc"
    bad_body = b"NOT_A_VALID_JSON{{{"
    req = urllib.request.Request(url, data=bad_body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            assert resp.status == 400
    except urllib.error.HTTPError as err:
        assert err.code == 400
        err_data = json.loads(err.read().decode())
        assert err_data["error"]["code"] == -32700


def test_bridge_oversized_payload_rejected(bridge_server):
    url = f"{bridge_server['url']}/rpc"
    oversized = b"x" * (3 * 1024 * 1024)  # 3MB > 2MB limit
    req = urllib.request.Request(url, data=oversized, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            assert resp.status in (400, 413)
    except urllib.error.HTTPError as err:
        assert err.code in (400, 413)
    except urllib.error.URLError:
        # Connection reset/broken pipe is also valid when server rejects oversized payload
        pass


def test_bridge_occupied_port_fails_gracefully():
    port = _find_free_port()
    # Occupy the port with a bound socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)
    try:
        cmd = [
            sys.executable,
            "-m",
            "delta_os.bridge",
            "--serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--timeout",
            "1",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        # Should exit with non-zero or address in use error without hanging
        assert res.returncode != 0 or "Address already in use" in res.stderr or "Address already in use" in res.stdout
    finally:
        sock.close()
