"""Live-readiness gate: real data only. No seeds, no fakes, no placeholders.

Fails if any live-critical path can fabricate market data:
- legacy router must default synthetic OFF (explicit opt-in only)
- real-time adapter must raise (never return an empty placeholder quote)
- sim matching engine must be deterministic (same seed -> same fills)
- scenario manifests must carry content hashes + verified=False until replay files land
- terminal safety must refuse orders on stale/synthetic frames
- research path must fail closed in DATA_MODE=LIVE without a feed
"""
from __future__ import annotations


def test_legacy_router_synthetic_off_by_default():
    import delta_compat  # noqa
    from data.router import DataRouter
    from unittest.mock import MagicMock
    r = DataRouter(MagicMock())
    assert r.synthetic_enabled is False
    r.enable_synthetic_offline()
    assert r.synthetic_enabled is True


def test_realtime_adapter_never_returns_placeholder_quote():
    import asyncio
    import delta_compat  # noqa
    from data.market.adapters import RealTimeAdapter
    import pytest

    async def go():
        a = RealTimeAdapter(api_key="test-key")
        with pytest.raises(NotImplementedError):
            await a.get_real_time_quote("SPY")
    asyncio.run(go())


def test_sim_matching_engine_deterministic_per_seed():
    import delta_compat  # noqa
    from simulation.market_simulator.matching_engine import MatchingEngine
    from simulation.market_simulator.order_book import LimitOrder, OrderSide
    from datetime import datetime, timezone

    def run():
        e = MatchingEngine("SPY", "SIM", seed=7)
        e.order_book.add_limit_order(LimitOrder("r1", OrderSide.SELL, 100.0, 50.0,
                                                datetime.now(timezone.utc), "SIM"))
        e.order_book.add_limit_order(LimitOrder("r2", OrderSide.SELL, 100.0, 50.0,
                                                datetime.now(timezone.utc), "SIM"))
        res = e.submit_limit_order(LimitOrder("t1", OrderSide.BUY, 100.0, 80.0,
                                              datetime.now(timezone.utc), "SIM"))
        return [(f.price, f.quantity) for f in res.fills]
    assert run() == run()


def test_scenario_manifests_honest_hashes():
    from data.scenarios.historical import SCENARIOS, get
    assert len(SCENARIOS) >= 6
    s = get("HIST-2020-COVID")
    assert s.dataset_hash.startswith("manifest-sha:")
    assert s.verified is False
    assert s.microstructure == "bar-resampled-l2-NOT-vendor-ticks"


def test_terminal_refuses_orders_on_synthetic_frames():
    from delta_os.data_router import QuoteFrame, Provenance
    from delta_os.safety import SafetyState, SafetyError
    import pandas as pd
    import pytest
    frame = pd.DataFrame({"close": [100.0]})
    synth = QuoteFrame(frame, Provenance("TIER3-SYNTH", "[SYNTHETIC SIMULATION ONLY]", "SPY", "now"))
    with pytest.raises(SafetyError):
        SafetyState().check_fresh(synth.provenance)
    stale = QuoteFrame(frame, Provenance("TIER3-CACHE", "[STALE DATA]", "SPY", "now"))
    with pytest.raises(SafetyError):
        SafetyState().check_fresh(stale.provenance)
    fresh = QuoteFrame(frame, Provenance("TIER1", "", "SPY", "now"))
    SafetyState().check_fresh(fresh.provenance)  # must not raise


def test_research_path_fails_closed_without_feed(monkeypatch):
    monkeypatch.setenv("DATA_MODE", "LIVE")
    monkeypatch.setenv("DELTA_TEST_NO_NETWORK", "1")
    import delta_compat  # noqa
    from research.real_loop.market_data import fetch_bars, MarketDataUnavailable
    import pytest
    with pytest.raises(MarketDataUnavailable):
        fetch_bars(["ZZZ-INVALID-SYMBOL-XYZ"], 30)
