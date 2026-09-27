from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
)


@dataclass(frozen=True, slots=True)
class LabelInterval:

    start: datetime
    end: datetime

    def __post_init__(self):

        if (
            self.start.tzinfo is None
            or self.end.tzinfo is None
        ):
            raise ValueError(
                "timestamps must be timezone-aware"
            )

        if self.end < self.start:
            raise ValueError(
                "end before start"
            )


class PurgedTimeSeriesSplit:

    def __init__(
        self,
        n_splits: int = 5,
        embargo: timedelta = timedelta(0),
    ):

        if n_splits < 2:
            raise ValueError(
                "n_splits must be >= 2"
            )

        if embargo < timedelta(0):
            raise ValueError(
                "embargo must be non-negative"
            )

        self.n_splits = n_splits
        self.embargo = embargo

    def split(
        self,
        intervals: list[LabelInterval],
    ):

        n = len(intervals)

        if n < self.n_splits:
            raise ValueError(
                "not enough observations"
            )

        boundaries = [
            n * i // self.n_splits
            for i in range(
                self.n_splits + 1
            )
        ]

        for fold in range(
            self.n_splits
        ):

            test_idx = list(
                range(
                    boundaries[fold],
                    boundaries[fold + 1],
                )
            )

            test_start = intervals[
                test_idx[0]
            ].start

            test_end = max(
                intervals[i].end
                for i in test_idx
            )

            embargo_end = (
                test_end
                + self.embargo
            )

            train_idx = []

            for index, label in enumerate(
                intervals
            ):

                if index in test_idx:
                    continue

                overlaps = (
                    label.start <= test_end
                    and label.end >= test_start
                )

                embargoed = (
                    label.start <= embargo_end
                    and label.end >= test_end
                )

                if (
                    not overlaps
                    and not embargoed
                ):
                    train_idx.append(
                        index
                    )

            yield train_idx, test_idx