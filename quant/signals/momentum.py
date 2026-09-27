from __future__ import annotations

from decimal import Decimal


def momentum(prices: tuple[Decimal, ...], lookback: int) -> Decimal:
    if len(prices) < lookback + 1 or lookback <= 0:
        raise ValueError("insufficient history.")
    base = prices[-lookback - 1]
    last = prices[-1]
    if base == 0:
        return Decimal("0")
    return (last - base) / abs(base)


def mean_reversion_zscore(prices: tuple[Decimal, ...], window: int) -> Decimal:
    if len(prices) < window or window <= 1:
        raise ValueError("insufficient history.")
    w = [float(p) for p in prices[-window:]]
    mean = sum(w) / len(w)
    var = sum((v - mean) ** 2 for v in w) / len(w)
    std = var ** 0.5 or 1e-12
    return Decimal(str((w[-1] - mean) / std))
