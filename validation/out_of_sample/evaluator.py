from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class OOSResult:
    strategy: str
    sharpe: Decimal
    max_drawdown: Decimal
    total_return: Decimal
    n_trades: int
    passed: bool
    reasons: tuple[str, ...] = ()


def evaluate_oos(
    returns: tuple[Decimal, ...],
    *,
    min_sharpe: Decimal = Decimal("0.5"),
    max_drawdown: Decimal = Decimal("0.25"),
    min_trades: int = 20,
) -> OOSResult:
    import math
    vals = [float(r) for r in returns]
    mean = sum(vals) / len(vals) if vals else 0.0
    var = sum((v - mean) ** 2 for v in vals) / len(vals) if vals else 0.0
    sharpe = Decimal(str(mean / (math.sqrt(var) + 1e-12) * math.sqrt(252))) if vals else Decimal("0")
    peak = -1e18
    mdd = 0.0
    cum = 0.0
    for v in vals:
        cum += v
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)
    reasons: list[str] = []
    if sharpe < min_sharpe:
        reasons.append(f"sharpe {sharpe:.2f} < {min_sharpe}")
    if Decimal(str(mdd)) > max_drawdown:
        reasons.append(f"drawdown {mdd:.3f} > {max_drawdown}")
    if len(vals) < min_trades:
        reasons.append("insufficient trades")
    return OOSResult("candidate", sharpe, Decimal(str(mdd)), Decimal(str(cum)), len(vals), not reasons, tuple(reasons))
