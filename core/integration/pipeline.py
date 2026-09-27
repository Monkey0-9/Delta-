from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Protocol

from core.contracts.integration import (
    Action,
    DecisionIntent,
    ExecutionIntent,
    IntegrationEnvelope,
    RiskDecision,
    RiskStatus,
    Stage,
    WorldSnapshotRef,
)

from core.integration.idempotency import IdempotencyStore


class WorldStatePort(Protocol):

    def snapshot(
        self,
        instrument_id: str,
    ) -> WorldSnapshotRef:
        ...


class DecisionPort(Protocol):

    def decide(
        self,
        *,
        instrument_id: str,
        world_state: WorldSnapshotRef,
        mandate: Mapping[str, Any],
    ) -> DecisionIntent:
        ...


class RiskPort(Protocol):

    def evaluate(
        self,
        intent: DecisionIntent,
        *,
        world_state: WorldSnapshotRef,
    ) -> RiskDecision:
        ...


class AuthorizationPort(Protocol):

    def authorize(
        self,
        intent: ExecutionIntent,
    ) -> bool:
        ...


class ExecutionPort(Protocol):

    def submit(
        self,
        intent: ExecutionIntent,
    ) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True, slots=True)
class IntegrationResult:

    correlation_id: str

    decision: DecisionIntent

    risk: RiskDecision

    execution: Mapping[str, Any] | None

    envelopes: tuple[
        IntegrationEnvelope,
        ...,
    ]


class IntegrationError(RuntimeError):
    pass


class AuthorizationDenied(IntegrationError):
    pass


class StaleState(IntegrationError):
    pass


