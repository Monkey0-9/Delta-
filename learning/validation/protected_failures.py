from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FailureCase:
    case_id: str
    regime: str
    volatility: Decimal
    liquidity: Decimal
    expected_max_loss: Decimal


@dataclass(frozen=True, slots=True)
class CandidateResult:
    case_id: str
    actual_loss: Decimal


@dataclass(frozen=True, slots=True)
class RegressionReport:
    passed: bool
    failed_cases: tuple[str, ...]


class ProtectedFailureRegression:
    """
    Candidate strategies must not reproduce known catastrophic
    failure patterns beyond the protected tolerance.
    """

    def __init__(
        self,
        tolerance: Decimal = Decimal("0.01"),
    ) -> None:
        self._tolerance = tolerance

    def evaluate(
        self,
        cases: tuple[FailureCase, ...],
        results: tuple[CandidateResult, ...],
    ) -> RegressionReport:

        expected = {
            case.case_id: case
            for case in cases
        }

        failed: list[str] = []

        for result in results:
            case = expected.get(result.case_id)

            if case is None:
                failed.append(result.case_id)
                continue

            allowed_loss = (
                case.expected_max_loss
                + self._tolerance
            )

            if result.actual_loss > allowed_loss:
                failed.append(result.case_id)

        return RegressionReport(
            passed=not failed,
            failed_cases=tuple(failed),
        )


def seeded_protected_cases() -> tuple[FailureCase, ...]:
    """Permanent catastrophic patterns. Never shrink this list."""
    return (
        FailureCase("FLASH-CRASH-2010", "crisis", Decimal("0.09"), Decimal("0.05"), Decimal("0.20")),
        FailureCase("COVID-CRASH-2020", "crisis", Decimal("0.12"), Decimal("0.08"), Decimal("0.25")),
        FailureCase("RATE-SHOCK-2022", "macro", Decimal("0.06"), Decimal("0.30"), Decimal("0.15")),
        FailureCase("LIQ-FREEZE-2008", "liquidity", Decimal("0.07"), Decimal("0.02"), Decimal("0.30")),
        FailureCase("CORR-SPIKE-2011", "correlation", Decimal("0.05"), Decimal("0.25"), Decimal("0.12")),
        FailureCase("GAP-RISK-OVERNIGHT", "event", Decimal("0.04"), Decimal("0.40"), Decimal("0.10")),
        FailureCase("STALE-FEED-EXEC", "data", Decimal("0.02"), Decimal("0.50"), Decimal("0.05")),
        FailureCase("CONC-SINGLE-NAME", "portfolio", Decimal("0.03"), Decimal("0.35"), Decimal("0.12")),
        FailureCase("VAR-BREACH-TAIL", "tail", Decimal("0.08"), Decimal("0.20"), Decimal("0.18")),
        FailureCase("SLIPPAGE-BLOWOUT", "execution", Decimal("0.03"), Decimal("0.10"), Decimal("0.08")),
        FailureCase("DUPLICATE-ORDER-STORM", "operational", Decimal("0.01"), Decimal("0.60"), Decimal("0.03")),
        FailureCase("KILL-SWITCH-DRILL", "operational", Decimal("0.01"), Decimal("0.60"), Decimal("0.00")),
        FailureCase("FX-DEPEG", "fx", Decimal("0.10"), Decimal("0.10"), Decimal("0.22")),
        FailureCase("CREDIT-SPREAD-BLOWOUT", "credit", Decimal("0.06"), Decimal("0.15"), Decimal("0.16")),
        FailureCase("VOL-REGIME-FLIP", "volatility", Decimal("0.07"), Decimal("0.30"), Decimal("0.14")),
    )