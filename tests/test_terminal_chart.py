"""Tests for DELTA In-Terminal Financial Visualizations."""
from __future__ import annotations

import pytest
from delta_os.terminal_chart import (
    CandleBar,
    render_candlestick_chart,
    render_depth_ladder,
    render_rsi_subplot,
)


def test_empty_candlestick_chart():
    res = render_candlestick_chart([], "AAPL")
    assert "UNAVAILABLE" in res or "Empty" in res


def test_candlestick_chart_rendering():
    candles = [
        {"open": 100.0, "high": 105.0, "low": 98.0, "close": 104.0, "volume": 1000.0},
        {"open": 104.0, "high": 108.0, "low": 102.0, "close": 107.0, "volume": 1500.0},
        {"open": 107.0, "high": 109.0, "low": 101.0, "close": 103.0, "volume": 1200.0},
    ]
    out = render_candlestick_chart(candles, "NVDA", width=40, height=8, provenance="TIER1")
    assert "NVDA" in out
    assert "[TIER1]" in out
    assert "VOLUME" in out
    # Verify wicks and body blocks
    assert "│" in out
    assert "█" in out or "░" in out


def test_rsi_subplot():
    rsi_series = [45.0, 52.0, 68.0, 72.0, 75.0, 71.0, 65.0]
    out = render_rsi_subplot(rsi_series, width=30, height=5)
    assert "RSI (14)" in out
    assert "Overbought: 70" in out
    assert "Oversold: 30" in out
    assert "●" in out


def test_depth_ladder():
    bids = [{"price": 100.0, "size": 200}, {"price": 99.8, "size": 400}]
    asks = [{"price": 100.2, "size": 250}, {"price": 100.4, "size": 500}]
    out = render_depth_ladder(bids, asks, width=50, provenance="SYNTHETIC")
    assert "ORDER BOOK DEPTH LADDER" in out
    assert "Spread:" in out
    assert "100.00" in out
    assert "100.20" in out
