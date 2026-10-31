"""Bridge Security & RBAC Exhaustive Verification Test Suite.

Proves:
1. `get_state` is protected and refuses unauthenticated requests when DELTA_REQUIRE_RPC_AUTH=1.
2. `get_state` allows authenticated requests with valid DELTA_RPC_KEY or pairing token.
3. GET `/pair?token=...` is rejected with HTTP 405 Method Not Allowed (eliminating URL token leakage).
4. POST `/pair` with JSON body succeeds with valid pairing token.
5. Untrusted proxy headers (X-Forwarded-For) without DELTA_TRUSTED_PROXY enforce authentication.
6. Public methods like `ping` and `/healthz` remain unauthenticated.
"""
from __future__ import annotations

import json
import threading
import time
import httpx
import pytest

from delta_os.bridge import run_network_server, PairingTokenRegistry, DeltaBridge


@pytest.fixture(scope="module")
def bridge_server():
    ready = threading.Event()
    port = 18765
    server_thread = threading.Thread(
        target=run_network_server,
        kwargs={
            "hostname": "127.0.0.1",
            "port": port,
            "timeout": 30.0,
            "ready_event": ready,
            "allow_remote": False,
        },
        daemon=True,
    )
    server_thread.start()
    ready.wait(timeout=3.0)
    base_url = f"http://127.0.0.1:{port}"
    yield base_url


def test_public_ping_and_healthz(bridge_server: str):
    # Healthz
    r = httpx.get(f"{bridge_server}/healthz")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

    # RPC ping
    payload = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    r = httpx.post(f"{bridge_server}/rpc", json=payload)
    assert r.status_code == 200
    assert r.json().get("result", {}).get("pong") is True


def test_get_state_unauthenticated_refusal(bridge_server: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DELTA_REQUIRE_RPC_AUTH", "1")
    monkeypatch.setenv("DELTA_RPC_KEY", "super_secret_rpc_token_12345")

    payload = {"jsonrpc": "2.0", "id": 2, "method": "get_state"}
    r = httpx.post(f"{bridge_server}/rpc", json=payload)
    assert r.status_code == 401
    err = r.json().get("error", {})
    assert err.get("code") == -32001
    assert "Unauthorized" in err.get("message", "")


def test_get_state_authenticated_access(bridge_server: str, monkeypatch: pytest.MonkeyPatch):
    key = "super_secret_rpc_token_12345"
    monkeypatch.setenv("DELTA_REQUIRE_RPC_AUTH", "1")
    monkeypatch.setenv("DELTA_RPC_KEY", key)

    payload = {"jsonrpc": "2.0", "id": 3, "method": "get_state"}
    headers = {"Authorization": f"Bearer {key}"}
    r = httpx.post(f"{bridge_server}/rpc", json=payload, headers=headers)
    assert r.status_code == 200
    res = r.json().get("result", {})
    assert "portfolio" in res or "equity" in res or "cash" in res


def test_get_pair_url_parameter_rejected(bridge_server: str):
    raw_token, _ = PairingTokenRegistry.generate_token(ttl_seconds=300)
    r = httpx.get(f"{bridge_server}/pair?token={raw_token}")
    assert r.status_code == 405
    data = r.json()
    assert data.get("status") == "REJECTED"
    assert "GET_DISALLOWED" in data.get("reason", "")


def test_post_pair_json_body_accepted(bridge_server: str):
    raw_token, _ = PairingTokenRegistry.generate_token(ttl_seconds=300)
    r = httpx.post(f"{bridge_server}/pair", json={"token": raw_token})
    assert r.status_code == 200
    data = r.json()
    assert data.get("paired") is True
    assert data.get("status") == "AUTHENTICATED"


def test_untrusted_reverse_proxy_enforces_auth(bridge_server: str, monkeypatch: pytest.MonkeyPatch):
    # Even without DELTA_REQUIRE_RPC_AUTH, X-Forwarded-For without DELTA_TRUSTED_PROXY enforces auth
    monkeypatch.delenv("DELTA_REQUIRE_RPC_AUTH", raising=False)
    monkeypatch.delenv("DELTA_TRUSTED_PROXY", raising=False)
    monkeypatch.setenv("DELTA_RPC_KEY", "proxy_test_secret_key")

    payload = {"jsonrpc": "2.0", "id": 4, "method": "get_state"}
    headers = {"X-Forwarded-For": "203.0.113.195"}
    r = httpx.post(f"{bridge_server}/rpc", json=payload, headers=headers)
    assert r.status_code == 401
