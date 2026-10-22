"""Tests for DELTA Pre-Trade Mistake Interceptor & Closed-Loop Learning."""
from __future__ import annotations

import pytest
from delta_os.pretrade_interceptor import PreTradeInterceptor
from learning.closed_loop import ClosedLoopLearner, FailureType


def test_interceptor_clean_order():
    interceptor = PreTradeInterceptor()
    warnings = interceptor.inspect_order(
        symbol="MSFT",
        side="BUY",
        quantity=50,
        price=300.0,
        regime="NEUTRAL",
        rsi=52.0,
        spread_bps=2.0,
    )
    assert len(warnings) == 0


def test_interceptor_blocks_toxic_regime_momentum():
    interceptor = PreTradeInterceptor()
    # Buying overbought asset (RSI > 75) in BEAR_CRASH regime is a documented failure mode
    warnings = interceptor.inspect_order(
        symbol="TSLA",
        side="BUY",
        quantity=100,
        price=200.0,
        regime="BEAR_CRASH",
        rsi=82.0,
        strict_veto=True,
    )
    assert len(warnings) >= 1
    assert any(w.blocked for w in warnings)
    assert any(w.failure_type == FailureType.REGIME_ERROR.value for w in warnings)


def test_interceptor_learns_from_trade_experience():
    learner = ClosedLoopLearner()
    interceptor = PreTradeInterceptor(learner=learner)

    # Ingest a losing trade
    interceptor.learn_from_trade(
        trade_id="TR-999",
        symbol="AAPL",
        predicted_return=0.02,
        realized_return=-0.045,  # -4.5% loss
        execution_shortfall_bps=25.0,
        vwap_slippage_bps=12.0,
        failure_type="MODEL_ERROR",
        details="AAPL breakout failed at resistance",
    )

    # Now inspect a new order on AAPL
    warnings = interceptor.inspect_order(
        symbol="AAPL",
        side="BUY",
        quantity=100,
        price=180.0,
        regime="NEUTRAL",
        rsi=50.0,
        strict_veto=False,
    )
    assert len(warnings) >= 1
    w = warnings[0]
    assert w.symbol == "AAPL"
    assert "Prior loss on AAPL" in w.lesson
    assert w.past_loss_pct > 4.0

    # Test Bayesian risk penalty
    penalty = interceptor.get_bayesian_risk_penalty("AAPL")
    assert penalty < 1.0  # Reduced due to prior loss

    # Test mistakes ledger
    ledger = interceptor.get_mistakes_ledger()
    assert len(ledger) >= 1
    assert ledger[0]["symbol"] == "AAPL"
    assert ledger[0]["status"] == "LOSS"
