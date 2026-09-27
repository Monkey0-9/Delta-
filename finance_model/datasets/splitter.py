from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True, slots=True)
class TemporalSplit:
    train: tuple[int, ...]
    validation: tuple[int, ...]
    test: tuple[int, ...]


def chronological_split(
    timestamps: Sequence[datetime],
    *,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
    purge: int = 0,
    embargo: int = 0,
) -> TemporalSplit:
    if not timestamps:
        raise ValueError("timestamps cannot be empty")

    if not 0.0 < train_fraction < 1.0:
        raise ValueError("invalid train_fraction")

    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("invalid validation_fraction")

    if train_fraction + validation_fraction >= 1.0:
        raise ValueError("train + validation must be < 1")

    ordered = sorted(
        enumerate(timestamps),
        key=lambda x: x[1],
    )

    n = len(ordered)

    train_end = int(n * train_fraction)
    validation_end = int(
        n * (train_fraction + validation_fraction)
    )

    train = tuple(
        index for index, _ in ordered[:train_end]
    )

    validation = tuple(
        index
        for index, _ in ordered[train_end + embargo:validation_end]
    )

    test = tuple(
        index
        for index, _ in ordered[validation_end + embargo:]
    )

    if purge:
        train = train[: max(0, len(train) - purge)]
        validation = validation[: max(0, len(validation) - purge)]

    if set(train) & set(validation) or set(train) & set(test) or set(validation) & set(test):
        raise ValueError("purge/embargo insufficient: splits overlap.")

    return TemporalSplit(
        train=train,
        validation=validation,
        test=test,
    )