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
