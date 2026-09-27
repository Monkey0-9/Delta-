from decimal import Decimal

from core.domain import (
    AssetClass,
    Currency,
    Instrument,
)
from decision import (
    DecisionAction,
    DecisionEngine,
    DecisionHorizon,
    DecisionInput,
)


def create_instrument() -> Instrument:
    return Instrument.create(
        symbol="NVDA",
        asset_class=AssetClass.EQUITY,
        currency=Currency("USD"),
        exchange="NASDAQ",
    )


def test_positive_signal_creates_buy() -> None:
    instrument = create_instrument()

    engine = DecisionEngine()

    decision = engine.evaluate(
        DecisionInput(
            instrument_id=instrument.instrument_id,
            horizon=DecisionHorizon.MEDIUM_TERM,
            expected_return=Decimal("0.08"),
            confidence=Decimal("0.85"),
            model_version="model-1",
            world_state_version="state-1",
        )
    )

    assert decision.action == DecisionAction.BUY
    assert decision.confidence == Decimal("0.85")


def test_negative_signal_creates_sell() -> None:
    instrument = create_instrument()

    decision = DecisionEngine().evaluate(
        DecisionInput(
            instrument_id=instrument.instrument_id,
            horizon=DecisionHorizon.SHORT_TERM,
            expected_return=Decimal("-0.05"),
            confidence=Decimal("0.80"),
            model_version="model-1",
            world_state_version="state-1",
        )
    )

    assert decision.action == DecisionAction.SELL


def test_low_confidence_waits() -> None:
    instrument = create_instrument()

    decision = DecisionEngine().evaluate(
        DecisionInput(
            instrument_id=instrument.instrument_id,
            horizon=DecisionHorizon.INTRADAY,
            expected_return=Decimal("0.10"),
            confidence=Decimal("0.30"),
            model_version="model-1",
            world_state_version="state-1",
        )
    )

    assert decision.action == DecisionAction.WAIT