from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class Window:

    train_start: int
    train_end: int
    test_start: int
    test_end: int


@dataclass(frozen=True, slots=True)
class WindowResult:

    window: Window
    metric: float


class WalkForward:

    def __init__(
        self,
        train_size: int,
        test_size: int,
        step: int,
        purge: int = 0,
        embargo: int = 0,
    ):

        if min(
            train_size,
            test_size,
            step,
        ) <= 0:
            raise ValueError(
                "window sizes must be positive"
            )

        if purge < 0 or embargo < 0:
            raise ValueError("purge/embargo must be non-negative")

        self.train_size = train_size
        self.test_size = test_size
        self.step = step
        self.purge = purge
        self.embargo = embargo

    def windows(
        self,
        n: int,
    ) -> list[Window]:

        result = []

        start = 0

        while (
            start
            + self.train_size
            + self.embargo
            + self.test_size
            <= n
        ):

            train_end = start + self.train_size - self.purge
            if train_end <= start:
                raise ValueError("purge >= train window.")
            test_start = start + self.train_size + self.embargo
            result.append(
                Window(
                    start,
                    train_end,
                    test_start,
                    test_start
                    + self.test_size,
                )
            )

            start += self.step

        return result

    def run(
        self,
        n: int,
        evaluator: Callable[
            [Window],
            float,
        ],
    ):

        return tuple(
            WindowResult(
                window,
                evaluator(window),
            )
            for window in self.windows(n)
        )