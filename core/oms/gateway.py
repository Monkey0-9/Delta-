"""Fail-closed OMS gateway: the ONLY sanctioned path from intent to broker.

Architecture (institutional invariant)::

    Strategy / AI proposal
        -> canonical core.domain.Order (validated, idempotent)
        -> risk.firewall.RiskFirewall.check (kill + limits + stale + audit)
        -> broker adapter (paper / Alpaca / IBKR / FIX)
        -> acknowledgement / fill / reconciliation

Never ``AI -> broker``. Any direct broker call that bypasses this gateway
is a P0 safety violation. The gateway:

* resolves the import duality (``core.*`` vs ``delta.core.*``) defensively
* maps the canonical Order to a TradeIntent without float coercion
  (Decimal throughout; shares vs notional never mixed)
* enforces kill-switch board (global/strategy/broker) fail-closed
* enforces idempotency (duplicate key -> BLOCK, no double-submit)
* appends an audit record for every decision (approve AND block)
* is transport-agnostic: brokers are injected as callables/adapters

References (public): FIX 4.4 order lifecycle; Alpaca trading API order
states; standard OMS/EMS separation (order management vs execution).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Protocol
from uuid import UUID

try:  # repo-root layout
    from core.domain.order import Order, OrderStatus
except ImportError:  # installed-package layout
    from delta.core.domain.order import Order, OrderStatus  # type: ignore

try:
    from risk.firewall.firewall import RiskFirewall
    from risk.pre_trade.validation import RiskVerdict, TradeIntent
except ImportError:  # installed-package layout
    from delta.risk.firewall.firewall import RiskFirewall  # type: ignore
    from delta.risk.pre_trade.validation import RiskVerdict, TradeIntent  # type: ignore


class BrokerSubmit(Protocol):
    def __call__(self, order: Order) -> dict[str, Any]: ...


@dataclass
class GatewayDecision:
    approved: bool
    order: Order
    reasons: tuple[str, ...] = ()
    risk_decision_id: str = ""
    audit_entry: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderGateway:
    """Single fail-closed order path. Fail closed over fail open."""

    firewall: RiskFirewall
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def submit(
        self,
        order: Order,
        *,
        ref_price: Decimal | None = None,
        current_position: Decimal = Decimal("0"),
        data_age_s: float = 0.0,
        authorized: bool = False,
        price_source: str = "real",
        broker: BrokerSubmit | None = None,
        now: datetime | None = None,
    ) -> GatewayDecision:
        ts = now or datetime.now(timezone.utc)
        intent = TradeIntent(
            order_id=order.order_id,
            instrument_id=order.instrument_id,
            side=order.side.value,
            quantity=order.quantity,
            limit_price=order.limit_price,
            idempotency_key=order.idempotency_key,
            authorized=authorized,
            price_source=price_source,
        )
        decision = self.firewall.check(
            intent,
            ref_price=ref_price,
            current_position=current_position,
            data_age_s=data_age_s,
            now=ts,
        )
        entry: dict[str, Any] = {
            "ts": ts.isoformat(),
            "order_id": str(order.order_id),
            "idempotency_key": order.idempotency_key,
            "verdict": decision.verdict.value,
            "reasons": list(decision.reasons),
            "risk_decision_id": decision.risk_decision_id,
        }
        if decision.verdict != RiskVerdict.APPROVE:
            entry["broker_ack"] = None
            self.audit_log.append(entry)
            return GatewayDecision(
                approved=False,
                order=order,
                reasons=decision.reasons,
                risk_decision_id=decision.risk_decision_id,
                audit_entry=entry,
            )
        # Approved: advance lifecycle CREATED -> VALIDATED -> RISK_APPROVED
        # -> SUBMITTED. Any broker exception -> SUBMITTED -> FAILED (both are
        # legal transitions; returning a RISK_APPROVED object for a failed
        # submit is a state lie and is forbidden).
        try:
            o1 = order.transition(OrderStatus.VALIDATED, timestamp=ts)
            o2 = o1.transition(OrderStatus.RISK_APPROVED, timestamp=ts)
        except ValueError as exc:
            entry["broker_ack"] = None
            entry["lifecycle_error"] = str(exc)
            self.audit_log.append(entry)
            return GatewayDecision(False, order, ("lifecycle_transition_failed",),
                                   decision.risk_decision_id, entry)
        ack: dict[str, Any] | None = None
        if broker is not None:
            try:
                submitted = o2.transition(OrderStatus.SUBMITTED, timestamp=ts)
            except ValueError as exc:
                entry["broker_ack"] = None
                entry["lifecycle_error"] = str(exc)
                self.audit_log.append(entry)
                return GatewayDecision(False, o2, ("lifecycle_transition_failed",),
                                       decision.risk_decision_id, entry)
            try:
                ack = broker(submitted)
            except Exception as exc:  # fail closed
                failed = submitted.transition(OrderStatus.FAILED, timestamp=ts)
                entry["broker_ack"] = {"error": str(exc)}
                self.audit_log.append(entry)
                return GatewayDecision(False, failed, ("broker_submit_failed",),
                                       decision.risk_decision_id, entry)
            entry["broker_ack"] = ack
            self.audit_log.append(entry)
            return GatewayDecision(True, submitted, (), decision.risk_decision_id, entry)
        entry["broker_ack"] = ack
        self.audit_log.append(entry)
        return GatewayDecision(True, o2, (), decision.risk_decision_id, entry)


def canonical_to_legacy_kwargs(order: Order, *, symbol: str) -> dict[str, Any]:
    """Explicit canonical (Decimal/UUID) -> legacy broker-ticket mapping.

    Rejects silently-unsafe coercion: fractional share quantities and
    non-positive prices raise instead of truncating. The caller supplies
    ``symbol`` because the canonical Order carries only ``instrument_id``;
    symbol resolution belongs to the security master, never to the gateway.
    """
    from decimal import InvalidOperation
    qty = order.quantity
    if qty != qty.to_integral_value():
        raise ValueError(f"fractional share quantity cannot map to broker ticket: {qty}")
    if qty <= 0:
        raise ValueError(f"non-positive quantity: {qty}")
    kw: dict[str, Any] = {
        "symbol": symbol,
        "side": order.side.value,
        "order_type": order.order_type.value,
        "quantity": int(qty),
        "time_in_force": order.time_in_force.value,
    }
    if order.limit_price is not None:
        if order.limit_price <= 0:
            raise ValueError(f"non-positive limit price: {order.limit_price}")
        kw["price"] = float(order.limit_price)
    if order.stop_price is not None:
        if order.stop_price <= 0:
            raise ValueError(f"non-positive stop price: {order.stop_price}")
        kw["stop_price"] = float(order.stop_price)
    return kw


def _next(order: Order) -> frozenset:  # minimal helper for transition reachability
    try:
        from core.domain.order import _ALLOWED_TRANSITIONS as _T
    except ImportError:
        from delta.core.domain.order import _ALLOWED_TRANSITIONS as _T  # type: ignore
    return _T.get(order.status, frozenset())


__all__ = ["OrderGateway", "GatewayDecision", "BrokerSubmit", "canonical_to_legacy_kwargs"]
