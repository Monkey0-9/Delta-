from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from core.domain.timestamp import ensure_utc, utc_now

from .horizon import DecisionHorizon


class DecisionAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REDUCE = "reduce"
    EXIT = "exit"
    WAIT = "wait"
    NO_TRADE = "no_trade"


@dataclass(frozen=True, slots=True)
class DecisionEvidence:
    source: str
    observation: str
    contribution: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("Evidence source cannot be empty.")

        if not self.observation:
            raise ValueError("Evidence observation cannot be empty.")

        object.__setattr__(
            self,
            "timestamp",
            ensure_utc(self.timestamp),
        )


@dataclass(frozen=True, slots=True)
class Decision:
    instrument_id: UUID
    action: DecisionAction
    horizon: DecisionHorizon

    confidence: Decimal
    expected_return: Decimal

    evidence: tuple[DecisionEvidence, ...] = ()

    decision_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    model_version: str = "unknown"
    world_state_version: str = "unknown"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "created_at",
            ensure_utc(self.created_at),
        )

        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError(
                "Confidence must be between 0 and 1."
            )

        if not self.model_version:
            raise ValueError(
                "model_version cannot be empty."
            )

        if not self.world_state_version:
            raise ValueError(
                "world_state_version cannot be empty."
            )