"""Execution: price-time priority, partial fills, book microstructure."""
from decimal import Decimal
from uuid import uuid4

from execution.matching.engine import PriceTimeMatcher
from market_data.order_book import BookLevel, OrderBook


def test_price_time_priority_fifo():
    m = PriceTimeMatcher()
    assert m.add("s1", "sell", Decimal("100"), Decimal("5")) == []
    assert m.add("s2", "sell", Decimal("100"), Decimal("5")) == []
    fills = m.add("b1", "buy", Decimal("100"), Decimal("7"))
    assert [f.sell_id for f in fills] == ["s1", "s2"]
    assert sum(f.quantity for f in fills) == Decimal("7")
    assert fills[0].price == Decimal("100")


def test_book_imbalance_microprice_spread():
    book = OrderBook(
        instrument_id=uuid4(),
        bids=(BookLevel(Decimal("99"), Decimal("10")), BookLevel(Decimal("98"), Decimal("5"))),
        asks=(BookLevel(Decimal("101"), Decimal("10")),),
    )
    assert book.spread == Decimal("2")
    assert book.mid == Decimal("100")
    assert book.imbalance() == Decimal("5") / Decimal("25")
    assert book.microprice() is not None
    book2 = book.apply_delta(asks=(BookLevel(Decimal("101"), Decimal("0")),))
    assert book2.best_ask is None


def test_derivatives_bsm_parity_sanity():
    from quant.derivatives.bsm import OptionSpec, bsm_price, greeks

    call = OptionSpec(spot=100.0, strike=100.0, rate=0.05, vol=0.2, t_years=1.0, is_call=True)
    put = OptionSpec(spot=100.0, strike=100.0, rate=0.05, vol=0.2, t_years=1.0, is_call=False)
    c, p = bsm_price(call), bsm_price(put)
    # put-call parity: C - P = S*exp(-qT) - K*exp(-rT)
    import math

    assert abs((c - p) - (100.0 - 100.0 * math.exp(-0.05))) < 1e-9
    g = greeks(call)
    assert 0.0 < g.delta < 1.0 and g.gamma > 0 and g.vega_per_point > 0
