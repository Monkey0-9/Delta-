"""P4: forecast/regime honesty envelope + guarded detector consult."""
import sys

sys.path.insert(0, "tests")
from test_automation_gate import _frame, _Router  # noqa: E402

from delta_os.brain import DeltaBrain


def _brain(frames, tier="TIER1"):
    b = DeltaBrain.__new__(DeltaBrain)
    b.data_router = _Router(frames, tier)  # type: ignore[assignment]
    return b


def test_forecast_carries_honesty_envelope():
    b = _brain({"T": _frame("up")})
    f = b.forecast_direction("T")
    for k in ("model", "model_version", "calibration", "confidence",
              "evidence", "provenance", "data_tier"):
        assert k in f, k
    assert "uncalibrated" in f["calibration"]
    assert f["confidence"] <= 0.5


def test_forecast_abstains_on_stale_inputs():
    b = _brain({"T": _frame("up")}, tier="TIER3-SYNTH")
    f = b.forecast_direction("T")
    assert "error" in f and "ABSTAIN" in f["error"], f


def test_forecast_abstains_when_edge_is_noise(monkeypatch):
    import delta_os.brain as bmod

    b = _brain({"T": _frame("flat")})
    # Flat market: RSI ~50, MACD ~0 -> drift ~= -80bps vs vol -> coin flip.
    f = b.forecast_direction("T")
    prob = f.get("probability_positive_return_pct", 50.0)
    if 40.0 <= prob <= 60.0:
        assert f["direction"].startswith("ABSTAIN"), f
        assert "NO ACTION" in f["turn_recommendation"]
    else:
        assert not f["direction"].startswith("ABSTAIN"), f


def test_regime_consult_labeled_and_nonbreaking():
    b = _brain({"SPY": _frame("down"), "T": _frame("down")})
    r = b.evaluate_portfolio_regime(positions={"T": 10.0})
    assert r["regime_source"] in ("quant-regime", "heuristic")
    assert "model_version" in r and "calibration" in r
    assert isinstance(r["crash_probability_pct"], float)


def test_detector_unreachable_falls_back_labeled(monkeypatch):
    import delta_os.brain as bmod

    b = _brain({"SPY": _frame("flat"), "T": _frame("flat")})
    monkeypatch.setitem(__import__("sys").modules, "quant.regime.detector", None)
    r = b.evaluate_portfolio_regime(positions={"T": 5.0})
    assert r["regime_source"] == "heuristic"
    assert r["detector_regime"] is None


def test_chat_never_crashes_on_unreadable_symbol():
    b = _brain({}, tier="TIER3-SYNTH")
    out = b.chat("what do you think of NVDA")
    # Chat analyses (refusal lives at the execution gate, tested elsewhere).
    assert "Quantitative Analysis" in out
    out2 = b.chat("some random question about taxes")
    assert "DELTA" in out2


def test_chat_unavailable_on_empty_frame():
    import pandas as pd

    short = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0],
         "volume": [10.0]},
        index=pd.date_range("2024-01-01", periods=1, tz="UTC"),
    )
    b = _brain({"NVDA": short})
    assert "UNAVAILABLE" in b.chat("what do you think of NVDA")


def test_forecast_log_and_calibration_resolution(tmp_path, monkeypatch):
    import json as _json
    from datetime import datetime, timedelta, timezone

    from delta_os import brain as bmod
    from delta_os.brain import DeltaBrain

    log = tmp_path / "forecast_log.jsonl"
    monkeypatch.setattr(bmod.DeltaBrain, "_forecast_log_path",
                        lambda self: str(log))
    b = DeltaBrain.__new__(DeltaBrain)
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    rows = [
        {"ts": past, "symbol": "T", "horizon_days": 5,
         "direction": "BULLISH (UP)", "prob_positive": 0.7},
        {"ts": past, "symbol": "T", "horizon_days": 5,
         "direction": "BEARISH (DOWN)", "prob_positive": 0.3},
        {"ts": datetime.now(timezone.utc).isoformat(), "symbol": "T",
         "horizon_days": 30, "direction": "BULLISH (UP)",
         "prob_positive": 0.8},
    ]
    log.write_text("\n".join(_json.dumps(r) for r in rows) + "\n",
                   encoding="utf-8")
    prices = iter([100.0, 110.0, 100.0, 90.0])  # (p0,p1) per resolved entry
    lookup = lambda sym, day: next(prices)  # noqa: E731
    cal = b.forecast_calibration(price_lookup=lookup)
    assert cal["n_logged"] == 3 and cal["n_resolved"] == 2, cal
    assert cal["accuracy"] == 1.0, cal  # both calls correct
    assert cal["mean_prob"] == 0.5
    assert cal["ece_single_bin"] == 0.5, cal


def test_calibration_empty_log_shape(tmp_path, monkeypatch):
    from delta_os import brain as bmod
    from delta_os.brain import DeltaBrain

    monkeypatch.setattr(bmod.DeltaBrain, "_forecast_log_path",
                        lambda self: str(tmp_path / "missing.jsonl"))
    b = DeltaBrain.__new__(DeltaBrain)
    cal = b.forecast_calibration(price_lookup=lambda s, d: None)
    assert cal["n_resolved"] == 0 and cal["accuracy"] is None


def test_binned_ece_curve(tmp_path, monkeypatch):
    import json as _json
    from datetime import datetime, timedelta, timezone

    from delta_os import brain as bmod
    from delta_os.brain import DeltaBrain

    log = tmp_path / "forecast_log.jsonl"
    monkeypatch.setattr(bmod.DeltaBrain, "_forecast_log_path",
                        lambda self: str(log))
    b = DeltaBrain.__new__(DeltaBrain)
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    rows = []
    # 4 correct high-prob + 4 correct low-prob(=bearish right) => ECE ~0.
    for i in range(4):
        rows.append({"ts": past, "symbol": "T", "horizon_days": 5,
                     "direction": "BULLISH (UP)", "prob_positive": 0.8})
        rows.append({"ts": past, "symbol": "T", "horizon_days": 5,
                     "direction": "BEARISH (DOWN)", "prob_positive": 0.2})
    log.write_text("\n".join(_json.dumps(r) for r in rows) + "\n",
                   encoding="utf-8")
    seq = [100.0, 110.0, 100.0, 90.0] * 4  # (up, down) per bull/bear pair
    it = iter(seq)
    cal = b.forecast_calibration(price_lookup=lambda s, d: next(it))
    assert cal["n_resolved"] == 8, cal
    assert cal["accuracy"] == 1.0
    # Perfect accuracy at p=0.8/0.2 is miscalibrated by construction:
    # |1-0.8|*1/2 + |1-0.2|*1/2 = 0.5. Calibration != accuracy.
    assert cal["ece_binned"] == 0.5, cal
    assert len(cal["bins"]) == 5
    assert sum(bn["n"] for bn in cal["bins"]) == 8
    by_n = sorted((bn["n"], bn["accuracy"], bn["mean_prob"]) for bn in cal["bins"] if bn["n"])
    assert by_n == [(4, 1.0, 0.2), (4, 1.0, 0.8)], by_n
    empty = [bn for bn in cal["bins"] if bn["n"] == 0]
    assert len(empty) == 3 and all(bn["accuracy"] is None for bn in empty)
