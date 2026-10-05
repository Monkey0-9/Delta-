"""P3: crash hedge sizing + dip ladder. Advisory only; execution via gated /trade."""
import sys

import pytest

sys.path.insert(0, "tests")
from test_automation_gate import _frame, _Router  # noqa: E402

from delta_os.brain import DeltaBrain
from delta_os.repl import Terminal


def _brain(frames, tier="TIER1"):
    b = DeltaBrain.__new__(DeltaBrain)
    b.data_router = _Router(frames, tier)  # type: ignore[assignment]
    return b


def _oversold(n=150, seed=3):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    flat = 1 + 0.0005 * rng.standard_normal(n - 20)
    crash = flat[-1] * np.cumprod(1 - 0.012 + 0.004 * rng.standard_normal(20))
    c = np.concatenate([flat, crash]) * 100.0
    return pd.DataFrame(
        {"open": c, "high": c * 1.005, "low": c * 0.995,
         "close": c, "volume": 2_000_000.0},
        index=pd.date_range("2024-01-01", periods=n, tz="UTC"),
    )


def test_hedge_plan_sizes_puts():
    b = _brain({"XYZ": _frame("up")})
    h = b.hedge_plan("XYZ", 1000.0)
    assert h["contracts"] >= 1 and h["premium_dollars"] > 0
    assert h["strike"] < h.get("spot_fallback", 1e18)
    assert "execute_via" in h and h["data_tier"] == "TIER1"


def test_hedge_refuses_without_position():
    b = _brain({"XYZ": _frame("up")})
    assert "error" in b.hedge_plan("XYZ", 0.0)


def test_dip_ladder_only_when_oversold():
    b = _brain({"DIP": _oversold(), "CALM": _frame("up")})
    d = b.dip_plan("DIP", 100_000.0)
    assert d["action"].startswith("BUY LOW ladder")
    assert len(d["tranches"]) == 3
    assert all(t["qty"] >= 0 for t in d["tranches"])
    d2 = b.dip_plan("CALM", 100_000.0)
    assert d2["action"] == "NO DIP (not oversold)"


def test_protect_dipbuy_honest_without_positions(monkeypatch):
    t = Terminal()
    t.brain.data_router = _Router({"DIP": _oversold()})  # type: ignore[assignment]
    out, _ = t.handle("/protect DIP")
    assert "No live long position" in out
    out2, _ = t.handle("/dipbuy DIP")
    assert "UNAVAILABLE: ledger equity unreadable" in out2 or "DIP LADDER" in out2
