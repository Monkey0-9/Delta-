"""Native LOB parity: C++ book must match PriceTimeMatcher fill-for-fill."""
from __future__ import annotations

from decimal import Decimal

import pytest

from execution.matching.engine import PriceTimeMatcher

lob = pytest.importorskip("native.lob", reason="native.lob missing")
if not lob.available():
    pytest.skip("lob.dll not built", allow_module_level=True)


def _script():
    return [
        ("s1", "sell", "100", "5"),
        ("s2", "sell", "100", "5"),
        ("b1", "buy", "100", "7"),      # crosses: s1 fully, s2 partial
        ("b2", "buy", "99", "10"),      # rests (below best ask... none left -> rests)
        ("s3", "sell", "99", "4"),      # crosses b2
        ("s4", "sell", "101", "8"),     # rests
        ("b3", "buy", "101", "20"),     # sweeps s4 + remainder rests
    ]


def _run(m):
    fills = []
    for oid, side, px, qty in _script():
        fills.append([(f.buy_id, f.sell_id, f.price, f.quantity)
                      for f in m.add(oid, side, Decimal(px), Decimal(qty))])
    return fills


def test_lob_matches_python_fill_for_fill():
    py = _run(PriceTimeMatcher())
    m = lob.NativeMatcher()
    try:
        nat = _run(m)
    finally:
        m.close()
    assert nat == py
    assert nat[2] == [("b1", "s1", Decimal("100"), Decimal("5")),
                      ("b1", "s2", Decimal("100"), Decimal("2"))]


def test_cancel_and_replace():
    m = lob.NativeMatcher()
    try:
        assert m.add("s1", "sell", Decimal("100"), Decimal("5")) == []
        assert m.cancel("s1") is True
        assert m.cancel("s1") is False  # already gone
        # crossing buy now rests (book empty)
        assert m.add("b1", "buy", Decimal("100"), Decimal("5")) == []
        # replace b1 as sell crossing nothing (no bids) -> rests as ask
        assert m.replace("b1", "sell", Decimal("99"), Decimal("5")) == []
        bid, ask = m.top()
        assert bid is None and ask == (Decimal("99"), Decimal("5"))
        # buy 2 @99 lifts part
        fills = m.add("b9", "buy", Decimal("99"), Decimal("2"))
        assert [(f.buy_id, f.sell_id, f.price, f.quantity) for f in fills] == [
            ("b9", "b1", Decimal("99"), Decimal("2"))]
    finally:
        m.close()


def test_top_of_book():
    m = lob.NativeMatcher()
    try:
        assert m.top() == (None, None)
        m.add("b1", "buy", Decimal("99"), Decimal("10"))
        m.add("s1", "sell", Decimal("101"), Decimal("4"))
        assert m.top() == ((Decimal("99"), Decimal("10")),
                           (Decimal("101"), Decimal("4")))
    finally:
        m.close()


def test_invalid_inputs_rejected():
    m = lob.NativeMatcher()
    try:
        with pytest.raises(ValueError):
            m.add("x", "hold", Decimal("1"), Decimal("1"))
        with pytest.raises(ValueError):
            m.add("x", "buy", Decimal("-1"), Decimal("1"))
    finally:
        m.close()


def test_add_many_matches_sequential():
    from decimal import Decimal as D

    script = [(f"o{i}", "sell" if i % 2 else "buy", D(100 + (i % 7)), D((i % 5) + 1))
              for i in range(300)]
    py = PriceTimeMatcher()
    exp = [[(f.buy_id, f.sell_id, f.price, f.quantity)
            for f in py.add(oid, side, px, q)] for oid, side, px, q in script]
    m = lob.NativeMatcher()
    try:
        got = [[(f.buy_id, f.sell_id, f.price, f.quantity) for f in fills]
               for fills in m.add_many(script)]
    finally:
        m.close()
    assert got == exp
