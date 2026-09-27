from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone

import pytest

from decision.horizon import DecisionHorizon
from quant.forecasting.forecast import (
    Forecast,
    ForecastDirection,
)
from quant.forecasting.horizon import (
    HorizonForecast,
    MultiHorizonAggregator,
)
from quant.time_series.statistics import (
    arithmetic_returns,
    mean_return,
    variance,
    volatility,
)
from quant.uncertainty.engine import (
    UncertaintyEngine,
)
from simulation.counterfactual.engine import (
    CounterfactualAction,
    CounterfactualResult,
)
from world_model.state.system_state import (
    MacroState,
    MarketState,
    RegimeState,
    UncertaintyState,
    WorldState,
)
from world_model.state_fusion.fusion import (
    StateFusion,
    StateFusionInput,
)


TIMESTAMP = datetime(
    2026,
    9,
    24,
    10,
    0,
    tzinfo=timezone.utc,
)


# ---------------------------------------------------------------------------
# WORLD MODEL
# ---------------------------------------------------------------------------


def test_market_state_normalizes_symbol() -> None:
    state = MarketState(
        symbol=" nvda ",
        price=Decimal("180.50"),
        volatility=Decimal("0.25"),
        liquidity_score=Decimal("0.95"),
        timestamp=TIMESTAMP,
    )

    assert state.symbol == "NVDA"
    assert state.price == Decimal("180.50")
    assert state.liquidity_score == Decimal("0.95")


def test_market_state_rejects_invalid_liquidity() -> None:
    with pytest.raises(ValueError):
        MarketState(
            symbol="NVDA",
            price=Decimal("180"),
            volatility=Decimal("0.20"),
            liquidity_score=Decimal("1.50"),
            timestamp=TIMESTAMP,
        )


def test_regime_state_validates_confidence() -> None:
    regime = RegimeState(
        name="high_volatility",
        confidence=Decimal("0.87"),
        timestamp=TIMESTAMP,
    )

    assert regime.name == "high_volatility"
    assert regime.confidence == Decimal("0.87")


def test_uncertainty_state_aggregates_components() -> None:
    uncertainty = UncertaintyState(
        model=Decimal("0.20"),
        data=Decimal("0.10"),
        regime=Decimal("0.30"),
        execution=Decimal("0.40"),
    )

    assert uncertainty.aggregate == Decimal("0.25")


def test_world_state_market_lookup() -> None:
    market = MarketState(
        symbol="NVDA",
        price=Decimal("180"),
        volatility=Decimal("0.20"),
        liquidity_score=Decimal("0.90"),
        timestamp=TIMESTAMP,
    )

    world = WorldState(
        market=(market,),
        portfolio_equity=Decimal("100000"),
        portfolio_exposure=Decimal("25000"),
    )

    assert world.market_for("nvda") == market
    assert world.market_for("AAPL") is None


def test_world_state_rejects_invalid_version() -> None:
    with pytest.raises(ValueError):
        WorldState(version=0)


# ---------------------------------------------------------------------------
# STATE FUSION
# ---------------------------------------------------------------------------


def test_state_fusion_creates_initial_world_state() -> None:
    market = MarketState(
        symbol="NVDA",
        price=Decimal("180"),
        volatility=Decimal("0.20"),
        liquidity_score=Decimal("0.90"),
        timestamp=TIMESTAMP,
    )

    input_data = StateFusionInput(
        market=(market,),
        portfolio_equity=Decimal("100000"),
        portfolio_exposure=Decimal("25000"),
    )

    world = StateFusion().build(input_data)

    assert world.version == 1
    assert world.portfolio_equity == Decimal("100000")
    assert world.market_for("NVDA") == market


def test_state_fusion_increments_version() -> None:
    first = WorldState(version=7)

    second = StateFusion().build(
        StateFusionInput(),
        previous=first,
    )

    assert second.version == 8


# ---------------------------------------------------------------------------
# TIME SERIES
# ---------------------------------------------------------------------------


def test_arithmetic_returns() -> None:
    prices = (
        Decimal("100"),
        Decimal("110"),
        Decimal("99"),
    )

    returns = arithmetic_returns(prices)

    assert returns[0] == Decimal("0.1")
    assert returns[1] == Decimal("-0.1")


def test_arithmetic_returns_requires_positive_previous_price() -> None:
    with pytest.raises(ValueError):
        arithmetic_returns(
            (
                Decimal("0"),
                Decimal("100"),
            )
        )


def test_mean_return() -> None:
    returns = (
        Decimal("0.10"),
        Decimal("0.20"),
        Decimal("0.30"),
    )

    assert mean_return(returns) == Decimal("0.20")


def test_variance_is_zero_for_single_observation() -> None:
    assert variance((Decimal("0.10"),)) == Decimal("0")


def test_volatility_is_non_negative() -> None:
    returns = (
        Decimal("0.01"),
        Decimal("-0.02"),
        Decimal("0.03"),
        Decimal("-0.01"),
    )

    result = volatility(returns)

    assert result >= Decimal("0")


# ---------------------------------------------------------------------------
# FORECASTING
# ---------------------------------------------------------------------------


