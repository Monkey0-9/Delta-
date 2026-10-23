"""Institutional Tests for 24/7 Sentinel Live Wiring & Cross-Process Kill Circuit.

Validates:
1. Sentinel passes real broker adapters to safety.kill_all upon drawdown breach.
2. Real portfolio equity and positions functions drive surveillance.
3. Cross-process kill state synchronization: persisting HALTED freezes order submission
   across independent process boundaries.
"""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
import pytest

from delta_os.brain import DeltaBrain, DeltaSentinel
from delta_os.safety import (
    SafetyState,
    OrderTicket,
    persist_safety_mode,
    read_persisted_safety_mode,
)


class MockBrokerAdapter:
    def __init__(self, name: str = "paper"):
        self.name = name
        self.cancel_all_called = False

    def cancel_all(self):
        self.cancel_all_called = True
        return {"cancelled": 3, "orders": ["O-1", "O-2", "O-3"]}


def test_sentinel_drawdown_trips_broker_adapters(tmp_path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))

    brain = DeltaBrain()
    safety = SafetyState(require_auth=False)
    adapter = MockBrokerAdapter("paper")

    # Start with $100,000 equity, then simulate drop to $95,000 (5.0% loss, exceeding 2.0% threshold)
    equity_val = 100_000.0

    def read_eq():
        return equity_val

    sentinel = DeltaSentinel(
        brain=brain,
        safety_state=safety,
        max_drawdown_pct=2.0,
        equity_fn=read_eq,
        broker_adapters=[adapter],
        state_path=str(tmp_path / "sentinel.json"),
    )

    # First tick: initialises peak at $100,000
    res1 = sentinel.tick_once()
    assert not res1["halted"]
    assert sentinel.peak_equity == 100_000.0
    assert not adapter.cancel_all_called

    # Second tick: simulate drawdown breach
    equity_val = 95_000.0
    res2 = sentinel.tick_once()
    assert res2["halted"]
    assert adapter.cancel_all_called, "Broker adapter cancel_all must be invoked upon drawdown tripwire"
    assert safety.mode == "HALTED"
    assert read_persisted_safety_mode() == "HALTED"


def test_cross_process_kill_circuit_enforcement(tmp_path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))

    # Process 1: Autonomous daemon or risk officer halts the trading system
    persist_safety_mode("HALTED")

    # Process 2: Independent trading session attempts order governor check
    independent_safety = SafetyState(require_auth=False)
    ticket = OrderTicket(
        symbol="AAPL",
        action="BUY",
        order_type="LIMIT",
        price=150.0,
        quantity=10.0,
        stop_loss=145.0,
        target=160.0,
    )

    allowed, reason = independent_safety.govern(
        ticket=ticket,
        equity=50_000.0,
        positions_value=0.0,
        day_equity=50_000.0,
    )

    assert not allowed, "Order must be denied when system is HALTED in persisted storage"
    assert reason == "HALTED"
    assert independent_safety.mode == "HALTED"


def test_unlock_restores_cross_process_order_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))
    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "DELTA_PROD_SEC_TOKEN_999")

    # Trip the system
    persist_safety_mode("HALTED")

    safety = SafetyState(require_auth=True)
    assert safety.mode == "HALTED"

    # Unlock with valid credentials
    safety.unlock(
        actor="risk_officer_alice",
        reason="morning_recheck_complete",
        token="DELTA_PROD_SEC_TOKEN_999",
        role="RISK_OFFICER",
    )

    assert safety.mode == "MANUAL"
    assert read_persisted_safety_mode() == "MANUAL"

    ticket = OrderTicket(
        symbol="SPY",
        action="BUY",
        order_type="LIMIT",
        price=500.0,
        quantity=5.0,
        stop_loss=490.0,
        target=525.0,
    )
    allowed, reason = safety.govern(
        ticket=ticket,
        equity=100_000.0,
        positions_value=0.0,
        day_equity=100_000.0,
    )
    assert allowed, f"Order should be allowed after authenticated unlock, got: {reason}"
