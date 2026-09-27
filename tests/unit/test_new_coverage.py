from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4


def test_storage_database_migrations_and_catalog(tmp_path):
    from storage.database.connection import Database
    from storage.database.migrations import SCHEMA_VERSION
    from storage.repositories.catalog import PersistentCatalog

    db = Database(tmp_path / "delta.db")
    conn = db.connect()
    assert db.migrate() == SCHEMA_VERSION
    db.close()

    cat = PersistentCatalog(tmp_path / "delta.db")
    cat.register("bars_1d", "abc123", version=2)
    assert cat.get("bars_1d") == "abc123"
    assert cat.describe("bars_1d")["version"] == 2
    assert "bars_1d" in cat.list()


def test_calendar_half_days_and_sessions():
    from data.ingestion.calendars import TradingCalendar

    cal = TradingCalendar(
        holidays=frozenset({date(2026, 1, 1)}),
        half_days=frozenset({date(2026, 7, 3)}),
    )
    assert not cal.is_trading_day(date(2026, 1, 1))
    assert cal.is_half_day(date(2026, 7, 3))
    assert cal.session_close_utc(date(2026, 7, 3)) == time(17, 0)
    assert cal.session_close_utc(date(2026, 7, 6)) == time(20, 0)
    assert cal.sessions_between(date(2026, 1, 5), date(2026, 1, 9)) == 5


def test_corporate_actions_as_of_and_ohlcv():
    from data.ingestion.corporate_actions import (
        BarOHLCV,
        CorporateAction,
        adjust_ohlcv,
        apply_actions_as_of,
    )

    split = CorporateAction("AAA", "split", Decimal("0.5"), "2026-02-01")
    prices = (Decimal("100"), Decimal("50"))
    dates = ("2026-01-15", "2026-02-15")
    assert apply_actions_as_of(prices, dates, (split,)) == (Decimal("50.0"), Decimal("50"))
    bars = (BarOHLCV(Decimal("100"), Decimal("110"), Decimal("90"), Decimal("105"), Decimal("1000"), "2026-01-15"),)
    adj = adjust_ohlcv(bars, (split,))
    assert adj[0].close == Decimal("52.5") and adj[0].volume == Decimal("2000")


def test_pit_correction_and_persistence(tmp_path):
    from data.point_in_time.store import PointInTimeStore, StoredEvent

    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store = PointInTimeStore()
    store.append(StoredEvent("e1", t0, t0, t0, "src", '{"p":1}'))
    store.correct(StoredEvent("e1", t0, t0 + timedelta(seconds=1), t0, "src", '{"p":2}'))
    assert store.as_of(t0)[0].payload == '{"p":2}'
    assert store.persist(str(tmp_path / "pit.db")) == 1


def test_signal_library():
    from quant.signals.signal_library import rsi, momentum, get_signal_library

    prices = tuple(Decimal(str(100 + i)) for i in range(60))
    rsi_value = rsi(prices)
    assert isinstance(rsi_value, Decimal)
    assert Decimal("0") <= rsi_value <= Decimal("100")
    
    # Test the new signal library
    lib = get_signal_library()
    assert len(lib.list_signals()) > 0
    
    # Test momentum computation
    mom = momentum(prices, 20)
    assert isinstance(mom, Decimal)


def test_factor_library():
    from quant.factors.library import combine_factors, quality_factor, value_factor

    v = value_factor({"A": Decimal("10"), "B": Decimal("20")})
    assert v["A"] > v["B"]
    q = quality_factor({"A": Decimal("0.2"), "B": Decimal("0.1")}, {"A": Decimal("0.05"), "B": Decimal("0.2")})
    assert q["A"] > q["B"]
    c = combine_factors(({"A": Decimal("0.2")}, {"A": Decimal("0.6")}))
    assert c["A"] == Decimal("0.4")


def test_calibration_metrics():
    from quant.forecasting.calibrated import calibration_report
    from quant.forecasting.metrics import IsotonicRecalibrator, PlattRecalibrator, log_loss

    probs = tuple(Decimal(str(p)) for p in (0.05, 0.05, 0.95, 0.95))
    outcomes = (0, 0, 1, 1)
    assert log_loss(probs, outcomes) > Decimal("0")
    assert calibration_report(probs, outcomes).passed
    assert IsotonicRecalibrator().fit(probs, outcomes).predict(Decimal("0.8")) >= Decimal("0")
    assert PlattRecalibrator().fit(probs, outcomes).predict(Decimal("0.8")) >= Decimal("0")


