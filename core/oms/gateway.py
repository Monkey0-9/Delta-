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
    # P0-3: approval and submission are distinct facts. approved=True with
    # submitted=False means risk approval ONLY (order sits at RISK_APPROVED);
    # submitted=True means the broker path ran and the ack was accepted.
    submitted: bool = False


def _ack_rejected(ack: Any) -> bool:
    """Explicit broker-rejection signals. Anything else counts as accepted —
    the ack must affirmatively refuse to land REJECTED."""
    if not isinstance(ack, dict):
        return False
    if ack.get("accepted") is False or ack.get("ack") is False:
        return True
    if ack.get("rejected") is True:
        return True
    return str(ack.get("status", "")).lower() in {
        "rejected", "expired", "cancelled"}


@dataclass
class OrderGateway:
    """Single fail-closed order path. Fail closed over fail open."""

    firewall: RiskFirewall
    audit_log: list[dict[str, Any]] = field(default_factory=list)
    # P0-4: production gateways require a verified role on every mutating
    # order call. require_role=False is an explicit non-production escape
    # hatch (perf harnesses, drills); it warns loudly and stamps the audit
    # trail. There is no silent legacy path.
    require_role: bool = True

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
        actor: str | None = None,
        role: Any | None = None,
        portfolio_gross: Decimal | None = None,
        portfolio_equity: Decimal | None = None,
    ) -> GatewayDecision:
        ts = now or datetime.now(timezone.utc)
        # P0-4: missing role on the production path is a refusal, not a
        # warning. The legacy warn-and-route branch survives ONLY behind
        # explicit require_role=False (non-production). Scrubbing still
        # applies on every path so a pasted token never lands at rest.
        import os as _os

        _secret = _os.environ.get("DELTA_UNLOCK_TOKEN", "") or None

        def _scrub(text: object) -> object:
            if _secret and isinstance(text, str) and _secret in text:
                return text.replace(_secret, "[REDACTED]")
            return text

        _legacy = role is None and not self.require_role
        if role is None and self.require_role:
            entry = {
                "ts": ts.isoformat(),
                "order_id": str(order.order_id),
                "idempotency_key": order.idempotency_key,
                "verdict": "block",
                "reasons": ["missing_role:role_required"],
                "risk_decision_id": "",
                "broker_ack": None,
                "submitted": False,
                "actor": _scrub(actor),
            }
            self.audit_log.append(entry)
            return GatewayDecision(False, order, ("missing_role:role_required",),
                                   "", entry, submitted=False)
        if _legacy:
            import warnings as _warnings

            _warnings.warn(
                "gateway.submit() without role= is legacy (require_role=False) "
                "and must never be used on the production execution path.",
                FutureWarning, stacklevel=2)

        # RBAC gate (optional: None preserves legacy behavior for existing
        # callers). Order routing requires RISK_OFFICER+; unknown or
        # under-privileged roles are refused with a reason and audit-logged
        # before the firewall ever sees the order.
        if role is not None:
            try:
                from security.authorization import Permission, normalize_role, role_can
            except ImportError:  # fail closed when the RBAC module is missing
                entry = {
                    "ts": ts.isoformat(),
                    "order_id": str(order.order_id),
                    "idempotency_key": order.idempotency_key,
                    "verdict": "block",
                    "reasons": ["unauthorized_role:rbac_unavailable"],
                    "risk_decision_id": "",
                    "broker_ack": None,
                    "actor": _scrub(actor),
                }
                self.audit_log.append(entry)
                return GatewayDecision(False, order, ("unauthorized_role:rbac_unavailable",),
                                       "", entry)
            resolved = normalize_role(role)
            if resolved is None or not role_can(resolved, Permission.SUBMIT_ORDER):
                _role = _scrub(str(role))
                reason = f"unauthorized_role:{_role}"
                entry = {
                    "ts": ts.isoformat(),
                    "order_id": str(order.order_id),
                    "idempotency_key": order.idempotency_key,
                    "verdict": "block",
                    "reasons": [reason],
                    "risk_decision_id": "",
                    "broker_ack": None,
                    "actor": _scrub(actor),
                    "role": _role,
                }
                self.audit_log.append(entry)
                return GatewayDecision(False, order, (reason,), "", entry)
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
            portfolio_gross=portfolio_gross,
            portfolio_equity=portfolio_equity,
        )
        entry: dict[str, Any] = {
            "ts": ts.isoformat(),
            "order_id": str(order.order_id),
            "idempotency_key": order.idempotency_key,
            "verdict": decision.verdict.value,
            "reasons": list(decision.reasons),
            "risk_decision_id": decision.risk_decision_id,
            "legacy_bypass": _legacy,
            "submitted": False,
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
                                       decision.risk_decision_id, entry,
                                       submitted=False)
            # P0-3: the ack decides the landing state. Explicit rejection ->
            # REJECTED (refused, never approved). Any non-rejecting ack ->
            # ACKNOWLEDGED. Returning a bare SUBMITTED order as "approved"
            # is forbidden: approval without ack state is a state lie.
            if _ack_rejected(ack):
                rejected = submitted.transition(OrderStatus.REJECTED, timestamp=ts)
                entry["broker_ack"] = ack
                self.audit_log.append(entry)
                return GatewayDecision(False, rejected, ("broker_rejected",),
                                       decision.risk_decision_id, entry,
                                       submitted=False)
            acked = submitted.transition(OrderStatus.ACKNOWLEDGED, timestamp=ts)
            entry["broker_ack"] = ack
            entry["submitted"] = True
            self.audit_log.append(entry)
            return GatewayDecision(True, acked, (), decision.risk_decision_id,
                                   entry, submitted=True)
        entry["broker_ack"] = ack
        self.audit_log.append(entry)
        return GatewayDecision(True, o2, (), decision.risk_decision_id, entry,
                               submitted=False)


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
