"""EMS: execution-management routing with no venue bypass.

Institutional invariant: the ONLY sanctioned path from intent to broker is
``Strategy/AI -> OrderGateway -> RiskFirewall -> broker adapter``. A direct
``AI -> venue`` call that skips kill/firewall/idempotency/audit is a P0
safety violation.

This adapter therefore refuses to touch the venue unless a gateway or
firewall is bound (constructor-injected, ``None`` by default so unbound
construction never silently fills). When bound, every submission is
admission-checked through the firewall path and audit-logged — including
refusals. The venue is never called on the bypass path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5


class BrokerError(Exception):
    """Raised when a submission bypasses the sanctioned OrderGateway path."""


@dataclass(frozen=True, slots=True)
class ExecutionRequest:

    order_id: str
    asset: str
    quantity: float


@dataclass(frozen=True, slots=True)
class ExecutionAck:

    order_id: str
    accepted: bool
    broker_order_id: str | None
    message: str


class ExecutionVenue(Protocol):

    def submit(
        self,
        request: ExecutionRequest,
    ) -> ExecutionAck:
        ...


def _intent_from_request(request: ExecutionRequest):
    """Map an execution request to a firewall TradeIntent (lazy import).

    Imported lazily so this module stays import-cycle safe: the firewall
    package never imports the EMS package back.

    EMS ExecutionRequest is buy-only: quantity must be positive. There is no
    sell path here (``submit`` already refuses qty <= 0); a non-positive
    quantity raises rather than implying a sell side.
    """
    try:
        from risk.pre_trade.validation import TradeIntent
    except ImportError:  # installed-package layout
        from delta.risk.pre_trade.validation import TradeIntent  # type: ignore

    if request.quantity <= 0:
        raise ValueError(
            "EMS ExecutionRequest is buy-only: quantity must be positive"
        )
    return TradeIntent(
        order_id=uuid5(NAMESPACE_URL, f"ems:{request.order_id}"),
        instrument_id=uuid5(NAMESPACE_URL, f"ems-asset:{request.asset}"),
        side="buy",
        quantity=Decimal(str(request.quantity)).copy_abs(),
        limit_price=None,
        # The request reached EMS only via the gateway-authorized strategy
        # path; this check enforces kill/limits/stale/idempotency, not the
        # upstream strategy authorization itself.
        idempotency_key=request.order_id,
        authorized=True,
        price_source="real",
    )


class EMS:

    def __init__(
        self,
        venue: ExecutionVenue,
        *,
        gateway: Any | None = None,
        firewall: Any | None = None,
    ):
        self.venue = venue
        self.gateway = gateway
        self._firewall = firewall if firewall is not None else (
            getattr(gateway, "firewall", None)
        )
        self.audit_log: list[dict[str, Any]] = []

    def submit_via_gateway(
        self,
        request: ExecutionRequest,
    ) -> ExecutionAck:
        """Narrow gateway/firewall seam: admit, then submit, always audited."""
        if self.gateway is None and self._firewall is None:
            raise BrokerError(
                "must route via OrderGateway: EMS has no gateway/firewall bound; "
                "direct AI->venue submission is refused"
            )
        firewall = self._firewall
        if firewall is None and self.gateway is not None:
            firewall = getattr(self.gateway, "firewall", None)
        if firewall is None:
            raise BrokerError(
                "must route via OrderGateway: bound gateway exposes no firewall; "
                "direct AI->venue submission is refused"
            )
        try:
            decision = firewall.check(_intent_from_request(request))
        except Exception as exc:
            # Fail closed: a firewall that errors (including kill-halt
            # exceptions) never admits the order to the venue.
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "order_id": request.order_id,
                "admitted": False,
                "reason": f"firewall error: {exc} (kill)",
                "broker_ack": None,
            }
            self.audit_log.append(entry)
            return ExecutionAck(
                request.order_id,
                False,
                None,
                f"firewall error: {exc} (kill)",
            )
        verdict = getattr(decision.verdict, "value", str(decision.verdict))
        if verdict != "approve":
            reasons = ",".join(decision.reasons)
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "order_id": request.order_id,
                "admitted": False,
                "reason": f"firewall refused: {reasons}",
                "risk_decision_id": getattr(decision, "risk_decision_id", ""),
                "broker_ack": None,
            }
            self.audit_log.append(entry)
            return ExecutionAck(
                request.order_id,
                False,
                None,
                f"firewall refused: {reasons}",
            )
        ack = None
        try:
            ack = self.venue.submit(request)
        except Exception as exc:
            # The firewall reserved request.order_id on APPROVE above. A
            # venue failure must not burn the key, or a legit retry of the
            # same order_id refuses as a duplicate. Release best-effort and
            # return a retryable (not accepted) ack; the retry re-runs the
            # full firewall admission path.
            seen = getattr(firewall, "_seen_keys", None)
            if seen is not None:
                try:
                    seen.discard(request.order_id)
                except Exception:
                    pass
            reason = f"venue error (retryable): {exc}"
            self.audit_log.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "order_id": request.order_id,
                "admitted": True,
                "reason": reason,
                "risk_decision_id": getattr(decision, "risk_decision_id", ""),
                "broker_ack": None,
            })
            return ExecutionAck(request.order_id, False, None, reason)
        self.audit_log.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "order_id": request.order_id,
            "admitted": True,
            "reason": "firewall approved",
            "risk_decision_id": getattr(decision, "risk_decision_id", ""),
            "broker_ack": {
                "accepted": ack.accepted,
                "broker_order_id": ack.broker_order_id,
            },
        })
        return ack

    def submit(
        self,
        request: ExecutionRequest,
    ) -> ExecutionAck:

        if request.quantity <= 0:
            raise ValueError(
                "invalid execution quantity"
            )

        return self.submit_via_gateway(
            request
        )
