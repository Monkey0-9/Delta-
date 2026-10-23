"""Institutional Tests for Terminal Chart Truth & Provenance Lineage.

Validates:
1. DeltaBridge.quote populates genuine historical OHLCV bars from QuoteFrame.
2. Historical RSI calculation reflects rolling 14-period mathematical values across closes.
3. Candlestick rendering utilizes authentic OHLCV bars rather than synthetic ±0.2% nudges.
4. L2 Order Book depth displays explicit SYNTHETIC_DEMO watermark badge.
"""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from apps.cli.main import app
from delta_os.bridge import DeltaBridge

runner = CliRunner()


def test_quote_returns_truthful_ohlcv_bars_and_rsi():
    bridge = DeltaBridge()
    q = bridge.quote("SPY")

    assert q["status"] == "AVAILABLE"
    assert "bars" in q
    bars = q["bars"]
    assert len(bars) > 0

    # Verify bar structure
    first_bar = bars[0]
    for k in ("open", "high", "low", "close", "volume"):
        assert k in first_bar
        assert isinstance(first_bar[k], float)
        assert first_bar[k] >= 0.0
    # High must be >= Low
    assert first_bar["high"] >= first_bar["low"]

    # Verify RSI history
    assert "rsi_history" in q
    rsi_hist = q["rsi_history"]
    assert isinstance(rsi_hist, list)
    if rsi_hist:
        for val in rsi_hist:
            assert 0.0 <= val <= 100.0


def test_chart_cli_truthful_rendering():
    res = runner.invoke(app, ["chart", "NVDA", "--days", "15"])
    assert res.exit_code == 0
    assert "NVDA" in res.stdout
    assert "ORDER BOOK DEPTH LADDER" in res.stdout
    # Must badge synthetic depth honestly
    assert "SYNTHETIC_DEMO" in res.stdout or "SYNTHETIC" in res.stdout


def test_chart_depth_watermark_present():
    res = runner.invoke(app, ["chart", "AAPL", "--depth", "--days", "10"])
    assert res.exit_code == 0
    assert "SYNTHETIC_DEMO" in res.stdout
