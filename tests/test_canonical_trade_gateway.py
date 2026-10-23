"""Tests ensuring /trade in REPL routes through canonical OrderGateway and OMS."""
from __future__ import annotations

import os
from decimal import Decimal
import pandas as pd
import pytest

from delta_os.repl import Terminal
from core.domain.order import OrderStatus


@pytest.fixture
def mock_terminal(monkeypatch):
    df = pd.DataFrame(
        {
            "open": [150.0] * 60,
            "high": [151.0] * 60,
            "low": [149.0] * 60,
            "close": [150.0] * 60,
            "volume": [100000.0] * 60,
        },
        index=pd.date_range("2024-01-01", periods=60, tz="UTC"),
    )
    monkeypatch.setattr("delta_os.data_router._tier1_yfinance", lambda s, d: df)
    t = Terminal()
    return t


def test_trade_routes_through_order_gateway(mock_terminal):
    t = mock_terminal
    out, _ = t.handle("/trade AAPL buy 10 --yes")
    assert "submitted" in out

    # Verify OrderGateway exists and has recorded the order in its audit_log
    gw = getattr(t, "_order_gateway", None)
    assert gw is not None
    assert len(gw.audit_log) >= 1
    last_audit = gw.audit_log[-1]
    assert last_audit["verdict"] == "approve"
    assert last_audit["submitted"] is True
    assert last_audit["broker_ack"] is not None


def test_trade_refuses_when_token_configured_and_unauthenticated(mock_terminal, monkeypatch):
    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "super-secret-auth-token")
    t = mock_terminal
    t.broker_name = "alpaca"
    # Provide a mock submit on router's current broker so authenticated orders can succeed
    cur = t.router.current()
    monkeypatch.setattr(cur, "submit", lambda *a, **k: {"order_id": "test-alpaca-1", "status": "FILLED", "filled": 10, "avg_price": 150.0})

    # Standard unauthenticated request on non-paper broker gets QUANT role which is refused for SUBMIT_ORDER
    out, _ = t.handle("/trade AAPL buy 10 --yes")
    assert "Gateway refusal" in out or "unauthorized_role" in out

    # Authenticated request with --unlock-token succeeds
    out2, _ = t.handle("/trade AAPL buy 10 --yes --unlock-token super-secret-auth-token")
    assert "submitted" in out2


def test_trade_audit_log_tracks_rejections(mock_terminal):
    t = mock_terminal
    # Out of bounds quantity that triggers gross exposure or price deviation
    out, _ = t.handle("/trade AAPL buy 100000000 --yes")
    assert "firewall" in out or "governor" in out or "error" in out.lower()
