"""P2 completion gates: calendar, fundamentals fail-closed, exporter, factors, eval."""
from datetime import datetime, timezone


def test_calendar_labels_regular_and_holiday():
    from data.market.exchange_calendar import ExchangeCalendar
    cal = ExchangeCalendar()
    # 2026-09-30 is Wednesday -> regular at 15:00 UTC (11:00 ET)
    assert cal.session(datetime(2026, 9, 30, 15, 0, tzinfo=timezone.utc)) == "regular"
    # Christmas 2026 -> closed
    assert cal.session(datetime(2026, 12, 25, 15, 0, tzinfo=timezone.utc)) == "closed"
    # Weekend -> closed
    assert cal.session(datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)) == "closed"


def test_session_reconstructor_uses_calendar():
    import time
    from datetime import datetime, timezone
    from data.market_reality import SessionReconstructor
    rec = SessionReconstructor()
    xmas = int(datetime(2026, 12, 25, 15, 0, tzinfo=timezone.utc).timestamp() * 1e9)
    assert rec.label(xmas) == "closed"


def test_value_feature_fail_closed_without_fundamentals():
    import pandas as pd
    from data.market.feature_engine import ValueFeature
    vf = ValueFeature(ratio="pe_missing_xyz")
    df = pd.DataFrame({"close": [100.0, 101.0]})
    try:
        vf.compute(df)
    except Exception as exc:
        assert "STUB_AUDIT" in str(exc) or "fundamental" in str(exc).lower()
        return
    raise AssertionError("ValueFeature must refuse without PIT fundamentals")


def test_fundamentals_provider_pit_refusal():
    from data.market.fundamentals import FundamentalsProvider, FundamentalsUnavailable
    prov = FundamentalsProvider(cache_dir="data/fundamentals_cache_nonexistent_xyz")
    try:
        prov.get("AAPL", "pe", "2026-01-01")
    except FundamentalsUnavailable:
        return
    raise AssertionError("must refuse when no PIT point")


def test_exporter_serves_prometheus():
    from observability.telemetry import Telemetry
    from observability.exporter import serve_background
    import urllib.request
    tel = Telemetry()
    tel.inc("orders", 2)
    tel.inc("fills", 1)
    srv, _th = serve_background(tel, port=18081)
    try:
        body = urllib.request.urlopen("http://127.0.0.1:18081/metrics", timeout=5).read().decode()
    finally:
        srv.shutdown()
    assert "delta_orders_total 2" in body


def test_factor_registry_16_classes():
    import quant.factors.full_library as fl
    assert len(fl.FACTOR_REGISTRY) >= 16
    import pandas as pd
    s = pd.Series(range(1, 120), dtype=float)
    assert fl.momentum(s).values is not None
    assert fl.short_reversal(s).values is not None
    assert fl.liquidity_amihud(s, s + 1e6).values is not None


def test_gates_all_run_no_silent_skip():
    from finance_model.evaluation.delta_gates import run_rule_probes, evaluate_gates, GateId
    probes = run_rule_probes()
    assert set(probes.keys()) == set(GateId)
    for g, (status, ev) in probes.items():
        assert isinstance(ev, str) and ev, g
        assert "probe_not_implemented" not in ev, g
    rep = evaluate_gates("smoke", probes)
    assert rep.results and isinstance(rep.passed, bool)
    assert not rep.passed  # UNPROVEN/FAIL present: honestly not promotable
