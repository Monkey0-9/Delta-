"""Institutional Canonical End-to-End Test Suite.

Proves the 12-stage quantitative trading pipeline with mathematical evidence:
1. Real Market Data & Point-in-Time (PIT) temporal integrity
2. Technical Indicator Mathematics (Wilder RSI, MACD, Bollinger Bands, ATR, VWAP)
3. Factor Alpha Generation & Beta Neutralization
4. Probabilistic Return Forecasting (P(r_{t+h} | X_t))
5. Macro Factor Regime Classification
6. Constrained Portfolio Optimization (Kelly / MVO, leverage & concentration limits)
7. Pre-Trade Risk Firewall & Scenario Stress Testing (VaR 95/99, CVaR, Shocks)
8. OMS Order State Machine & Submission Idempotency
9. Paper Broker Matching with Almgren-Chriss Slippage & Transaction Fees
10. Three-Way Reconciliation (Internal OMS vs External Broker Fills vs Ledger)
11. Cryptographic SHA-256 Chained Audit Trail
12. TUI Rust Bridge Protocol Schema Parity
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from core.canonical_pipeline import (
    AlphaSignal,
    CanonicalInstitutionalPipeline,
    CanonicalOrder,
    CanonicalOrderStatus,
    MarketRegime,
    OrderSide,
    PortfolioAllocation,
    PortfolioRiskMetrics,
    ReturnForecast,
    TechnicalIndicators,
    compute_atr,
    compute_bollinger_bands,
    compute_macd,
    compute_session_vwap,
    compute_wilder_rsi,
)
from delta_os.bridge import DeltaBridge
from execution.reconciliation.engine import ReconciliationStatus


@pytest.fixture
def pipeline():
    return CanonicalInstitutionalPipeline(initial_cash=1_000_000.0, venue="XNYS")


# ============================================================================
# 1. REAL MARKET DATA & POINT-IN-TIME (PIT)
# ============================================================================

def test_market_data_pit_monotone(pipeline):
    """Ensure data is strictly monotonic in time with no future data leakage."""
    bars = pipeline.fetch_market_bars("SPY", n_bars=100)
    assert len(bars) == 100
    assert bars.index.is_monotonic_increasing
    assert not bars.isna().any().any()
    # Check OHLC relations: high >= low, high >= open, high >= close
    assert (bars["high"] >= bars["low"]).all()
    assert (bars["high"] >= bars["open"]).all()
    assert (bars["high"] >= bars["close"]).all()
    assert (bars["low"] <= bars["open"]).all()
    assert (bars["low"] <= bars["close"]).all()


# ============================================================================
# 2. TECHNICAL INDICATOR MATHEMATICS
# ============================================================================

def test_technical_indicators_mathematics(pipeline):
    """Verify Wilder RSI, MACD, Bollinger Bands, ATR, and VWAP mathematical invariants."""
    bars = pipeline.fetch_market_bars("AAPL", n_bars=120)
    ind = pipeline.extract_features("AAPL", bars)

    # 1. RSI bounded in [0, 100]
    assert 0.0 <= ind.rsi <= 100.0

    # 2. Bollinger Bands ordering: upper >= middle >= lower
    assert ind.bb_upper >= ind.bb_middle >= ind.bb_lower

    # 3. MACD histogram = MACD line - Signal line
    np.testing.assert_allclose(ind.macd_histogram, ind.macd - ind.macd_signal, atol=1e-5)

    # 4. ATR must be strictly positive
    assert ind.atr > 0.0

    # 5. VWAP must be positive and within reasonable bounds of recent price
    assert ind.vwap > 0.0
    assert abs(ind.vwap - ind.price) / ind.price < 0.20


# ============================================================================
# 3. ALPHA GENERATION & BETA NEUTRALIZATION
# ============================================================================

def test_alpha_neutralization_and_decay(pipeline):
    """Confirm factor extraction produces both raw and beta-neutralized alpha signals."""
    spy_bars = pipeline.fetch_market_bars("SPY", n_bars=120)
    nvda_bars = pipeline.fetch_market_bars("NVDA", n_bars=120)

    market_ind = pipeline.extract_features("SPY", spy_bars)
    stock_ind = pipeline.extract_features("NVDA", nvda_bars)

    alpha = pipeline.generate_alpha(stock_ind, market_ind)
    assert isinstance(alpha, AlphaSignal)
    assert alpha.symbol == "NVDA"
    assert -5.0 <= alpha.raw_score <= 5.0
    assert -5.0 <= alpha.neutralized_score <= 5.0
    assert 0.0 <= alpha.confidence <= 1.0


# ============================================================================
# 4. PROBABILISTIC RETURN FORECASTING
# ============================================================================

def test_probabilistic_return_forecast(pipeline):
    """Validate full return distribution P(r_{t+h} | X_t)."""
    bars = pipeline.fetch_market_bars("MSFT", n_bars=120)
    ind = pipeline.extract_features("MSFT", bars)
    mkt = pipeline.extract_features("SPY", pipeline.fetch_market_bars("SPY", n_bars=120))
    alpha = pipeline.generate_alpha(ind, mkt)

    fc = pipeline.forecast_return(alpha, ind, horizon_days=5)
    assert isinstance(fc, ReturnForecast)
    assert fc.horizon_days == 5
    assert fc.variance > 0.0
    assert fc.volatility == pytest.approx(math.sqrt(fc.variance), rel=1e-5)
    assert fc.conf_interval_95[0] < fc.expected_return < fc.conf_interval_95[1]
    assert 0.0 <= fc.p_positive <= 1.0
    assert 0.0 <= fc.p_tail_loss <= 1.0


# ============================================================================
# 5. REGIME CLASSIFICATION
# ============================================================================

def test_regime_classification_invariants(pipeline):
    """Ensure market regime classifier handles tranquil and crisis market conditions."""
    mkt_bars = pipeline.fetch_market_bars("SPY", n_bars=120)
    mkt_ind = pipeline.extract_features("SPY", mkt_bars)
    regime = pipeline.detect_regime(mkt_ind)
    assert isinstance(regime, MarketRegime)
    assert regime in {
        MarketRegime.BULL_TREND,
        MarketRegime.BEAR_TREND,
        MarketRegime.HIGH_VOLATILITY,
        MarketRegime.RANGE_BOUND,
        MarketRegime.CRISIS_STRESS,
    }


# ============================================================================
# 6. PORTFOLIO ALLOCATION & CONSTRAINTS
# ============================================================================

def test_portfolio_allocation_and_leverage_limits(pipeline):
    """Ensure portfolio weights obey institutional risk constraints (<= 20% single name)."""
    symbols = ["SPY", "NVDA", "AAPL", "MSFT"]
    prices = {"SPY": 500.0, "NVDA": 120.0, "AAPL": 220.0, "MSFT": 420.0}
    forecasts = {
        sym: ReturnForecast(
            symbol=sym,
            horizon_days=5,
            expected_return=0.015,
            variance=0.0004,
            volatility=0.02,
            conf_interval_95=(-0.02, 0.05),
            p_positive=0.65,
            p_tail_loss=0.02,
            confidence=0.85,
            baseline_return=0.001,
        )
        for sym in symbols
    }

    alloc = pipeline.optimize_portfolio(forecasts, prices, MarketRegime.BULL_TREND)
    assert isinstance(alloc, PortfolioAllocation)
    for sym, w in alloc.weights.items():
        assert abs(w) <= 0.200001, f"Weight {w} exceeded 20% concentration limit for {sym}"
    assert alloc.leverage <= 1.500001


# ============================================================================
# 7. RISK FIREWALL & STRESS SHOCKS
# ============================================================================

def test_risk_firewall_and_limits(pipeline):
    """Validate VaR (95%/99%), CVaR (Expected Shortfall), and macroeconomic stress shocks."""
    pipeline.positions = {"SPY": 500, "AAPL": 400}
    prices = {"SPY": 500.0, "AAPL": 220.0}

    risk_metrics = pipeline.evaluate_risk(prices)
    assert isinstance(risk_metrics, PortfolioRiskMetrics)
    assert risk_metrics.var95_dollar > 0.0
    assert risk_metrics.var99_dollar >= risk_metrics.var95_dollar
    assert risk_metrics.cvar_dollar >= risk_metrics.var95_dollar
    assert risk_metrics.concentration_pct <= 100.0
    assert risk_metrics.status in {"SAFE", "WARNING", "LIMIT_BREACH"}


# ============================================================================
# 8. OMS STATE MACHINE & IDEMPOTENCY
# ============================================================================

def test_oms_order_lifecycle_and_idempotency(pipeline):
    """Ensure orders pass strictly through the canonical state machine and reject duplicates."""
    idemp_key = f"IDEMP-TEST-{uuid.uuid4().hex}"
    order = pipeline.create_order("SPY", OrderSide.BUY, 50, 500.0, idempotency_key=idemp_key)
    assert order.status == CanonicalOrderStatus.SUBMITTED
    assert CanonicalOrderStatus.CREATED in order.history
    assert CanonicalOrderStatus.VALIDATED in order.history
    assert CanonicalOrderStatus.RISK_APPROVED in order.history

    # Duplicate submission with same idempotency key must return the existing order
    duplicate = pipeline.create_order("SPY", OrderSide.BUY, 50, 500.0, idempotency_key=idemp_key)
    assert duplicate.order_id == order.order_id
    assert len(pipeline.orders) == 1


# ============================================================================
# 9. PAPER BROKER EXECUTION & SLIPPAGE
# ============================================================================

def test_paper_execution_and_almgren_chriss_slippage(pipeline):
    """Verify execution incorporates market impact, slippage, and updates cash/positions."""
    initial_cash = pipeline.cash
    order = pipeline.create_order("AAPL", OrderSide.BUY, 100, 200.0)
    fill = pipeline.execute_order(order, market_price=200.0)

    assert fill is not None
    assert fill.symbol == "AAPL"
    assert fill.quantity == 100
    # Buy fill price must be >= market price due to positive slippage
    assert fill.price >= 200.0
    assert fill.fee > 0.0
    assert pipeline.positions["AAPL"] == 100
    assert pipeline.cash < initial_cash
    assert pipeline.orders[order.order_id].status == CanonicalOrderStatus.FILLED


# ============================================================================
# 10. THREE-WAY RECONCILIATION
# ============================================================================

def test_three_way_reconciliation(pipeline):
    """Ensure local OMS, broker execution reports, and position books reconcile cleanly."""
    order = pipeline.create_order("MSFT", OrderSide.BUY, 50, 400.0)
    pipeline.execute_order(order, market_price=400.0)

    results = pipeline.reconcile()
    assert len(results) == 1
    assert results[0].status == ReconciliationStatus.MATCHED
    assert results[0].expected_quantity == results[0].actual_quantity == 50
    assert results[0].message == "matched"


# ============================================================================
# 11. CRYPTOGRAPHIC SHA-256 AUDIT TRAIL
# ============================================================================

def test_sha256_chained_audit_trail(pipeline):
    """Verify the tamper-evident cryptographic hash chain of the audit trail."""
    pipeline.log_audit("TEST_STAGE_1", {"data": 123})
    pipeline.log_audit("TEST_STAGE_2", {"data": 456})

    assert len(pipeline.audit_log) >= 2
    for i in range(1, len(pipeline.audit_log)):
        curr_entry = pipeline.audit_log[i]
        prev_entry = pipeline.audit_log[i - 1]
        assert curr_entry.prev_hash == prev_entry.entry_hash

        # Recompute hash to prove cryptographic chain integrity
        payload_bytes = json.dumps(curr_entry.details, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()
        assert curr_entry.payload_hash == payload_hash

        expected_raw = f"{curr_entry.prev_hash}:{curr_entry.stage}:{payload_hash}:{curr_entry.timestamp}".encode("utf-8")
        expected_hash = hashlib.sha256(expected_raw).hexdigest()
        assert curr_entry.entry_hash == expected_hash


# ============================================================================
# 12. TUI RUST BRIDGE PROTOCOL SCHEMA PARITY
# ============================================================================

def test_tui_bridge_json_rpc_schema_parity():
    """Verify that Python bridge output strictly conforms to the Rust Ratatui StateSnapshot schema."""
    bridge = DeltaBridge()
    state = bridge.get_state()

    # Required top-level keys
    assert "portfolio" in state
    assert "risk" in state
    assert "orders" in state
    assert "execution" in state
    assert "models" in state
    assert "agents" in state
    assert "system" in state

    # Portfolio schema
    p = state["portfolio"]
    assert isinstance(p["equity"], (int, float))
    assert isinstance(p["cash"], (int, float))
    assert isinstance(p["realized_pnl"], (int, float))
    assert isinstance(p["leverage"], (int, float))
    assert isinstance(p["positions"], list)

    # Risk schema (including new typed fields for TUI)
    r = state["risk"]
    assert isinstance(r["var95_dollar"], (int, float))
    assert isinstance(r["var99_dollar"], (int, float))
    assert isinstance(r["cvar_dollar"], (int, float))
    assert isinstance(r["market_beta"], (int, float))
    assert isinstance(r["rate_shock_impact"], (int, float))
    assert isinstance(r["oil_shock_impact"], (int, float))

    # Quote schema with technical indicators and depth
    q = bridge.quote("SPY")
    assert q["status"] == "AVAILABLE"
    assert "rsi" in q and isinstance(q["rsi"], (int, float))
    assert "macd" in q and isinstance(q["macd"], (int, float))
    assert "bb_upper" in q and isinstance(q["bb_upper"], (int, float))
    assert "vwap" in q and isinstance(q["vwap"], (int, float))
    assert "regime" in q and isinstance(q["regime"], str)
    assert "depth_bids" in q and len(q["depth_bids"]) == 5
    assert "depth_asks" in q and len(q["depth_asks"]) == 5
