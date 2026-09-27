from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class CalibrationBin:

    lower: float
    upper: float
    count: int
    mean_confidence: float
    empirical_accuracy: float

    @property
    def calibration_gap(self) -> float:
        return abs(
            self.mean_confidence
            - self.empirical_accuracy
        )


@dataclass(frozen=True, slots=True)
class CalibrationReport:

    bins: tuple[CalibrationBin, ...]
    expected_calibration_error: float
    maximum_calibration_error: float
    brier_score: float
    observations: int


class ProbabilityCalibrator:

    def __init__(
        self,
        bins: int = 10,
    ):
        if bins < 2:
            raise ValueError(
                "bins must be >= 2"
            )

        self.bins = bins

    def evaluate(
        self,
        probabilities: list[float],
        outcomes: list[int],
    ) -> CalibrationReport:

        if len(probabilities) != len(outcomes):
            raise ValueError(
                "probabilities/outcomes length mismatch"
            )

        if not probabilities:
            raise ValueError(
                "empty calibration sample"
            )

        for p in probabilities:
            if not 0.0 <= p <= 1.0:
                raise ValueError(
                    "probability outside [0,1]"
                )

        for y in outcomes:
            if y not in (0, 1):
                raise ValueError(
                    "outcome must be 0 or 1"
                )

        bins = []

        for index in range(self.bins):

            lower = index / self.bins
            upper = (
                (index + 1)
                / self.bins
            )

            selected = [
                (p, y)
                for p, y in zip(
                    probabilities,
                    outcomes,
                )
                if (
                    p >= lower
                    and (
                        p < upper
                        or (
                            index
                            == self.bins - 1
                            and p <= upper
                        )
                    )
                )
            ]

            if not selected:
                continue

            mean_p = sum(
                p for p, _ in selected
            ) / len(selected)

            accuracy = sum(
                y for _, y in selected
            ) / len(selected)

            bins.append(
                CalibrationBin(
                    lower,
                    upper,
                    len(selected),
                    mean_p,
                    accuracy,
                )
            )

        total = len(probabilities)

        ece = sum(
            (
                item.count
                / total
            )
            * item.calibration_gap
            for item in bins
        )

        mce = max(
            (
                item.calibration_gap
                for item in bins
            ),
            default=0.0,
        )

        brier = sum(
            (
                p - y
            ) ** 2
            for p, y in zip(
                probabilities,
                outcomes,
            )
        ) / total

        return CalibrationReport(
            tuple(bins),
            ece,
            mce,
            brier,
            total,
        )