from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from broker.contracts import (
    BrokerAdapter,
    BrokerOrder,
    OrderSide,
    OrderType,
)
from broker.health import check
from governance.execution_policy import (
    ExecutionContext,
    authorize,
)
from trader.mandate import (
    AutonomyMode,
    TradingMandate,
)


@dataclass(frozen=True)
class LiveExecutionResult:
    allowed: bool
    broker_order_id: str | None
    reasons: tuple[str, ...]


class LiveExecutionEngine:

    def __init__(
        self,
        broker: BrokerAdapter,
        mandate: TradingMandate,
    ):
        self.broker = broker
        self.mandate = mandate

    def execute(
        self,
        *,
        mode: AutonomyMode,
        client_order_id: str,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        order_type: OrderType,
        notional: Decimal,
        market_open: bool,
        data_fresh: bool,
        risk_approved: bool,
        authorization_valid: bool,
        kill_switch_active: bool,
        model_eligible: bool,
        uncertainty_acceptable: bool,
        duplicate_order: bool,
    ) -> LiveExecutionResult:

        broker_health = check(
            self.broker
        )

        context = ExecutionContext(
            market_open=market_open,
            data_fresh=data_fresh,
            broker_healthy=(
                broker_health.healthy
            ),
            risk_approved=risk_approved,
            authorization_valid=(
                authorization_valid
            ),
            kill_switch_active=(
                kill_switch_active
            ),
            model_eligible=model_eligible,
            uncertainty_acceptable=(
                uncertainty_acceptable
            ),
            duplicate_order=duplicate_order,
        )

        policy = authorize(
            self.mandate,
            mode,
            order_notional=notional,
            context=context,
        )

        if not policy.allowed:
            return LiveExecutionResult(
                allowed=False,
                broker_order_id=None,
                reasons=policy.reasons,
            )

        order = BrokerOrder(
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
        )

        result = self.broker.submit(
            order
        )

        return LiveExecutionResult(
            allowed=True,
            broker_order_id=(
                result.broker_order_id
            ),
            reasons=(),
        )