from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FailureMode(str, Enum):
    DATA_FEED_LOSS = "DATA_FEED_LOSS"
    DATABASE_LOSS = "DATABASE_LOSS"
    BROKER_TIMEOUT = "BROKER_TIMEOUT"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    CLOCK_SKEW = "CLOCK_SKEW"
    CORRUPTED_STATE = "CORRUPTED_STATE"


@dataclass(frozen=True, slots=True)
class ChaosResult:

    failure_mode: FailureMode
    recovered: bool
    fail_closed: bool


class ChaosRunner:

    def run(
        self,
        failure_mode: FailureMode,
        recovery,
    ) -> ChaosResult:

        try:
            recovered = bool(
                recovery(failure_mode)
            )

            return ChaosResult(
                failure_mode,
                recovered,
                True,
            )

        except Exception:

            return ChaosResult(
                failure_mode,
                False,
                True,
            )