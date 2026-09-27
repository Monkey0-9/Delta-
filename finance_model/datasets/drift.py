from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class NumericDrift:
    field: str
    reference_count: int
    current_count: int
    reference_mean: float
    current_mean: float
    reference_std: float
    current_std: float
    mean_shift: float
    std_shift: float
    psi: float
    status: str


@dataclass(frozen=True, slots=True)
class DriftReport:
    metrics: tuple[NumericDrift, ...]

    @property
    def drifted_fields(self) -> tuple[str, ...]:
        return tuple(
            metric.field
            for metric in self.metrics
            if metric.status == "DRIFT"
        )

    @property
    def passed(self) -> bool:
        return not self.drifted_fields


class DistributionDriftDetector:
    """
    Lightweight numerical distribution-drift detector.

    The detector uses:
      - Population-independent mean shift
      - Relative standard-deviation shift
      - PSI (Population Stability Index)

    This is a research/data-quality screening mechanism.
    It is not evidence by itself that model performance degraded.

    A minimum of two observations is required on both sides before
    distribution statistics are evaluated.
    """

    def __init__(
        self,
        *,
        psi_threshold: float = 0.20,
        mean_shift_threshold: float = 0.25,
        std_shift_threshold: float = 0.50,
    ) -> None:
        if psi_threshold < 0:
            raise ValueError("psi_threshold must be >= 0")

        if mean_shift_threshold < 0:
            raise ValueError(
                "mean_shift_threshold must be >= 0"
            )

        if std_shift_threshold < 0:
            raise ValueError(
                "std_shift_threshold must be >= 0"
            )

        self.psi_threshold = psi_threshold
        self.mean_shift_threshold = mean_shift_threshold
        self.std_shift_threshold = std_shift_threshold

    @staticmethod
    def _numeric_values(
        rows: Iterable[Mapping[str, object]],
        field: str,
    ) -> list[float]:
        values: list[float] = []

        for row in rows:
            value = row.get(field)

            if isinstance(value, bool):
                continue

            if isinstance(value, (int, float)):
                value_float = float(value)

                if math.isfinite(value_float):
                    values.append(value_float)

        return values

    @staticmethod
    def _safe_relative_shift(
        reference: float,
        current: float,
    ) -> float:
        denominator = max(abs(reference), 1e-12)
        return abs(current - reference) / denominator

    @staticmethod
    def _quantile(
        values: Sequence[float],
        probability: float,
    ) -> float:
        if not values:
            raise ValueError("values must not be empty")

        ordered = sorted(values)

        if len(ordered) == 1:
            return ordered[0]

        position = probability * (len(ordered) - 1)
        lower = int(math.floor(position))
        upper = int(math.ceil(position))

        if lower == upper:
            return ordered[lower]

        weight = position - lower

        return (
            ordered[lower] * (1.0 - weight)
            + ordered[upper] * weight
        )

    @classmethod
    def _histogram(
        cls,
        values: Sequence[float],
        edges: Sequence[float],
    ) -> list[int]:
        counts = [0] * (len(edges) - 1)

        if not values:
            return counts

        for value in values:
            if value <= edges[0]:
                counts[0] += 1
                continue

            if value >= edges[-1]:
                counts[-1] += 1
                continue

            for index in range(len(edges) - 1):
                left = edges[index]
                right = edges[index + 1]

                if left <= value < right:
                    counts[index] += 1
                    break

        return counts

    @classmethod
    def _psi(
        cls,
        reference: Sequence[float],
        current: Sequence[float],
    ) -> float:
        if not reference or not current:
            return 0.0

        # Use quantile-derived bins from the reference distribution.
        quantiles = [
            cls._quantile(reference, probability)
            for probability in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        ]

        edges: list[float] = [quantiles[0]]

        for edge in quantiles[1:]:
            if edge > edges[-1]:
                edges.append(edge)

        # A constant reference distribution cannot form useful bins.
        if len(edges) < 2:
            return 0.0

        reference_counts = cls._histogram(reference, edges)
        current_counts = cls._histogram(current, edges)

        reference_total = len(reference)
        current_total = len(current)

        epsilon = 1e-6
        psi = 0.0

        for reference_count, current_count in zip(
            reference_counts,
            current_counts,
        ):
            reference_share = max(
                reference_count / reference_total,
                epsilon,
            )

            current_share = max(
                current_count / current_total,
                epsilon,
            )

            psi += (
                (current_share - reference_share)
                * math.log(current_share / reference_share)
            )

        return float(max(psi, 0.0))

    def compare(
        self,
        reference: Iterable[Mapping[str, object]],
        current: Iterable[Mapping[str, object]],
        *,
        fields: Sequence[str],
    ) -> DriftReport:
        reference_rows = list(reference)
        current_rows = list(current)

        metrics: list[NumericDrift] = []

        for field in fields:
            reference_values = self._numeric_values(
                reference_rows,
                field,
            )
            current_values = self._numeric_values(
                current_rows,
                field,
            )

            reference_count = len(reference_values)
            current_count = len(current_values)

            # Distribution statistics are not meaningful with
            # fewer than two observations on either side.
            if reference_count < 2 or current_count < 2:
                reference_mean = (
                    statistics.mean(reference_values)
                    if reference_values
                    else 0.0
                )

                current_mean = (
                    statistics.mean(current_values)
                    if current_values
                    else 0.0
                )

                reference_std = (
                    statistics.stdev(reference_values)
                    if reference_count >= 2
                    else 0.0
                )

                current_std = (
                    statistics.stdev(current_values)
                    if current_count >= 2
                    else 0.0
                )

                metrics.append(
                    NumericDrift(
                        field=field,
                        reference_count=reference_count,
                        current_count=current_count,
                        reference_mean=reference_mean,
                        current_mean=current_mean,
                        reference_std=reference_std,
                        current_std=current_std,
                        mean_shift=0.0,
                        std_shift=0.0,
                        psi=0.0,
                        status="INSUFFICIENT_DATA",
                    )
                )

                continue

            reference_mean = statistics.mean(reference_values)
            current_mean = statistics.mean(current_values)

            reference_std = statistics.stdev(reference_values)
            current_std = statistics.stdev(current_values)

            mean_shift = self._safe_relative_shift(
                reference_mean,
                current_mean,
            )

            std_shift = self._safe_relative_shift(
                reference_std,
                current_std,
            )

            psi = self._psi(
                reference_values,
                current_values,
            )

            drift_detected = (
                psi >= self.psi_threshold
                or mean_shift >= self.mean_shift_threshold
                or std_shift >= self.std_shift_threshold
            )

            status = "DRIFT" if drift_detected else "STABLE"

            metrics.append(
                NumericDrift(
                    field=field,
                    reference_count=reference_count,
                    current_count=current_count,
                    reference_mean=reference_mean,
                    current_mean=current_mean,
                    reference_std=reference_std,
                    current_std=current_std,
                    mean_shift=mean_shift,
                    std_shift=std_shift,
                    psi=psi,
                    status=status,
                )
            )

        return DriftReport(metrics=tuple(metrics))