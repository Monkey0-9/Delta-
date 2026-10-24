"""Tests for P0-D: Canonical AccountSnapshot API, missing quote fail-closed degradation,
Sentinel block-new-orders on missing/NaN equity, and active broker adapter kill wiring.
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import pytest

from delta_os import brokers
from delta_os.brain import DeltaBrain, DeltaSentinel
from delta_os.safety import OrderTicket, SafetyState


def test_account_snapshot_paper_clean():
    """PaperAdapter.get_account_snapshot computes equity with live quotes without private ledger access."""
    adapter = brokers.PaperAdapter(seed=42)
    # Cash starts at 100,000
    res = adapter.submit("AAPL", "BUY", 10.0, 150.0)
    assert res["status"] in ("FILLED", "PARTIAL")
    filled_qty = res["filled"]
    assert filled_qty > 0

    snap = adapter.get_account_snapshot(price_provider=lambda sym: 160.0 if sym == "AAPL" else None)
    assert not snap.degraded
    assert snap.equity is not None
    assert snap.positions.get("AAPL") == filled_qty
    assert snap.prices.get("AAPL") == 160.0
    assert snap.market_values.get("AAPL") == pytest.approx(filled_qty * 160.0)
    expected_equity = snap.cash + (filled_qty * 160.0)
    assert snap.equity == pytest.approx(expected_equity)


def test_account_snapshot_missing_quote_fails_closed():
    """Missing or NaN quote must mark snapshot as degraded and set equity to None (NO avg_price fallback)."""
    adapter = brokers.PaperAdapter(seed=42)
    adapter.submit("MSFT", "BUY", 5.0, 300.0)

    # Price provider returns None (quote unavailable)
    snap = adapter.get_account_snapshot(price_provider=lambda sym: None)
    assert snap.degraded
    assert snap.equity is None
    assert "Missing or unverified quote" in (snap.degraded_reason or "")

    # Price provider returns NaN
    snap_nan = adapter.get_account_snapshot(price_provider=lambda sym: float("nan"))
    assert snap_nan.degraded
    assert snap_nan.equity is None


def test_sentinel_tick_missing_equity_blocks_new_orders():
    """When equity is None or NaN, Sentinel must set safety mode to DEGRADED and block new orders."""
    brain = DeltaBrain()
    safety = SafetyState(require_auth=False)
    safety.mode = "MANUAL"

    equity_val = None

    sentinel = DeltaSentinel(
        brain=brain,
        safety_state=safety,
        max_drawdown_pct=2.0,
        equity_fn=lambda: equity_val,
    )

    # First tick with None equity
    out = sentinel.tick_once()
    assert safety.mode == "DEGRADED"
    assert any("degraded" in a.lower() or "block" in a.lower() for a in out["actions"])

    # Attempting to govern an order in DEGRADED mode must be rejected
    ticket = OrderTicket("SPY", "BUY", "LIMIT", 400.0, 1.0)
    allowed, reason = safety.govern(ticket, equity=100000.0, positions_value=0.0, day_equity=100000.0)
    assert not allowed
    assert "DEGRADED" in reason or "blocked" in reason.lower()

    # Recovery: equity becomes available again
    equity_val = 100000.0
    out2 = sentinel.tick_once()
    assert safety.mode != "DEGRADED"


def test_sentinel_kill_path_cancels_active_adapter():
    """When drawdown threshold is breached, Sentinel must call cancel_all on the active broker adapter."""
    brain = DeltaBrain()
    safety = SafetyState(require_auth=False)
    adapter = brokers.PaperAdapter(seed=42)

    # Submit an order that remains open (unfilled limit order)
    # Set limit price far below to leave it working if ledger supported open orders,
    # or test cancel_all invocation on adapter directly.
    class MockAdapter:
        def __init__(self):
            self.cancelled_all = False

        def cancel_all(self):
            self.cancelled_all = True
            return {"cancelled": 3}

    mock_ad = MockAdapter()

    # Simulate drawdown: start at 100,000, drop to 95,000 (5% drop > 2% max_dd)
    eq_feed = [100000.0, 95000.0]
    idx = 0

    def eq_fn():
        nonlocal idx
        val = eq_feed[min(idx, len(eq_feed) - 1)]
        idx += 1
        return val

    sentinel = DeltaSentinel(
        brain=brain,
        safety_state=safety,
        max_drawdown_pct=2.0,
        equity_fn=eq_fn,
        broker_adapters=[mock_ad],
    )

    # Tick 1: initializes peak at 100k
    sentinel.tick_once()
    assert not mock_ad.cancelled_all
    assert safety.mode != "HALTED"

    # Tick 2: drops to 95k -> trips circuit breaker!
    out = sentinel.tick_once()
    assert out["halted"]
    assert mock_ad.cancelled_all
    assert safety.mode == "HALTED"


def test_broker_router_snapshot_delegation():
    """BrokerRouter.get_account_snapshot delegates to active broker adapter."""
    router = brokers.BrokerRouter()
    assert router.active == "paper"
    snap = router.get_account_snapshot()
    assert snap.broker == "paper"
    assert snap.connected
    assert snap.equity is not None


def test_adapter_cancellation_no_fake_ledger_access():
    """AlpacaAdapter and IBKRAdapter cancel() must not assume existence of self._ledger."""
    alpaca = brokers.AlpacaAdapter(key_id="test", secret="test")
    assert not hasattr(alpaca, "_ledger")
    # Calling cancel on non-existent connection fails cleanly with BrokerError / connect error, NOT AttributeError
    with pytest.raises(Exception) as exc_info:
        alpaca.cancel("order-123")
    assert not isinstance(exc_info.value, AttributeError)

    ibkr = brokers.IBKRAdapter(host="", account_id="")
    assert not hasattr(ibkr, "_ledger")
    with pytest.raises(brokers.BrokerError) as exc_info_ibkr:
        ibkr.cancel("order-123")
    assert "not configured" in str(exc_info_ibkr.value).lower()

