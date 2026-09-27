from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WalkForwardSplit:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def walk_forward_splits(
    n: int, *, train: int, test: int, step: int, purge: int = 0, embargo: int = 0
) -> list[WalkForwardSplit]:
    """Chronological splits with no overlap between train and test.

    purge: bars dropped from the end of each train window (leakage guard).
    embargo: bars skipped between train-end and test-start (adjacent-info guard).
    Both default to 0 for backward compatibility.
    """
    splits: list[WalkForwardSplit] = []
    start = 0
    while start + train + test + embargo <= n:
        train_end = start + train - purge
        if train_end <= start:
            raise ValueError("purge >= train window.")
        test_start = start + train + embargo
        splits.append(WalkForwardSplit(start, train_end, test_start, test_start + test))
        start += step
    if not splits:
        raise ValueError("not enough data for one split.")
    return splits
