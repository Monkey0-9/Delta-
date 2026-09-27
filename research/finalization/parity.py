from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParityResult:
    name: str
    passed: bool
    maximum_absolute_error: float
    maximum_relative_error: float
    tolerance: float


def compare_vectors(
    name: str,
    reference: list[float],
    candidate: list[float],
    tolerance: float = 1e-10,
) -> ParityResult:

    if len(reference) != len(candidate):
        raise ValueError(
            "Vector length mismatch."
        )

    max_abs = 0.0
    max_rel = 0.0

    for a, b in zip(
        reference,
        candidate,
    ):

        abs_error = abs(a - b)

        denominator = max(
            abs(a),
            abs(b),
            1e-30,
        )

        rel_error = (
            abs_error
            / denominator
        )

        max_abs = max(
            max_abs,
            abs_error,
        )

        max_rel = max(
            max_rel,
            rel_error,
        )

    passed = (
        max_abs <= tolerance
        or max_rel <= tolerance
    )

    return ParityResult(
        name=name,
        passed=passed,
        maximum_absolute_error=max_abs,
        maximum_relative_error=max_rel,
        tolerance=tolerance,
    )