class IntegrationCoordinator:

    def __init__(
        self,
        world_state: WorldStatePort,
        decision: DecisionPort,
        risk: RiskPort,
        authorization: AuthorizationPort,
        execution: ExecutionPort,
        *,
        idempotency: IdempotencyStore | None = None,
        max_state_age_seconds: float = 300.0,
    ) -> None:

        if max_state_age_seconds < 0:
            raise ValueError(
                "max_state_age_seconds must be >= 0"
            )

        self.world_state = world_state
        self.decision = decision
        self.risk = risk
        self.authorization = authorization
        self.execution = execution

        self.idempotency = (
            idempotency
            or IdempotencyStore()
        )

        self.max_state_age_seconds = (
            max_state_age_seconds
        )

    @staticmethod
    def _correlation(
        instrument_id: str,
        state: WorldSnapshotRef,
    ) -> str:

        raw = (
            f"{instrument_id}|"
            f"{state.state_id}|"
            f"{state.version}|"
            f"{state.state_hash}"
        )

        return (
            "CORR-"
            + sha256(
                raw.encode()
            ).hexdigest()[:24]
        )

    def run(
        self,
        *,
        instrument_id: str,
        mandate: Mapping[str, Any],
        now: datetime | None = None,
    ) -> IntegrationResult:

        current = (
            now
            or datetime.now(timezone.utc)
        )

        if current.tzinfo is None:
            raise ValueError(
                "now must be timezone-aware"
            )

        # --------------------------------------------------
        # 1. WORLD STATE
        # --------------------------------------------------

        state = self.world_state.snapshot(
            instrument_id
        )

        age = (
            current - state.as_of
        ).total_seconds()

        if age < 0:
            raise StaleState(
                "world state is from the future"
            )

        if age > self.max_state_age_seconds:
            raise StaleState(
                "world state is stale: "
                f"age={age:.3f}s"
            )

        correlation = self._correlation(
            instrument_id,
            state,
        )

        envelopes: list[
            IntegrationEnvelope
        ] = []

        envelopes.append(
            IntegrationEnvelope.build(
                correlation,
                Stage.WORLD_STATE,
                {
                    "state_id": state.state_id,
                    "version": state.version,
                    "state_hash": state.state_hash,
                    "source_hash": state.source_hash,
                    "as_of": state.as_of.isoformat(),
                },
            )
        )

        # --------------------------------------------------
        # 2. DECISION
        # --------------------------------------------------

        decision = self.decision.decide(
            instrument_id=instrument_id,
            world_state=state,
            mandate=mandate,
        )

        if decision.world_state != state:
            raise IntegrationError(
                "decision references "
                "a different world state"
            )

        envelopes.append(
            IntegrationEnvelope.build(
                correlation,
                Stage.DECISION,
                {
                    "decision_id":
                        decision.decision_id,
                    "action":
                        decision.action.value,
                    "quantity":
                        decision.quantity,
                    "model_version":
                        decision.model_version,
                    "strategy_version":
                        decision.strategy_version,
                    "world_state_version":
                        decision.world_state.version,
                },
                envelopes[-1].envelope_hash(),
            )
        )

        # --------------------------------------------------
        # 3. RISK
        # --------------------------------------------------

        risk = self.risk.evaluate(
            decision,
            world_state=state,
        )

        if risk.decision_id != (
            decision.decision_id
        ):
            raise IntegrationError(
                "risk decision references "
                "the wrong decision"
            )

        envelopes.append(
            IntegrationEnvelope.build(
                correlation,
                Stage.RISK,
                {
                    "risk_decision_id":
                        risk.risk_decision_id,
                    "decision_id":
                        risk.decision_id,
                    "status":
                        risk.status.value,
                    "approved_quantity":
                        risk.approved_quantity,
                    "limits_version":
                        risk.limits_version,
                    "data_fresh":
                        risk.data_fresh,
                },
                envelopes[-1].envelope_hash(),
            )
        )

        # --------------------------------------------------
        # NON-TRADING DECISIONS
        # --------------------------------------------------

        if decision.action not in (
            Action.BUY,
            Action.SELL,
        ):

            return IntegrationResult(
                correlation,
                decision,
                risk,
                None,
                tuple(envelopes),
            )

        # --------------------------------------------------
        # RISK BLOCK
        # --------------------------------------------------

        if (
            risk.status is RiskStatus.BLOCKED
            or risk.approved_quantity <= 0
        ):

            return IntegrationResult(
                correlation,
                decision,
                risk,
                None,
                tuple(envelopes),
            )

        if not risk.data_fresh:
            raise IntegrationError(
                "risk layer approved stale data"
            )

        # --------------------------------------------------
        # 4. EXECUTION INTENT
        # --------------------------------------------------

        order_id = (
            "ORD-"
            + sha256(
                (
                    correlation
                    + decision.decision_id
                ).encode()
            ).hexdigest()[:24]
        )

        idempotency_key = (
            f"{order_id}:"
            f"{risk.risk_decision_id}:"
            f"{risk.approved_quantity:.12g}"
        )

        execution_intent = ExecutionIntent(
            order_id=order_id,
            idempotency_key=idempotency_key,
            decision_id=decision.decision_id,
            risk_decision_id=(
                risk.risk_decision_id
            ),
            instrument_id=(
                decision.instrument_id
            ),
            action=decision.action,
            quantity=risk.approved_quantity,
            created_at=current,
        )

        # --------------------------------------------------
        # 5. AUTHORIZATION
        # --------------------------------------------------

        envelopes.append(
            IntegrationEnvelope.build(
                correlation,
                Stage.AUTHORIZATION,
                {
                    "order_id": order_id,
                    "idempotency_key":
                        idempotency_key,
                    "decision_id":
                        decision.decision_id,
                    "risk_decision_id":
                        risk.risk_decision_id,
                },
                envelopes[-1].envelope_hash(),
            )
        )

        authorized = (
            self.authorization.authorize(
                execution_intent
            )
        )

        if not authorized:
            raise AuthorizationDenied(
                "execution authorization denied"
            )

        # --------------------------------------------------
        # 6. IDEMPOTENCY RESERVATION
        # --------------------------------------------------

        reservation_owner = (
            f"{correlation}:"
            f"{decision.decision_id}"
        )

        reserved = self.idempotency.reserve(
            idempotency_key,
            reservation_owner,
        )

        if not reserved:

            previous = self.idempotency.result(
                idempotency_key
            )

            if previous is not None:
                return IntegrationResult(
                    correlation,
                    decision,
                    risk,
                    previous,
                    tuple(envelopes),
                )

            raise IntegrationError(
                "duplicate execution request is "
                "already reserved but has no "
                "completed result"
            )

        # --------------------------------------------------
        # 7. EXECUTION
        # --------------------------------------------------

        envelopes.append(
            IntegrationEnvelope.build(
                correlation,
                Stage.EXECUTION,
                {
                    "order_id": order_id,
                    "decision_id":
                        decision.decision_id,
                    "risk_decision_id":
                        risk.risk_decision_id,
                    "quantity":
                        risk.approved_quantity,
                },
                envelopes[-1].envelope_hash(),
            )
        )

        result = self.execution.submit(
            execution_intent
        )

        # --------------------------------------------------
        # 8. IDEMPOTENCY COMPLETION
        # --------------------------------------------------

        result_dict = dict(result)

        self.idempotency.complete(
            idempotency_key,
            result_dict,
        )

        return IntegrationResult(
            correlation,
            decision,
            risk,
            result_dict,
            tuple(envelopes),
        )