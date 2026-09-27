from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PostTradeState:
    equity: Decimal
    peak: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    leverage: Decimal


def check_post_trade(s: PostTradeState, *, max_dd: Decimal = Decimal("0.2"), max_lev: Decimal = Decimal("3")) -> tuple[str, ...]:
    breaches = []
    dd = (s.peak - s.equity) / s.peak if s.peak > 0 else Decimal("0")
    if dd > max_dd:
        breaches.append(f"drawdown {dd:.3f}")
    if s.leverage > max_lev:
        breaches.append(f"leverage {s.leverage}")
    return tuple(breaches)


def var_cvar(losses: tuple[Decimal, ...], alpha: Decimal = Decimal("0.95")) -> tuple[Decimal, Decimal]:
    if not losses:
        raise ValueError("empty losses.")
    xs = sorted(losses)
    k = min(len(xs) - 1, int(float(alpha) * len(xs)))
    var = xs[k]
    tail = xs[k:]
    return var, sum(tail) / len(tail)


def parametric_var(
    returns: tuple[Decimal, ...], alpha: Decimal = Decimal("0.95"), notional: Decimal = Decimal("1")
) -> Decimal:
    """Gaussian VaR from sample mean/std. Fail-closed on empty input."""
    if not returns:
        raise ValueError("empty returns.")
    import math

    xs = [float(r) for r in returns]
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    std = var ** 0.5
    z = {0.90: 1.282, 0.95: 1.645, 0.975: 1.96, 0.99: 2.326}.get(round(float(alpha), 3), 1.645)
    return Decimal(str(max(-(mean - z * std) * float(notional), 0.0)))


def ewma_volatility(returns: tuple[Decimal, ...], lam: Decimal = Decimal("0.94")) -> Decimal:
    """RiskMetrics EWMA volatility. Fail-closed on empty input."""
    if not returns:
        raise ValueError("empty returns.")
    if not Decimal("0") < lam < Decimal("1"):
        raise ValueError("lambda in (0,1).")
    l = float(lam)
    v = float(returns[0]) ** 2
    for r in returns[1:]:
        v = l * v + (1 - l) * float(r) ** 2
    return Decimal(str(v ** 0.5))


def liquidity_var(
    position: Decimal, spread_bps: Decimal, adv: Decimal, participation: Decimal = Decimal("0.1")
) -> Decimal:
    """Liquidity-adjusted VaR add-on: spread cost + sqrt-impact (Almgren)."""
    if adv <= 0 or position < 0:
        raise ValueError("adv must be positive, position non-negative.")
    import math

    spread_cost = position * spread_bps / Decimal("10000")
    impact = position * Decimal(str(math.sqrt(float(position / adv)))) * participation
    return spread_cost + impact


def concentration_score(weights: tuple[Decimal, ...]) -> Decimal:
    """Herfindahl index in [1/n, 1]; 1 = fully concentrated."""
    if not weights:
        raise ValueError("empty weights.")
    tot = sum(abs(w) for w in weights) or Decimal("1")
    norm = [abs(w) / tot for w in weights]
    return sum(w * w for w in norm)


def funding_gap_risk(
    liabilities: Decimal, liquid_assets: Decimal, haircut: Decimal = Decimal("0.15")
) -> Decimal:
    """Funding gap after haircuts; positive = shortfall."""
    if not Decimal("0") <= haircut < Decimal("1"):
        raise ValueError("haircut in [0,1).")
    return liabilities - liquid_assets * (Decimal("1") - haircut)
