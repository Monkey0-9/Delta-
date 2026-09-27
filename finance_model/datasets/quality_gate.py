from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable


@dataclass(frozen=True, slots=True)
class QualityViolation:
    record_id: str
    field: str
    violation_type: str
    message: str


@dataclass(frozen=True, slots=True)
class QualityReport:
    total_records: int
    valid_records: int
    violations: tuple[QualityViolation, ...]

    @property
    def passed(self) -> bool:
        return not self.violations

    @property
    def violation_count(self) -> int:
        return len(self.violations)


class DatasetQualityGate:
    """
    Deterministic data-quality gate.

    The gate checks structural and numerical validity but deliberately
    does not perform statistical distribution drift detection.
    """

    def __init__(
        self,
        *,
        required_fields: tuple[str, ...] = (
            "record_id",
            "asset",
            "decision_time",
        ),
        numeric_fields: tuple[str, ...] = (),
        min_numeric: dict[str, float] | None = None,
        max_numeric: dict[str, float] | None = None,
        allow_nan: bool = False,
        allow_infinite: bool = False,
    ) -> None:
        self.required_fields = required_fields
        self.numeric_fields = numeric_fields
        self.min_numeric = min_numeric or {}
        self.max_numeric = max_numeric or {}
        self.allow_nan = allow_nan
        self.allow_infinite = allow_infinite

    def validate(
        self,
        records: Iterable[dict[str, object]],
    ) -> QualityReport:
        rows = list(records)
        violations: list[QualityViolation] = []

        seen: set[str] = set()

        for index, record in enumerate(rows):
            record_id = str(
                record.get(
                    "record_id",
                    f"<row-{index}>",
                )
            )

            # Required fields
            for field in self.required_fields:
                value = record.get(field)

                if value is None:
                    violations.append(
                        QualityViolation(
                            record_id=record_id,
                            field=field,
                            violation_type="missing",
                            message=f"Required field '{field}' is missing",
                        )
                    )
                    continue

                if isinstance(value, str) and not value.strip():
                    violations.append(
                        QualityViolation(
                            record_id=record_id,
                            field=field,
                            violation_type="empty",
                            message=f"Required field '{field}' is empty",
                        )
                    )

            # Duplicate IDs
            if record_id in seen:
                violations.append(
                    QualityViolation(
                        record_id=record_id,
                        field="record_id",
                        violation_type="duplicate",
                        message="Duplicate record_id",
                    )
                )
            else:
                seen.add(record_id)

            # Numeric validation
            for field in self.numeric_fields:
                value = record.get(field)

                if value is None:
                    continue

                if isinstance(value, bool) or not isinstance(
                    value,
                    (int, float),
                ):
                    violations.append(
                        QualityViolation(
                            record_id=record_id,
                            field=field,
                            violation_type="type",
                            message=(
                                f"Numeric field '{field}' "
                                "must contain int or float"
                            ),
                        )
                    )
                    continue

                numeric = float(value)

                if not self.allow_nan and numeric != numeric:
                    violations.append(
                        QualityViolation(
                            record_id=record_id,
                            field=field,
                            violation_type="nan",
                            message=f"NaN detected in '{field}'",
                        )
                    )
                    continue

                if not self.allow_infinite and not isfinite(numeric):
                    violations.append(
                        QualityViolation(
                            record_id=record_id,
                            field=field,
                            violation_type="infinite",
                            message=f"Infinite value in '{field}'",
                        )
                    )
                    continue

                minimum = self.min_numeric.get(field)

                if minimum is not None and numeric < minimum:
                    violations.append(
                        QualityViolation(
                            record_id=record_id,
                            field=field,
                            violation_type="range",
                            message=(
                                f"{field}={numeric} "
                                f"is below minimum {minimum}"
                            ),
                        )
                    )

                maximum = self.max_numeric.get(field)

                if maximum is not None and numeric > maximum:
                    violations.append(
                        QualityViolation(
                            record_id=record_id,
                            field=field,
                            violation_type="range",
                            message=(
                                f"{field}={numeric} "
                                f"is above maximum {maximum}"
                            ),
                        )
                    )

        return QualityReport(
            total_records=len(rows),
            valid_records=max(
                0,
                len(rows) - len(
                    {
                        violation.record_id
                        for violation in violations
                    }
                ),
            ),
            violations=tuple(violations),
        )