def test_mean_variance_optimizer():
    from quant.portfolio.optimizer import AssetForecast, MeanVarianceOptimizer

    fc = (
        AssetForecast(uuid4(), Decimal("0.10"), Decimal("0.2")),
        AssetForecast(uuid4(), Decimal("0.05"), Decimal("0.1")),
    )
    cov = ((Decimal("0.04"), Decimal("0.005")), (Decimal("0.005"), Decimal("0.01")))
    res = MeanVarianceOptimizer().optimize(fc, cov)
    assert abs(sum(w.weight for w in res.weights) - Decimal("1")) < Decimal("1e-9")


def test_strategy_harness_and_algos():
    from datetime import timezone
    from simulation.backtest.config import BacktestConfig
    from simulation.backtest.strategy import SignalStrategy, run_strategy_backtest
    from simulation.replay.event import ReplayEvent
    from execution.algorithms.advanced import arrival_price, is_schedule, pov_schedule, twap_schedule
    from decimal import Decimal as D

    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = tuple(ReplayEvent(t0 + timedelta(seconds=i), i, f"e{i}") for i in range(4))
    prices = (D("10"), D("11"), D("12"), D("13"))
    sig = (D("1"), D("-1"), D("1"), D("-1"))
    ctx = run_strategy_backtest(
        config=BacktestConfig(initial_cash=D("10000")),
        events=events,
        strategy=SignalStrategy(signal=sig, prices=prices),
    )
    assert ctx.fills == 2
    assert twap_schedule(D("100"), 4).benchmark == "TWAP"
    assert is_schedule(D("100"), 4).benchmark == "IS"
    assert pov_schedule(D("100"), (D("50"), D("50")), D("0.1")).benchmark == "POV"
    assert arrival_price((D("1"), D("1")), (D("10"), D("12")), D("10")) == D("1")


def test_llm_router_prompts_finbench():
    from decimal import Decimal as D
    from finance_model.calibration import abstention_report
    from finance_model.finbench import FIN_BENCH_DIMS, finbench_dataset, score_suite
    from finance_model.prompts import DEFAULT_ANALYSIS_PROMPT, PromptRegistry
    from finance_model.router import LocalRouter

    router = LocalRouter()
    dec = router.route(complexity=D("0.1"), tokens=100, tool="quant.read")
    assert dec.model == "delta-local-small"
    try:
        router.route(complexity=D("0.1"), tokens=10, tool="broker.execute")
        raise AssertionError("must reject broker tool")
    except ValueError:
        pass
    reg = PromptRegistry()
    reg.register(DEFAULT_ANALYSIS_PROMPT)
    assert "AAA" in reg.get("financial_analysis").render(
        {"instrument": "AAA", "horizon": "1M", "expected_return": "1%", "evidence": "[ev-1]"})
    cases = finbench_dataset()
    assert len(cases) == len(FIN_BENCH_DIMS) == 12
    answers = {c.case_id: (c.expected, c.evidence_ids) for c in cases}
    assert all(s.score >= D("0.5") for s in score_suite(cases, answers))
    rep = abstention_report(confidences=(D("0.9"), D("0.1")), correct=(True, False))
    assert rep.abstention_rate == D("0.5")


def test_risk_analytics_and_attribution():
    from decimal import Decimal as D
    from risk.post_trade.attribution import brinson_attribution, factor_attribution
    from risk.post_trade.monitor import (
        concentration_score,
        ewma_volatility,
        funding_gap_risk,
        liquidity_var,
        parametric_var,
    )

    assert parametric_var((D("0.01"), D("-0.02"), D("0.015"))) >= D("0")
    assert ewma_volatility((D("0.01"), D("-0.01"))) > D("0")
    assert liquidity_var(D("1000"), D("5"), D("100000")) > D("0")
    assert concentration_score((D("0.5"), D("0.5"))) == D("0.5")
    assert funding_gap_risk(D("100"), D("200")) < D("0")
    rep = brinson_attribution(
        portfolio_weights={"EQ": D("0.6")}, benchmark_weights={"EQ": D("0.5")},
        portfolio_returns={"EQ": D("0.1")}, benchmark_returns={"EQ": D("0.08")},
    )
    assert rep.total == D("0.6") * D("0.1") - D("0.5") * D("0.08")
    assert factor_attribution({"MKT": D("1")}, {"MKT": D("0.05")}) == {"MKT": D("0.05")}


def test_release_gate_and_walkforward_runner():
    from decimal import Decimal as D
    from validation.release import ReleaseEvidence, certify_release
    from validation.walk_forward.runner import run_walk_forward

    good = ReleaseEvidence(True, True, True, True, True, True, True)
    assert certify_release(good).status.value == "certified"
    bad = ReleaseEvidence(True, True, True, True, True, False, True)
    assert certify_release(bad).status.value == "blocked"
    rep = run_walk_forward(100, train=50, test=20, step=20,
                           evaluate=lambda a, b, c, d: D("0.1"))
    assert rep.passed and len(rep.folds) >= 1
