"""Mistake tolerance: bad inputs fail loudly or degrade gracefully, never silently."""
from __future__ import annotations

from decimal import Decimal

import pytest


def test_accel_rejects_bad_cov():
    import numpy as np

    from native import accel

    with pytest.raises(ValueError):
        accel.erc_sweep(np.eye(3), np.ones(2))
    with pytest.raises(ValueError):
        accel.erc_sweep(np.full((2, 2), np.nan), np.ones(2))
    assert accel.returns(np.array([100.0])) .tolist() == []
    m, s = accel.roll_mean_std(np.array([]), 5)
    assert len(m) == 0


def test_lob_coerces_and_rejects():
    from native import lob

    assert lob._ticks(100) == 100 * lob.SCALE  # int coerced, not crashed
    with pytest.raises(ValueError):
        lob._ticks(Decimal("NaN"))
    with pytest.raises(ValueError):
        lob._ticks(Decimal("-5"))


def test_sim_rejects_nonfinite():
    from research.real_loop import market_sim as S

    e = S.SimEngine(seed=1)
    try:
        with pytest.raises(ValueError):
            e.build_book_from_bar(Decimal("NaN"), 0.02)
        with pytest.raises(ValueError):
            e.submit("x", "buy", Decimal("NaN"), Decimal("1"))
        with pytest.raises(ValueError):
            e.submit("x", "buy", Decimal("-1"), Decimal("1"))
    finally:
        e.close()


def test_event_backtest_rejects_garbage():
    import pandas as pd

    from research.real_loop import event_backtest as EB
    from research.real_loop import market_data as M

    bars = M.synthetic_bars("TOL", days=120).frame
    tgt = pd.Series(0.0, index=bars.index)
    with pytest.raises(ValueError):
        EB.run_event_backtest(bars.iloc[:10], tgt.iloc[:10], seed=1)  # < warmup
    bad = bars.copy()
    bad.iloc[5, bad.columns.get_loc("close")] = -3.0
    with pytest.raises(ValueError):
        EB.run_event_backtest(bad, tgt, seed=1)


def test_datasets_reject_empty_and_verify_tamper(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_MODE", "SIMULATION")
    import json

    from research.real_loop import datasets as D

    with pytest.raises(ValueError):
        D.build_dataset([], days=100)
    ds, _ = D.build_dataset(["AA.PL"], days=120, dataset_id="T1")
    assert ds.verify()
    reg = str(tmp_path / "reg.jsonl")
    D.save(ds, reg)
    assert D.load("T1", reg).verify()
    rec = json.loads(open(reg, encoding="utf-8").read())
    rec["fingerprint"] = "DS-TAMPERED000"
    open(reg, "w", encoding="utf-8").write(json.dumps(rec))
    with pytest.raises(ValueError):
        D.load("T1", reg)
    with pytest.raises(ValueError):
        D.load("NOPE", reg)


def test_python_matcher_cancel_replace_parity():
    from execution.matching.engine import PriceTimeMatcher

    m = PriceTimeMatcher()
    assert m.add("s1", "sell", Decimal("100"), Decimal("5")) == []
    assert m.cancel("s1") is True
    assert m.cancel("s1") is False
    assert m.add("b1", "buy", Decimal("100"), Decimal("5")) == []
    assert m.replace("b1", "sell", Decimal("99"), Decimal("5")) == []
    fills = m.add("b9", "buy", Decimal("99"), Decimal("2"))
    assert [(f.buy_id, f.sell_id) for f in fills] == [("b9", "b1")]


def test_shadow_rejects_short_history(monkeypatch):
    monkeypatch.setenv("DATA_MODE", "SIMULATION")
    import pytest as _pt

    from scripts.shadow_track import shadow_symbol

    with _pt.raises(ValueError):
        shadow_symbol("AA.PL", days=50, horizon="week")
