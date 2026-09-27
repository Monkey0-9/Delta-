from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quant.forecasting.calibration import brier_score, expected_calibration_error
from quant.forecasting.metrics import log_loss


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    brier: Decimal
    ece: Decimal
    log_loss: Decimal
    n: int
    passed: bool
    reasons: tuple[str, ...] = ()


def calibration_report(
    probs: tuple[Decimal, ...],
    outcomes: tuple[int, ...],
    *,
    max_brier: Decimal = Decimal("0.25"),
    max_ece: Decimal = Decimal("0.10"),
    bins: int = 10,
) -> CalibrationReport:
    """ECE/Brier/log-loss report with promotion thresholds. Fail-closed."""
    if len(probs) != len(outcomes) or not probs:
        raise ValueError("need non-empty aligned inputs.")
    b = brier_score(probs, outcomes)
    e = expected_calibration_error(probs, outcomes, bins=bins)
    ll = log_loss(probs, outcomes)
    reasons: list[str] = []
    if b > max_brier:
        reasons.append(f"brier {b} > {max_brier}")
    if e > max_ece:
        reasons.append(f"ece {e} > {max_ece}")
    return CalibrationReport(b, e, ll, len(probs), not reasons, tuple(reasons))
