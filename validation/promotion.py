"""Stage-4 T: promotion thresholds enforced in code (not docs).

backtest Sharpe > 1 alone NEVER validates. Requires: OOS Sharpe > 0,
deflated Sharpe (Bailey) p-value, PBO < 0.5, min OOS bars, cost-aware.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    oos_sharpe: float
    dsr_pvalue: float  # P(SR_hat > SR_0); require < 0.05
    pbo: float  # require < 0.5
    oos_bars: int  # require >= 252
    cost_aware: bool
    sharpe_backtest: float = 0.0


class PromotionBlocked(RuntimeError):
    pass


def require_promotion(ev: PromotionEvidence) -> None:
    reasons: list[str] = []
    if not ev.cost_aware:
        reasons.append("not cost-aware")
    if ev.oos_bars < 252:
        reasons.append(f"oos_bars {ev.oos_bars} < 252")
    if not ev.oos_sharpe > 0:
        reasons.append(f"oos_sharpe {ev.oos_sharpe} <= 0")
    if not ev.dsr_pvalue < 0.05:
        reasons.append(f"dsr_pvalue {ev.dsr_pvalue} >= 0.05")
    if not ev.pbo < 0.5:
        reasons.append(f"pbo {ev.pbo} >= 0.5")
    if reasons:
        raise PromotionBlocked(
            "promotion blocked (" + "; ".join(reasons) + "). "
            f"backtest Sharpe {ev.sharpe_backtest} alone never validates.")


__all__ = ["PromotionEvidence", "PromotionBlocked", "require_promotion"]
