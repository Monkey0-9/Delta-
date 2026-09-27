from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FailureType(StrEnum):
    NETWORK = "network"
    BROKER = "broker"
    MARKET_DATA = "market_data"
    DUPLICATE_EVENT = "duplicate_event"
    OUT_OF_ORDER_EVENT = "out_of_order_event"
    STALE_DATA = "stale_data"
    PROCESS_CRASH = "process_crash"
    STORAGE_FAILURE = "storage_failure"
    MODEL_FAILURE = "model_failure"
    RISK_FAILURE = "risk_failure"


@dataclass(frozen=True, slots=True)
class FailureInjection:
    failure_type: FailureType
    probability: float = 1.0
    duration_ms: int = 0

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(
                "probability must be between 0 and 1"
            )

        if self.duration_ms < 0:
            raise ValueError(
                "duration_ms cannot be negative"
            )