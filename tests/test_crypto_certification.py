"""Crypto Feed & Execution Adapter Certification Test Suite.

Verifies:
- Live and offline fallback quotes with accurate provenance tags
- Satoshi / fractional precision math
- Idempotency deduplication
- Cash and position accounting for BUY and SELL
- Rejection on insufficient cash or position
- Fail-closed live execution refusal (ERR_LIVE_PROHIBITED)
"""
import pytest
from unittest.mock import MagicMock, patch

from data.providers.crypto_feed import GlobalCryptoFeed, CryptoQuote
from execution.adapters.crypto_adapter import CryptoAdapter, CryptoPosition


def test_crypto_feed_offline_fallback():
    feed = GlobalCryptoFeed(timeout=0.01)
    # Even if offline or network blocked, returns synthetic baseline quote with SYNTHETIC_OFFLINE
    quote = feed.get_quote("BTC/USD")
    assert quote.symbol == "BTC/USD"
    assert quote.price > 0.0
    assert quote.bid <= quote.price <= quote.ask
    assert quote.provenance in ("TIER2_CRYPTO_LIVE", "SYNTHETIC_OFFLINE")


def test_crypto_adapter_paper_lifecycle():
    adapter = CryptoAdapter(initial_usd=100_000.0)
    st = adapter.status()
    assert st["broker"] == "crypto_247"
    assert st["connected"] is True
    assert st["cash"] == 100_000.0
    assert st["mode"] == "PAPER_SIMULATION"

    # Buy 0.5 BTC at price 60,000 (notional = 30,000)
    res = adapter.submit(
        symbol="BTC/USD",
        side="BUY",
        quantity=0.5,
        price=60_000.0,
        idempotency_key="CRYPTO-ORDER-001",
    )
    assert res["status"] == "FILLED"
    assert res["filled"] == 0.5
    assert adapter.cash == 70_000.0
    assert "BTC/USD" in adapter.positions_map
    assert adapter.positions_map["BTC/USD"].quantity == 0.5

    # Idempotent re-submission returns duplicate record without double deduction
    res_dup = adapter.submit(
        symbol="BTC/USD",
        side="BUY",
        quantity=0.5,
        price=60_000.0,
        idempotency_key="CRYPTO-ORDER-001",
    )
    assert res_dup["duplicate"] is True
    assert adapter.cash == 70_000.0

    # Sell 0.2 BTC at 65,000 (proceeds = 13,000)
    res_sell = adapter.submit(
        symbol="BTC/USD",
        side="SELL",
        quantity=0.2,
        price=65_000.0,
        idempotency_key="CRYPTO-ORDER-002",
    )
    assert res_sell["status"] == "FILLED"
    assert adapter.cash == 83_000.0
    assert abs(adapter.positions_map["BTC/USD"].quantity - 0.3) < 1e-8


def test_crypto_adapter_insufficient_balance():
    adapter = CryptoAdapter(initial_usd=1_000.0)
    # Attempt to buy 1 BTC at $60,000
    res = adapter.submit(
        symbol="BTC/USD",
        side="BUY",
        quantity=1.0,
        price=60_000.0,
    )
    assert res["status"] == "REJECTED"
    assert "Insufficient USD cash" in res["reason"]

    # Attempt to sell unowned coin
    res_sell = adapter.submit(
        symbol="ETH/USD",
        side="SELL",
        quantity=1.0,
        price=3_000.0,
    )
    assert res_sell["status"] == "REJECTED"
    assert "Insufficient ETH/USD position" in res_sell["reason"]


def test_crypto_adapter_live_armed_fail_closed():
    adapter = CryptoAdapter()
    adapter.live_armed = True
    with pytest.raises(PermissionError, match="ERR_LIVE_PROHIBITED"):
        adapter.submit("BTC/USD", "BUY", 0.1, 60_000.0)