def test_forecast_direction_contract() -> None:
    forecast = Forecast(
        symbol="NVDA",
        horizon="medium_term",
        expected_return=Decimal("0.08"),
        confidence=Decimal("0.82"),
        direction=ForecastDirection.UP,
        model_version="forecast-v1",
    )

    assert forecast.symbol == "NVDA"
    assert forecast.direction == ForecastDirection.UP
    assert forecast.confidence == Decimal("0.82")


def test_forecast_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        Forecast(
            symbol="NVDA",
            horizon="medium_term",
            expected_return=Decimal("0.08"),
            confidence=Decimal("1.10"),
            direction=ForecastDirection.UP,
            model_version="forecast-v1",
        )


# ---------------------------------------------------------------------------
# UNCERTAINTY
# ---------------------------------------------------------------------------


def test_uncertainty_engine() -> None:
    estimate = UncertaintyEngine.estimate(
        model=Decimal("0.10"),
        data=Decimal("0.20"),
        regime=Decimal("0.30"),
        execution=Decimal("0.40"),
    )

    assert estimate.aggregate == Decimal("0.25")


# ---------------------------------------------------------------------------
# MULTI-HORIZON
# ---------------------------------------------------------------------------


def test_multi_horizon_weighted_return() -> None:
    short = Forecast(
        symbol="NVDA",
        horizon="short_term",
        expected_return=Decimal("0.04"),
        confidence=Decimal("0.80"),
        direction=ForecastDirection.UP,
        model_version="v1",
    )

    long = Forecast(
        symbol="NVDA",
        horizon="long_term",
        expected_return=Decimal("0.12"),
        confidence=Decimal("0.90"),
        direction=ForecastDirection.UP,
        model_version="v1",
    )

    result = MultiHorizonAggregator.aggregate(
        (
            HorizonForecast(
                horizon=DecisionHorizon.SHORT_TERM,
                forecast=short,
                weight=Decimal("1"),
            ),
            HorizonForecast(
                horizon=DecisionHorizon.LONG_TERM,
                forecast=long,
                weight=Decimal("3"),
            ),
        )
    )

    assert result == Decimal("0.10")


def test_empty_multi_horizon_returns_zero() -> None:
    assert (
        MultiHorizonAggregator.aggregate(())
        == Decimal("0")
    )


# ---------------------------------------------------------------------------
# COUNTERFACTUAL / DIGITAL TWIN
# ---------------------------------------------------------------------------


def test_counterfactual_selects_risk_adjusted_action() -> None:
    baseline = CounterfactualAction(
        name="HOLD",
        expected_return=Decimal("0.04"),
        expected_risk=Decimal("0.01"),
    )

    buy = CounterfactualAction(
        name="BUY",
        expected_return=Decimal("0.10"),
        expected_risk=Decimal("0.03"),
    )

    reduce = CounterfactualAction(
        name="REDUCE",
        expected_return=Decimal("0.03"),
        expected_risk=Decimal("0.005"),
    )

    result = CounterfactualResult(
        baseline=baseline,
        alternatives=(buy, reduce),
    )

    assert result.best_risk_adjusted_alternative == buy


def test_counterfactual_includes_baseline() -> None:
    baseline = CounterfactualAction(
        name="HOLD",
        expected_return=Decimal("0.05"),
        expected_risk=Decimal("0.01"),
    )

    result = CounterfactualResult(
        baseline=baseline,
        alternatives=(),
    )

    assert result.best_risk_adjusted_alternative == baseline


# ---------------------------------------------------------------------------
# INTEGRATED W4-W8 TEST
# ---------------------------------------------------------------------------


def test_world_to_quant_to_counterfactual_pipeline() -> None:
    market = MarketState(
        symbol="NVDA",
        price=Decimal("180"),
        volatility=Decimal("0.25"),
        liquidity_score=Decimal("0.90"),
        timestamp=TIMESTAMP,
    )

    regime = RegimeState(
        name="risk_on",
        confidence=Decimal("0.85"),
        timestamp=TIMESTAMP,
    )

    uncertainty = UncertaintyState(
        model=Decimal("0.10"),
        data=Decimal("0.10"),
        regime=Decimal("0.20"),
        execution=Decimal("0.10"),
    )

    world = StateFusion().build(
        StateFusionInput(
            market=(market,),
            regime=regime,
            uncertainty=uncertainty,
            portfolio_equity=Decimal("100000"),
            portfolio_exposure=Decimal("20000"),
        )
    )

    forecast = Forecast(
        symbol="NVDA",
        horizon="medium_term",
        expected_return=Decimal("0.08"),
        confidence=Decimal("0.85"),
        direction=ForecastDirection.UP,
        model_version="forecast-v1",
    )

    horizon_result = MultiHorizonAggregator.aggregate(
        (
            HorizonForecast(
                horizon=DecisionHorizon.MEDIUM_TERM,
                forecast=forecast,
                weight=Decimal("1"),
            ),
        )
    )

    counterfactual = CounterfactualResult(
        baseline=CounterfactualAction(
            name="HOLD",
            expected_return=Decimal("0.02"),
            expected_risk=Decimal("0.01"),
        ),
        alternatives=(
            CounterfactualAction(
                name="BUY",
                expected_return=horizon_result,
                expected_risk=uncertainty.aggregate,
            ),
        ),
    )

    assert world.version == 1
    assert world.market_for("NVDA") is not None
    assert horizon_result == Decimal("0.08")
    assert (
        counterfactual.best_risk_adjusted_alternative.name
        == "BUY"
    )