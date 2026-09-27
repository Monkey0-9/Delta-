from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from typing import Any, Mapping


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


class Stage(StrEnum):
    WORLD_STATE = "WORLD_STATE"
    DECISION = "DECISION"
    RISK = "RISK"
    AUTHORIZATION = "AUTHORIZATION"
    EXECUTION = "EXECUTION"


class Action(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"


class RiskStatus(StrEnum):
    APPROVED = "APPROVED"
    REDUCED = "REDUCED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class WorldSnapshotRef:
    state_id: str
    version: int
    state_hash: str
    as_of: datetime
    source_hash: str

    def __post_init__(self) -> None:
        if not self.state_id:
            raise ValueError("state_id is required")

        if self.version < 0:
            raise ValueError("version must be >= 0")

        if len(self.state_hash) != 64:
            raise ValueError("state_hash must be SHA-256")

        if len(self.source_hash) != 64:
            raise ValueError("source_hash must be SHA-256")

        if self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")


@dataclass(frozen=True, slots=True)
class DecisionIntent:
    decision_id: str
    instrument_id: str
    action: Action
    quantity: float

    horizon: str

    model_version: str
    strategy_version: str

    world_state: WorldSnapshotRef

    confidence: float
    expected_return: float
    expected_risk: float

    evidence_ids: tuple[str, ...]

    policy_version: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise ValueError("decision_id is required")

        if not self.instrument_id:
            raise ValueError("instrument_id is required")

        if self.quantity < 0:
            raise ValueError("quantity cannot be negative")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")

        if not self.model_version:
            raise ValueError("model_version is required")

        if not self.strategy_version:
            raise ValueError("strategy_version is required")

        if not self.policy_version:
            raise ValueError("policy_version is required")

        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    risk_decision_id: str
    decision_id: str

    status: RiskStatus

    approved_quantity: float

    limits_version: str
    reasons: tuple[str, ...]

    checked_at: datetime

    data_fresh: bool
    authorization_required: bool

    def __post_init__(self) -> None:
        if not self.risk_decision_id:
            raise ValueError("risk_decision_id is required")

        if not self.decision_id:
            raise ValueError("decision_id is required")

        if self.approved_quantity < 0:
            raise ValueError("approved_quantity cannot be negative")

        if not self.limits_version:
            raise ValueError("limits_version is required")

        if self.checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")

        if (
            self.status is RiskStatus.BLOCKED
            and self.approved_quantity != 0
        ):
            raise ValueError(
                "BLOCKED risk decision must approve zero quantity"
            )


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    order_id: str
    idempotency_key: str

    decision_id: str
    risk_decision_id: str

    instrument_id: str
    action: Action
    quantity: float

    created_at: datetime

    def __post_init__(self) -> None:
        if not self.order_id:
            raise ValueError("order_id is required")

        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")

        if not self.decision_id:
            raise ValueError("decision_id is required")

        if not self.risk_decision_id:
            raise ValueError("risk_decision_id is required")

        if self.quantity <= 0:
            raise ValueError("execution quantity must be > 0")

        if self.action not in (Action.BUY, Action.SELL):
            raise ValueError(
                "only BUY/SELL may become execution intents"
            )

        if self.created_at.tzinfo is None:
            raise ValueError(
                "created_at must be timezone-aware"
            )


@dataclass(frozen=True, slots=True)
class IntegrationEnvelope:
    correlation_id: str
    stage: Stage

    payload_hash: str
    parent_hash: str

    created_at: datetime

    schema_version: str = "wave45.v1"

    @classmethod
    def build(
        cls,
        correlation_id: str,
        stage: Stage,
        payload: Mapping[str, Any],
        parent_hash: str = "",
        *,
        created_at: datetime | None = None,
    ) -> "IntegrationEnvelope":

        now = created_at or utc_now()

        return cls(
            correlation_id=correlation_id,
            stage=stage,
            payload_hash=stable_hash(payload),
            parent_hash=parent_hash,
            created_at=now,
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def envelope_hash(self) -> str:
        return stable_hash(self.as_dict())