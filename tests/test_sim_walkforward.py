"""Simulator + walk-forward gates: determinism, no-leakage, microstructure."""
from __future__ import annotations

from decimal import Decimal


def test_sim_is_deterministic():
    from research.real_loop import market_sim as S

    def run():
        e = S.SimEngine(seed=11)
        e.build_book_from_bar(Decimal("100"), 0.02)
        e.submit("a1", "buy", None, Decimal("250"))
        e.submit("a2", "sell", Decimal("101"), Decimal("50"))
        fills = e.step_until(10_000_000, Decimal("100"))
        m = e.mark(Decimal("100"))
        e.close()
        return [(f.buy_id, f.sell_id, f.price, f.quantity) for f in fills], m["equity"]

    f1, e1 = run()
    f2, e2 = run()
    assert f1 == f2 and e1 == e2 and len(f1) > 0


def test_sim_market_order_crosses_and_pays_fees():
    from research.real_loop import market_sim as S

    e = S.SimEngine(seed=3, fee_bps=Decimal("1.0"))
    e.build_book_from_bar(Decimal("100"), 0.02)
    e.submit("m1", "buy", None, Decimal("150"))
    e.step_until(10_000_000, Decimal("100"))
    m = e.mark(Decimal("100"))
    e.close()
    assert m["position"] > 0
    assert m["cash"] < Decimal("1000000")
    assert m["microstructure"].startswith("synthetic-ladder")
    assert all(f.event_ns >= 50_000 for f in e.fills)  # latency respected


def test_sim_rejects_bad_orders():
    from research.real_loop import market_sim as S

    e = S.SimEngine(seed=1)
    try:
        with __import__("pytest").raises(ValueError):
            e.submit("x", "hold", Decimal("1"), Decimal("1"))
        with __import__("pytest").raises(ValueError):
            e.submit("x", "buy", Decimal("1"), Decimal("0"))
    finally:
        e.close()


def test_purged_splits_have_no_overlap():
    import numpy as np

    from research.real_loop import walkforward as W

    for tr, te in W.purged_splits(300, n_folds=4, horizon=5):
        assert len(set(tr) & set(te)) == 0
        assert te[0] - tr[-1] >= 5 + 1  # horizon purge + embargo gap
        assert len(tr) >= 60


def test_purged_splits_reject_short_history():
    import pytest

    from research.real_loop import walkforward as W

    with pytest.raises(ValueError):
        W.purged_splits(50, n_folds=4, horizon=5)


def test_walk_forward_structure():
    from research.real_loop import features as F
    from research.real_loop import market_data as M
    from research.real_loop import walkforward as W

    bars = M.synthetic_bars("WFTEST", days=300).frame
    feat = F.compute_features(bars, "WFTEST", "wfhash")
    out = W.walk_forward(bars["close"], feat, fwd_days=5, n_folds=3)
    assert out["version"] == "wf-v1" and 1 <= len(out["folds"]) <= 3
    assert out["n_folds"] == len(out["folds"])
    assert set(out["gate"]) == {"pass", "rule"}
    assert all(set(f) == {"n", "gross", "net", "hit", "sharpe"} for f in out["folds"])
