"""Extended signal family: carry, Donchian breakout, Bollinger %B, vol breakout.

All Decimal-preserving, deterministic, fail-closed on short input.
Complements quant/signals/signal_library.py and momentum.py.
"""
from __future__ import annotations

from decimal import Decimal


def _dec(values: tuple[float | Decimal, ...]) -> tuple[Decimal, ...]:
    return tuple(Decimal(str(v)) for v in values)


def carry_signal(near_yield: Decimal, far_yield: Decimal) -> int:
    """Term-structure roll: positive carry -> +1 (long front), else -1/0."""
    carry = far_yield - near_yield
    if carry > 0:
        return 1
    if carry < 0:
        return -1
    return 0


def donchian_breakout(prices: tuple[float | Decimal, ...], window: int) -> int:
    """+1 close above highest high, -1 below lowest low, else 0."""
    xs = _dec(prices)
    if window < 2 or len(xs) < window + 1:
        raise ValueError("need at least window+1 prices.")
    channel_high = max(xs[-(window + 1) : -1])
    channel_low = min(xs[-(window + 1) : -1])
    last = xs[-1]
    if last > channel_high:
        return 1
    if last < channel_low:
        return -1
    return 0


def bollinger_pct_b(
    prices: tuple[float | Decimal, ...], window: int = 20, num_std: Decimal = Decimal("2")
) -> Decimal:
    """%B position within Bollinger Bands. Clamp to [-0.5, 1.5] for stability."""
    xs = _dec(prices)
    if window < 2 or len(xs) < window:
        raise ValueError("need at least window prices.")
    if num_std <= 0:
        raise ValueError("num_std must be positive.")
    segment = xs[-window:]
    mean = sum(segment, Decimal("0")) / Decimal(len(segment))
    var = sum((x - mean) ** 2 for x in segment) / Decimal(len(segment))
    std = var.sqrt()
    if std == 0:
        return Decimal("0.5")
    pct_b = (xs[-1] - (mean - num_std * std)) / (2 * num_std * std)
    return max(Decimal("-0.5"), min(Decimal("1.5"), pct_b))


def vol_breakout_signal(
    prices: tuple[float | Decimal, ...], short: int = 10, long: int = 60, ratio: Decimal = Decimal("1.5")
) -> int:
    """+1 when short-horizon vol exceeds long-horizon vol by ratio (breakout)."""
    from quant.time_series.statistics import volatility

    xs = _dec(prices)
    if short < 2 or long <= short or len(xs) < long + 1:
        raise ValueError("need at least long+1 prices with long > short >= 2.")
    if ratio <= 0:
        raise ValueError("ratio must be positive.")
    short_vol = volatility(_returns(xs[-short - 1 :]))
    long_vol = volatility(_returns(xs[-long - 1 :]))
    if long_vol == 0:
        return 0
    return 1 if short_vol / long_vol >= ratio else 0


def _returns(prices: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    out: list[Decimal] = []
    for prev, cur in zip(prices, prices[1:]):
        if prev == 0:
            raise ValueError("zero price in returns.")
        out.append((cur - prev) / abs(prev))
    return tuple(out)


def garch11_volatility(
    returns: tuple[float | Decimal, ...],
    omega: Decimal = Decimal("0.000001"),
    alpha: Decimal = Decimal("0.08"),
    beta: Decimal = Decimal("0.90"),
) -> Decimal:
    """GARCH(1,1) terminal conditional vol. Stationarity (a+b<1) enforced."""
    if alpha <= 0 or beta < 0 or omega <= 0 or alpha + beta >= 1:
        raise ValueError("invalid GARCH parameters.")
    rs = _dec(returns)
    if len(rs) < 3:
        raise ValueError("need >= 3 returns.")
    var = sum(r * r for r in rs) / Decimal(len(rs))
    for r in rs:
        var = omega + alpha * r * r + beta * var
    return var.sqrt()


def pair_spread_zscore(
    leg_a: tuple[float | Decimal, ...],
    leg_b: tuple[float | Decimal, ...],
    window: int = 60,
    hedge: Decimal = Decimal("1"),
) -> Decimal:
    """Statistical-arbitrage spread z-score over trailing window."""
    a, b = _dec(leg_a), _dec(leg_b)
    if len(a) != len(b) or len(a) < window + 1:
        raise ValueError("legs must align with >= window+1 points.")
    spread = tuple(x - hedge * y for x, y in zip(a, b))[-window:]
    mean = sum(spread, Decimal("0")) / Decimal(len(spread))
    var = sum((s - mean) ** 2 for s in spread) / Decimal(len(spread))
    if var == 0:
        return Decimal("0")
    return (spread[-1] - mean) / var.sqrt()


def cross_asset_momentum_rank(returns_map: dict[str, Decimal]) -> list[tuple[str, Decimal]]:
    """Cross-sectional momentum ranks in [0,1], best first."""
    if not returns_map:
        raise ValueError("returns_map cannot be empty.")
    ordered = sorted(returns_map.items(), key=lambda kv: kv[1], reverse=True)
    n = len(ordered)
    if n == 1:
        return [(ordered[0][0], Decimal("1"))]
    return [(asset, Decimal(n - 1 - i) / Decimal(n - 1)) for i, (asset, _) in enumerate(ordered)]


def regime_conditioned_signal(signal: Decimal, regime: str, weights: dict[str, Decimal] | None = None) -> Decimal:
    """Scale a raw signal by regime weight (default: crisis/illiquid -> 0)."""
    table = weights or {"crisis": Decimal("0"), "illiquid": Decimal("0"),
                        "high_volatility": Decimal("0.5"), "trending": Decimal("1"),
                        "normal": Decimal("1")}
    if regime not in table:
        raise ValueError(f"unknown regime: {regime}")
    return signal * table[regime]
