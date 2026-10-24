"""Tests for P0-E: Authorization integrity, default-deny unverified operators,
hard veto non-bypassability, and end-to-end order lineage query in ComplianceLog.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

from governance.compliance import ComplianceLog
from security.authorization import Role, role_can, Permission


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("DELTA_UNLOCK_TOKEN", raising=False)
    monkeypatch.delenv("DELTA_FORCE_TOKEN", raising=False)


def test_force_override_unauthenticated_denied(clean_env):
    """Force override without DELTA_UNLOCK_TOKEN must be denied (no DEV_UNAUTHENTICATED)."""
    from delta_os.repl import Terminal

    term = Terminal()
    # Attempt trade with --force but without DELTA_UNLOCK_TOKEN configured
    out, _ = term.handle("/trade SPY buy 1 --force --yes")
    assert "BLOCKED" in out
    assert "Force override refused" in out or "DELTA_UNLOCK_TOKEN required" in out

    # Compliance log must NOT contain DEV_UNAUTHENTICATED
    records = term.safety.compliance._records
    for r in records:
        if r.kind == "force_override":
            assert r.payload.get("auth") != "DEV_UNAUTHENTICATED"


def test_hard_safety_veto_cannot_be_bypassed_by_force(monkeypatch):
    """Hard safety veto (e.g. HALTED mode or kill switch active) cannot be bypassed even with valid token and --force."""
    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "SECRET_KEY_999")
    from delta_os.repl import Terminal

    term = Terminal()
    # Trip kill switch
    term.safety.mode = "HALTED"

    out, _ = term.handle("/trade SPY buy 1 --force --unlock-token SECRET_KEY_999 --yes")
    assert "BLOCKED" in out
    assert "HALTED" in out or "kill" in out.lower()


def test_unauthenticated_role_defaults_to_quant_and_denies_order_submit(clean_env, monkeypatch):
    """Unauthenticated operators default to QUANT, denying order submission without credentials."""
    from delta_os.repl import Terminal

    term = Terminal()
    monkeypatch.setattr(term.brain, "gate_automation", lambda s, d: {"verdict": "ALLOW", "reasons": ["pass"]})
    # Attempting to trade without authenticated credentials on a real/live broker or when token configured
    term.broker_name = "alpaca"
    out, _ = term.handle("/trade SPY buy 1 --yes")
    # Must fail with BLOCKED or Gateway refusal / permission_denied
    assert "BLOCKED" in out or "refused" in out.lower() or "denied" in out.lower() or "permission" in out.lower()


def test_compliance_log_order_lineage_query(tmp_path):
    """ComplianceLog can join and query full order lineage from snapshot to fills and reconciliation."""
    log_path = tmp_path / "compliance.jsonl"
    log = ComplianceLog(log_path)

    order_id = "ORD-TEST-001"
    idem_key = "IDEM-TEST-001"

    # 1. Data snapshot
    log.append("data_snapshot", {
        "order_id": order_id,
        "symbol": "SPY",
        "as_of": "2026-10-24T00:00:00Z",
        "data_tier": "TIER1",
        "quality": "verified",
        "source_hash": "a1b2c3d4",
    })

    # 2. Strategy decision
    log.append("strategy_decision", {
        "order_id": order_id,
        "symbol": "SPY",
        "model": "momentum_v1",
        "regime": "BULL_NORMAL",
        "signal": 1.0,
    })

    # 3. Risk verdict
    log.append("risk_verdict", {
        "order_id": order_id,
        "verdict": "APPROVED",
        "checks_passed": ["max_leverage", "drawdown", "anti_tilt"],
    })

    # 4. Verified approval
    log.append("order_approval", {
        "order_id": order_id,
        "actor": "authenticated-risk-officer",
        "role": "risk_officer",
        "auth_method": "TOKEN_VERIFIED",
    })

    # 5. Order intent / gateway
    log.append("order", {
        "order_id": order_id,
        "idempotency_key": idem_key,
        "symbol": "SPY",
        "side": "BUY",
        "quantity": 10.0,
        "price": 500.0,
    })

    # 6. Broker acknowledgement
    log.append("broker_ack", {
        "order_id": order_id,
        "status": "ACKNOWLEDGED",
        "broker": "paper",
    })

    # 7. Execution Fill & Fee
    log.append("fill", {
        "order_id": order_id,
        "symbol": "SPY",
        "side": "BUY",
        "qty": 10.0,
        "price": 500.05,
        "fee": 0.50,
        "arrival_px": 500.0,
    })

    # 8. Reconciliation
    log.append("reconciliation", {
        "order_id": order_id,
        "reconciled": True,
        "breaks": [],
    })

    # Query full lineage
    lineage = log.get_order_lineage(order_id)
    assert lineage is not None
    assert lineage["order_id"] == order_id
    assert lineage["data_snapshot"]["data_tier"] == "TIER1"
    assert lineage["strategy_decision"]["regime"] == "BULL_NORMAL"
    assert lineage["risk_verdict"]["verdict"] == "APPROVED"
    assert lineage["approval"]["role"] == "risk_officer"
    assert lineage["order"]["quantity"] == 10.0
    assert lineage["broker_ack"]["status"] == "ACKNOWLEDGED"
    assert len(lineage["fills"]) == 1
    assert lineage["fills"][0]["price"] == 500.05
    assert lineage["reconciliation"]["reconciled"] is True

    # List lineages
    lineages = log.list_lineages()
    assert len(lineages) == 1
    assert lineages[0]["order_id"] == order_id


def test_trade_execution_persists_lineage_join(monkeypatch):
    """Submitting a trade through REPL must record the full lineage in ComplianceLog."""
    import pandas as pd
    from delta_os.repl import Terminal

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

    term = Terminal()
    out, _ = term.handle("/trade AAPL buy 10 --yes")
    assert "submitted" in out

    # Verify compliance log contains joined lineage for this order
    lineages = term.safety.compliance.list_lineages()
    assert len(lineages) >= 1
    last_lineage = lineages[-1]
    assert last_lineage["symbol"] == "AAPL"
    assert last_lineage["side"] == "BUY"
    assert last_lineage["quantity"] == 10.0
    assert last_lineage["data_snapshot"].get("price") == 150.0
    assert last_lineage["risk_verdict"].get("verdict") == "approve"
    assert last_lineage["broker_ack"].get("status") in ("FILLED", "PARTIAL")
    assert len(last_lineage["fills"]) >= 1
    assert last_lineage["realized_outcome"]["filled_qty"] > 0

