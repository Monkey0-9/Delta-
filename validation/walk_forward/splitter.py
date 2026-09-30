from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WalkForwardSplit:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def walk_forward_splits(
    n: int, *, train: int, test: int, step: int, purge: int = 1, embargo: int = 1
) -> list[WalkForwardSplit]:
    """Chronological splits with no overlap between train and test.

    purge: bars dropped from the end of each train window (leakage guard).
    embargo: bars skipped between train-end and test-start (adjacent-info guard).
    P0 fail-closed fix (2026-09-30): defaults are now 1/1, not 0/0. A zero
    purge/embargo silently permits look-ahead when labels span multiple bars
    (Lopez de Prado AFML Ch.7). Callers needing the legacy exact partition
    for non-temporal unit tests must pass purge=0, embargo=0 explicitly and
    document why temporal leakage is impossible.
    """
    if purge < 0 or embargo < 0:
        raise ValueError("purge/embargo must be >= 0.")
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
