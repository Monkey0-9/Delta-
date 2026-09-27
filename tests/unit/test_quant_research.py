from __future__ import annotations
from datetime import date
from decimal import Decimal
from uuid import uuid4

from data.ingestion.calendars import TradingCalendar
from data.ingestion.corporate_actions import CorporateAction
from data.ingestion.features import ewma_vol, returns
from execution.algorithms.slicing import twap_slices, vwap_slices
from quant.factors.cross_section import cross_sectional_rank
from quant.forecasting.calibration import brier_score
from quant.portfolio.optimizer import AssetForecast, PortfolioConstraint, PortfolioOptimizer
from quant.signals.momentum import mean_reversion_zscore, momentum
from risk.post_trade.monitor import check_post_trade, var_cvar
from finance_model.grounding import verify_grounding


def test_signals() -> None:
    px = tuple(Decimal(str(100 + i)) for i in range(30))
    assert momentum(px, 10) > 0
    assert isinstance(mean_reversion_zscore(px, 20), Decimal)


def test_optimizer_constraints() -> None:
    f = tuple(AssetForecast(uuid4(), Decimal("0.05") - Decimal(str(i)) * Decimal("0.01"), Decimal("0.1")) for i in range(3))
    r = PortfolioOptimizer().optimize(f, (PortfolioConstraint("max_weight", None, Decimal("0.5")),))
    assert abs(sum(w.weight for w in r.weights) - 1) < Decimal("0.0001")


def test_algos() -> None:
    assert sum(twap_slices(Decimal("100"), 4)) == Decimal("100")
    assert sum(vwap_slices(Decimal("100"), (Decimal("1"), Decimal("3")))) == Decimal("100")


def test_post_trade() -> None:
    from risk.post_trade.monitor import PostTradeState
    s = PostTradeState(Decimal("90"), Decimal("100"), Decimal("50"), Decimal("10"), Decimal("1"))
    assert check_post_trade(s) == ()
    v, c = var_cvar((Decimal("1"), Decimal("2"), Decimal("10")))
    assert c >= v


def test_grounding_gate() -> None:
    assert verify_grounding(("up [e1]",), ("e1",))[0].supported
    assert not verify_grounding(("up",), ("e1",))[0].supported


def test_features_cal() -> None:
    assert len(returns((Decimal("100"), Decimal("110")))) == 1
    assert TradingCalendar().is_trading_day(date(2026, 9, 25))
    assert CorporateAction("X", "split", Decimal("0.5")).adjust_price(Decimal("100")) == Decimal("50")
    assert cross_sectional_rank({"a": Decimal("1"), "b": Decimal("2")})["b"] == Decimal("1")
    assert brier_score((Decimal("0.8"),), (1,)) < Decimal("0.1")
