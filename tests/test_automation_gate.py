"""P2: automation gate verdicts + best-of-list ranking. Deterministic frames."""
import pandas as pd
from types import SimpleNamespace

from delta_os.brain import DeltaBrain


def _frame(trend="up", n=150, vol=0.004, seed=11):
    import numpy as np

    rng = np.random.default_rng(seed)
    drift = {"up": 0.0015, "down": -0.004, "flat": 0.0}[trend]
    rets = drift + vol * rng.standard_normal(n)
    closes = 100.0 * np.cumprod(1 + rets)
    return pd.DataFrame(
        {"open": closes, "high": closes * 1.005, "low": closes * 0.995,
         "close": closes, "volume": 1_000_000.0},
        index=pd.date_range("2024-01-01", periods=n, tz="UTC"),
    )


class _Router:
    def __init__(self, frames, tier="TIER1"):
        self.frames = frames
        self.tier = tier

    def quote(self, symbol, days=150):
        df = self.frames.get(symbol.upper(), _frame("flat"))
        return SimpleNamespace(
            frame=df, provenance=SimpleNamespace(tier=self.tier, badge=""))


def _brain(frames, tier="TIER1"):
    b = DeltaBrain.__new__(DeltaBrain)
    b.data_router = _Router(frames, tier)  # type: ignore[assignment]
    return b


def test_buy_bull_allows_and_buy_bear_holds():
    b = _brain({"BULL": _frame("up"), "BEAR": _frame("down")})
    g = b.gate_automation("BULL", "buy")
    assert g["verdict"] == "ALLOW", g
    g2 = b.gate_automation("BEAR", "buy")
    assert g2["verdict"] == "HOLD", g2
    assert any("opposes BUY" in r or "drift" in r for r in g2["reasons"])


def test_sell_strength_holds():
    b = _brain({"BULL": _frame("up")})
    g = b.gate_automation("BULL", "sell")
    assert g["verdict"] == "HOLD", g


def test_synthetic_tier_blocks():
    b = _brain({"BULL": _frame("up")}, tier="TIER3-SYNTH")
    g = b.gate_automation("BULL", "buy")
    assert g["verdict"] == "BLOCK"
    assert "TIER1/TIER2" in g["reasons"][0]


def test_rank_alternatives_picks_strongest_for_buy():
    b = _brain({"AAA": _frame("up", seed=1), "BBB": _frame("down", seed=2)})
    r = b.rank_alternatives(["AAA", "BBB"], "buy")
    assert r["pick"] == "AAA", r
    assert [x["symbol"] for x in r["ranking"]] == ["AAA", "BBB"]
    r2 = b.rank_alternatives(["AAA", "BBB"], "sell")
    assert r2["pick"] == "BBB", r2


def test_rank_never_invents_and_skips_unreadable():
    b = _brain({"AAA": _frame("up")}, tier="TIER3-SYNTH")
    r = b.rank_alternatives(["AAA", "ZZZ"], "buy")
    assert r["pick"] is None
    assert {s["symbol"] for s in r["skipped"]} == {"AAA", "ZZZ"}
    assert "no tradable alternate" in r["rationale"]
