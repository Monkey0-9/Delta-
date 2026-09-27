from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from validation.walk_forward.splitter import walk_forward_splits


@dataclass(frozen=True, slots=True)
class FoldResult:
    split_index: int
    metric: Decimal
    passed: bool


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    folds: tuple[FoldResult, ...]
    pass_rate: Decimal
    passed: bool


def run_walk_forward(
    n: int,
    *,
    train: int,
    test: int,
    step: int,
    evaluate: Callable[[int, int, int, int], Decimal],
    min_metric: Decimal = Decimal("0"),
    min_pass_rate: Decimal = Decimal("0.5"),
) -> WalkForwardReport:
    """Execute fn over chronological splits. Deterministic, fail-closed."""
    splits = walk_forward_splits(n, train=train, test=test, step=step)
    folds: list[FoldResult] = []
    for i, s in enumerate(splits):
        metric = evaluate(s.train_start, s.train_end, s.test_start, s.test_end)
        folds.append(FoldResult(i, metric, metric >= min_metric))
    rate = Decimal(str(sum(1 for f in folds if f.passed) / len(folds)))
    return WalkForwardReport(tuple(folds), rate, rate >= min_pass_rate)
