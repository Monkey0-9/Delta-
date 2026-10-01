from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from simulation.backtest.config import BacktestConfig
from simulation.backtest.strategy import SignalStrategy, run_strategy_backtest
from simulation.replay.event import ReplayEvent
from validation.out_of_sample.evaluator import evaluate_oos
from validation.release import ReleaseEvidence, certify_release


def test_full_paper_pipeline_e2e() -> None:
    from data.point_in_time.store import PointInTimeStore, StoredEvent
    from finance_model.engine import FinanceAnalysisPolicy
    from finance_model.contracts import FinancialAnalysisInput
    from portfolio.state import PortfolioState
    from risk.firewall.firewall import RiskFirewall
    from risk.limits.limits import RiskLimits

    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store = PointInTimeStore()
    assert store.append(StoredEvent("e1", t0, t0, t0, "feed", '{"close":100}'))
    assert len(store.as_of(t0)) == 1

    model = FinanceAnalysisPolicy("test-v1")
    analysis = model.analyze(
        FinancialAnalysisInput(
            instrument="AAA", world_state_version="w1", quant_state_version="q1",
            portfolio_context="flat", horizon="1D",
            expected_return=Decimal("0.01"), uncertainty=Decimal("0.1"),
        )
    )
    assert analysis.candidate_action == "BUY_CANDIDATE"

    events = tuple(ReplayEvent(t0 + timedelta(seconds=i), i, f"e{i}") for i in range(4))
    ctx = run_strategy_backtest(
        config=BacktestConfig(initial_cash=Decimal("10000")),
        events=events,
        strategy=SignalStrategy(
            signal=(Decimal("1"), Decimal("-1"), Decimal("1"), Decimal("-1")),
            prices=(Decimal("10"), Decimal("11"), Decimal("12"), Decimal("13")),
        ),
    )
    assert ctx.fills == 2

    oos = evaluate_oos(tuple(Decimal("0.01") for _ in range(30)))
    assert oos.n_trades == 30


def test_release_gate_blocks_bad_perf() -> None:
    ev = ReleaseEvidence(True, True, True, True, True, False, True)
    assert certify_release(ev).status.value == "blocked"
