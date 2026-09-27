from __future__ import annotations
from decimal import Decimal


def brier_score(probs: tuple[Decimal, ...], outcomes: tuple[int, ...]) -> Decimal:
    if len(probs) != len(outcomes) or not probs:
        raise ValueError("need non-empty aligned inputs.")
    s = sum((float(p) - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)
    return Decimal(str(s))


def expected_calibration_error(probs: tuple[Decimal, ...], outcomes: tuple[int, ...], bins: int = 10) -> Decimal:
    if len(probs) != len(outcomes) or not probs:
        raise ValueError("need non-empty aligned inputs.")
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, o in zip(probs, outcomes):
        buckets[min(int(float(p) * bins), bins - 1)].append((float(p), o))
    ece, n = 0.0, len(probs)
    for b in buckets:
        if b:
            acc = sum(o for _, o in b) / len(b)
            conf = sum(p for p, _ in b) / len(b)
            ece += abs(acc - conf) * len(b) / n
    return Decimal(str(ece))
