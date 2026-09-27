from decimal import Decimal
from uuid import uuid4

from portfolio import (
    ExposureCalculator,
    PortfolioAccounting,
    PortfolioState,
    PositionState,
)


def test_position_market_value() -> None:
    instrument_id = uuid4()

    position = PositionState(
        instrument_id=instrument_id,
        quantity=Decimal("100"),
        average_cost=Decimal("100"),
        market_price=Decimal("120"),
    )

    assert position.market_value == Decimal("12000")


def test_unrealized_pnl() -> None:
    instrument_id = uuid4()

    position = PositionState(
        instrument_id=instrument_id,
        quantity=Decimal("100"),
        average_cost=Decimal("100"),
        market_price=Decimal("120"),
    )

    assert position.unrealized_pnl == Decimal("2000")


def test_portfolio_equity() -> None:
    position = PositionState(
        instrument_id=uuid4(),
        quantity=Decimal("10"),
        average_cost=Decimal("100"),
        market_price=Decimal("120"),
    )

    portfolio = PortfolioState(
        cash=Decimal("5000"),
        positions=(position,),
    )

    assert portfolio.position_market_value == Decimal("1200")
    assert portfolio.equity == Decimal("6200")


def test_realized_sell_pnl() -> None:
    pnl = PortfolioAccounting.realized_sell_pnl(
        quantity=Decimal("10"),
        average_cost=Decimal("100"),
        execution_price=Decimal("130"),
    )

    assert pnl == Decimal("300")


def test_exposure() -> None:
    position = PositionState(
        instrument_id=uuid4(),
        quantity=Decimal("10"),
        average_cost=Decimal("100"),
        market_price=Decimal("120"),
    )

    portfolio = PortfolioState(
        cash=Decimal("1080"),
        positions=(position,),
    )

    exposure = ExposureCalculator.calculate(portfolio)

    assert exposure.gross_exposure == Decimal("1200")
    assert exposure.net_exposure == Decimal("1200")
    assert exposure.leverage == Decimal("1200") / Decimal("2280")