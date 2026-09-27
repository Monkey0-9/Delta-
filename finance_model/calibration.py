from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quant.forecasting.calibrated import calibration_report


@dataclass(frozen=True, slots=True)
class AbstentionReport:
    abstention_rate: Decimal
    selective_accuracy: Decimal
    n: int
    passed: bool
    reasons: tuple[str, ...] = ()


def abstention_report(
    *,
    confidences: tuple[Decimal, ...],
    correct: tuple[bool, ...],
    threshold: Decimal = Decimal("0.40"),
    min_selective_accuracy: Decimal = Decimal("0.60"),
) -> AbstentionReport:
    """Calibration/abstention metrics wired to the adaptation gate.

    Abstain when confidence < threshold. Selective accuracy = accuracy on
    non-abstained items. Fail-closed on misalignment.
    """
    if len(confidences) != len(correct) or not confidences:
        raise ValueError("need non-empty aligned inputs.")
    abstained = sum(1 for c in confidences if c < threshold)
    kept = [(c, ok) for c, ok in zip(confidences, correct) if c >= threshold]
    acc = sum(1 for _, ok in kept if ok) / len(kept) if kept else 0.0
    reasons: list[str] = []
    if Decimal(str(acc)) < min_selective_accuracy and kept:
        reasons.append(f"selective accuracy {acc:.3f} < {min_selective_accuracy}")
    return AbstentionReport(
        Decimal(str(abstained / len(confidences))),
        Decimal(str(acc)),
        len(confidences),
        not reasons,
        tuple(reasons),
    )


def llm_calibration_gate(
    probs: tuple[Decimal, ...],
    outcomes: tuple[int, ...],
    confidences: tuple[Decimal, ...],
    correct: tuple[bool, ...],
) -> tuple[bool, str]:
    cal = calibration_report(probs, outcomes)
    abst = abstention_report(confidences=confidences, correct=correct)
    if not cal.passed:
        return False, f"calibration failed: {cal.reasons}"
    if not abst.passed:
        return False, f"abstention failed: {abst.reasons}"
    return True, "LLM calibration/abstention passed."
