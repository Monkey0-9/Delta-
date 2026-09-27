from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CorporateAction:
    symbol: str
    kind: str  # split, dividend, merger
    factor: Decimal  # price multiplier e.g. split 2:1 -> 0.5
    ex_date: str = ""

    def adjust_price(self, price: Decimal) -> Decimal:
        if self.factor <= 0:
            raise ValueError("factor must be positive.")
        return price * self.factor

    def adjust_volume(self, volume: Decimal) -> Decimal:
        if self.kind == "split":
            if self.factor <= 0:
                raise ValueError("factor must be positive.")
            return volume / self.factor
        return volume


def _ex(action: CorporateAction) -> str:
    return action.ex_date or ""


def apply_actions(prices: tuple[Decimal, ...], actions: tuple[CorporateAction, ...]) -> tuple[Decimal, ...]:
    out = prices
    for a in actions:
        out = tuple(a.adjust_price(p) for p in out)
    return out


def apply_actions_as_of(
    prices: tuple[Decimal, ...],
    dates: tuple[str, ...],
    actions: tuple[CorporateAction, ...],
) -> tuple[Decimal, ...]:
    """Apply only actions with ex_date <= each bar date (back-adjust pipeline).

    ``dates`` and ``prices`` must align. Bars on/after an ex-date are left
    unadjusted; bars before it are multiplied by the action factor, which is
    the standard total-return back-adjustment. Deterministic and fail-closed
    on length mismatch.
    """
    if len(prices) != len(dates):
        raise ValueError("prices/dates must align.")
    out: list[Decimal] = []
    for price, day in zip(prices, dates):
        adj = price
        for action in actions:
            if _ex(action) and day < _ex(action):
                adj = action.adjust_price(adj)
        out.append(adj)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class BarOHLCV:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    day: str = ""


def adjust_ohlcv(
    bars: tuple[BarOHLCV, ...], actions: tuple[CorporateAction, ...]
) -> tuple[BarOHLCV, ...]:
    """Back-adjust an OHLCV series for splits (price*factor, volume/factor).

    Cash dividends and mergers leave price history unchanged here; they are
    recorded for total-return accounting downstream.
    """
    out: list[BarOHLCV] = []
    for bar in bars:
        o, h, l, c, v = bar.open, bar.high, bar.low, bar.close, bar.volume
        for action in actions:
            if action.kind == "split" and action.ex_date and bar.day < action.ex_date:
                o = action.adjust_price(o)
                h = action.adjust_price(h)
                l = action.adjust_price(l)
                c = action.adjust_price(c)
                v = action.adjust_volume(v)
        out.append(BarOHLCV(o, h, l, c, v, bar.day))
    return tuple(out)
