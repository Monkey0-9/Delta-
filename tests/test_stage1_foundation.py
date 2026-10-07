"""Stage-1 Foundation tests (plan A/B/F/D/C): arch docs, DataPoint PIT, labels, quality gate."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
import yaml

from core.domain.canonical import DataPoint, assert_pit_order, pit_join_filter


def _dt(h=10):
    return datetime(2026, 10, 1, h, 0, tzinfo=timezone.utc)


def test_datapoint_order_enforced():
    with pytest.raises(ValueError):
        DataPoint(symbol="AAPL", event_time=_dt(10), publication_time=_dt(9))
    with pytest.raises(ValueError):
        DataPoint(symbol="AAPL", event_time=_dt(10), publication_time=_dt(11),
                  decision_time=_dt(10, ) if False else _dt(10))  # decision 10:00 < avail 11:00
    ok = DataPoint(symbol="AAPL", event_time=_dt(10), publication_time=_dt(11),
                   received_time=_dt(12), decision_time=_dt(13), execution_time=_dt(14))
    assert ok.is_usable_at(_dt(12))
    assert not ok.is_usable_at(_dt(11))


def test_pit_join_filter_drops_future():
    pts = [
        DataPoint(symbol="A", event_time=_dt(9), publication_time=_dt(9)),
        DataPoint(symbol="A", event_time=_dt(15), publication_time=_dt(16)),
    ]
    kept = pit_join_filter(pts, _dt(10))
    assert len(kept) == 1 and kept[0].event_time == _dt(9)
    with pytest.raises(ValueError):
        assert_pit_order(_dt(10), pub=_dt(9))


def test_bar_pit_stamps():
    from data.market.canonical import Bar
    b = Bar(symbol="AAPL", o=100, h=102, l=99, c=101, v=1e6, t_event=1000.0,
            t_pub=1001.0, t_avail=1002.0)
    assert b.is_usable_at(1002.0)
    assert not b.is_usable_at(1001.0)
    with pytest.raises(ValueError):
        Bar(symbol="AAPL", o=100, h=102, l=99, c=101, v=1e6,
            t_event=1002.0, t_pub=1000.0)


def test_label_frame_embargo_and_triple_barrier():
    from data.labels.engine import build_label_frame, triple_barrier, LabelSpec, LabelKind
    idx = pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC")
    close = pd.Series(100 + pd.Series(range(60)).apply(float) * 0.5, index=idx)
    frame = build_label_frame(close)
    assert "future_return_5d" in frame.columns and "triple_barrier" in frame.columns
    # embargo tail must be NA
    assert frame["future_return_5d"].iloc[-1] is pd.NA or pd.isna(frame["future_return_5d"].iloc[-1])
    tb = triple_barrier(close, LabelSpec(kind=LabelKind.TRIPLE_BARRIER, horizon=5))
    assert set(tb.dropna().unique()) <= {0, 1, -1}


def test_quality_gate_fail_raises_and_quarantines():
    from data.quality.gate import gate_report, assert_quality_or_raise, QualityGateBlocked
    bad = gate_report("XYZ", "UNUSABLE", reason="negative prices")
    assert bad.verdict == "FAIL" and bad.quarantined
    with pytest.raises(QualityGateBlocked):
        assert_quality_or_raise(bad)
    good = gate_report("AAA", "EXCELLENT")
    assert good.verdict == "PASS"
    assert_quality_or_raise(good)


def test_pipeline_pit_filter_and_quality_gate():
    from core.canonical_pipeline import CanonicalInstitutionalPipeline as CanonicalPipeline
    pipe = CanonicalPipeline.__new__(CanonicalPipeline)
    import types
    pipe.audit_log = []
    pipe.last_audit_hash = "0" * 16
    pipe._audit = types.MethodType(
        lambda self, k, d: (self.audit_log.append((k, d)), "00")[1], pipe)
    df = pd.DataFrame(
        {"open": [100.0, 101.0], "high": [102.0, 103.0], "low": [99.0, 100.0],
         "close": [101.0, 102.0], "volume": [1e6, 1.1e6]},
        index=pd.DatetimeIndex([_dt(9), _dt(10)]))
    df["t_publication"] = df.index + pd.Timedelta(minutes=15)
    df["t_availability"] = df.index + pd.Timedelta(minutes=30)
    kept = pipe.pit_filter_bars(df, _dt(9) + timedelta(minutes=40))
    assert len(kept) == 1  # only first bar available


def test_system_status_yaml_and_arch_docs():
    root = Path(__file__).resolve().parents[1]
    assert (root / "docs" / "SYSTEM_STATUS.yaml").exists()
    data = yaml.safe_load((root / "docs" / "SYSTEM_STATUS.yaml").read_text())
    assert data["gates"]["R10_production"] is False
    assert data["live_policy"].startswith("ERR_LIVE_PROHIBITED")
    for f in ("SYSTEM_ARCHITECTURE.md", "DATA_ARCHITECTURE.md", "AI_ARCHITECTURE.md",
              "ML_ARCHITECTURE.md", "RESEARCH_ARCHITECTURE.md",
              "EXECUTION_ARCHITECTURE.md", "RISK_ARCHITECTURE.md", "MODEL_LIFECYCLE.md"):
        assert (root / "docs" / f).exists(), f
