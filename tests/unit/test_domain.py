from decimal import Decimal

from core.domain import (
    AssetClass,
    Currency,
    Instrument,
    Money,
    OrderIntent,
    OrderSide,
    OrderType,
    Portfolio,
    Position,
    Price,
    Quantity,
)


def test_instrument_creation() -> None:
    instrument = Instrument.create(
        symbol="nvda",
        asset_class=AssetClass.EQUITY,
        currency=Currency("USD"),
        exchange="NASDAQ",
    )

    assert instrument.symbol == "NVDA"
    assert instrument.currency == Currency("USD")
    assert instrument.exchange == "NASDAQ"


def test_global_currency_codes() -> None:
    usd = Currency("USD")
    inr = Currency("INR")
    aed = Currency("AED")
    eur = Currency("EUR")

    assert usd.code == "USD"
    assert inr.code == "INR"
    assert aed.code == "AED"
    assert eur.code == "EUR"


def test_invalid_currency_code() -> None:
    try:
        Currency("US")
        assert False, "Invalid currency should raise ValueError"
    except ValueError:
        pass


def test_currency_normalization() -> None:
    currency = Currency(" inr ")

    assert currency.code == "INR"


def test_money_arithmetic() -> None:
    a = Money(
        Decimal("100.00"),
        Currency("USD"),
    )

    b = Money(
        Decimal("25.00"),
        Currency("USD"),
    )

    assert a + b == Money(
        Decimal("125.00"),
        Currency("USD"),
    )

    assert a - b == Money(
        Decimal("75.00"),
        Currency("USD"),
    )


def test_money_rejects_currency_mismatch() -> None:
    usd = Money(
        Decimal("100"),
        Currency("USD"),
    )

    inr = Money(
        Decimal("100"),
        Currency("INR"),
    )

    try:
        usd + inr
        assert False, "Currency mismatch should raise ValueError"
    except ValueError:
        pass


def test_order_intent() -> None:
    instrument = Instrument.create(
        symbol="NVDA",
        asset_class=AssetClass.EQUITY,
        currency=Currency("USD"),
    )

    order = OrderIntent(
        instrument_id=instrument.instrument_id,
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        order_type=OrderType.MARKET,
    )

    assert order.quantity == Decimal("10")
    assert order.side == OrderSide.BUY
    assert order.order_type == OrderType.MARKET


def test_position() -> None:
    instrument = Instrument.create(
        symbol="NVDA",
        asset_class=AssetClass.EQUITY,
        currency=Currency("USD"),
    )

    position = Position(
        instrument_id=instrument.instrument_id,
        quantity=Quantity(Decimal("10")),
        average_price=Price(
            Decimal("100"),
            Currency("USD"),
        ),
        current_price=Price(
            Decimal("120"),
            Currency("USD"),
        ),
    )

    assert position.market_value == Decimal("1200")
    assert position.cost_basis == Decimal("1000")
    assert position.unrealized_pnl == Decimal("200")


def test_portfolio() -> None:
    instrument = Instrument.create(
        symbol="NVDA",
        asset_class=AssetClass.EQUITY,
        currency=Currency("USD"),
    )

    position = Position(
        instrument_id=instrument.instrument_id,
        quantity=Quantity(Decimal("10")),
        average_price=Price(
            Decimal("100"),
            Currency("USD"),
        ),
        current_price=Price(
            Decimal("120"),
            Currency("USD"),
        ),
    )

    portfolio = Portfolio(
        cash=Money(
            Decimal("5000"),
            Currency("USD"),
        ),
        positions={
            instrument.instrument_id: position,
        },
    )

    assert portfolio.market_value == Decimal("1200")
    assert portfolio.equity == Decimal("6200")
    assert portfolio.unrealized_pnl == Decimal("200")


def test_empty_portfolio() -> None:
    portfolio = Portfolio(
        cash=Money(
            Decimal("10000"),
            Currency("INR"),
        ),
    )

    assert portfolio.market_value == Decimal("0")
    assert portfolio.equity == Decimal("10000")
    assert portfolio.unrealized_pnl == Decimal("0")