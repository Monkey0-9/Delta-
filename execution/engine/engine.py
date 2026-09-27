from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from core.domain.order import OrderStatus
from execution.orders.order_state import ManagedOrder
from risk.firewall.firewall import RiskFirewall, RiskVerdict
from risk.pre_trade.validation import TradeIntent


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    order_id: UUID
    status: OrderStatus
    verdict: str
    reasons: tuple[str, ...] = ()


class OrderManagementSystem:
    """OMS: VALIDATED -> RISK_APPROVED -> SUBMITTED -> ACKNOWLEDGED."""

    def __init__(self, risk: RiskFirewall | None = None) -> None:
        self._risk = risk or RiskFirewall()
        self._orders: dict[UUID, ManagedOrder] = {}

    def submit(
        self,
        intent: TradeIntent,
        *,
        ref_price: Decimal | None = None,
        current_position: Decimal = Decimal("0"),
        current_position_notional: Decimal | None = None,
        data_age_s: float = 0.0,
        portfolio_var: Decimal | None = None,
    ) -> ExecutionResult:
        order = ManagedOrder(
            order_id=intent.order_id,
            instrument_id=intent.instrument_id,
            side=intent.side,
            quantity=intent.quantity,
            idempotency_key=intent.idempotency_key,
        )
        order.advance(OrderStatus.VALIDATED)
        decision = self._risk.check(
            intent, ref_price=ref_price,
            current_position=current_position,
            current_position_notional=current_position_notional,
            data_age_s=data_age_s,
            portfolio_var=portfolio_var,
        )
        if decision.verdict == RiskVerdict.BLOCK:
            order.status = OrderStatus.REJECTED
            self._orders[order.order_id] = order
            return ExecutionResult(order.order_id, order.status, "block", decision.reasons)
        order.advance(OrderStatus.RISK_APPROVED)
        order.advance(OrderStatus.SUBMITTED)
        order.advance(OrderStatus.ACKNOWLEDGED)
        self._orders[order.order_id] = order
        return ExecutionResult(order.order_id, order.status, "approve", ())

    def get(self, order_id: UUID) -> ManagedOrder:
        return self._orders[order_id]
