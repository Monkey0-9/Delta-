from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trader.mandate import (
    AutonomyMode,
    TradingMandate,
)


@dataclass(frozen=True)
class ExecutionContext:
    market_open: bool
    data_fresh: bool
    broker_healthy: bool
    risk_approved: bool
    authorization_valid: bool
    kill_switch_active: bool
    model_eligible: bool
    uncertainty_acceptable: bool
    duplicate_order: bool


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reasons: tuple[str, ...]


def authorize(
    mandate: TradingMandate,
    mode: AutonomyMode,
    *,
    order_notional: Decimal,
    context: ExecutionContext,
) -> PolicyDecision:

    reasons: list[str] = []

    if mode not in mandate.allowed_modes:
        reasons.append(
            "execution mode not allowed"
        )

    if (
        order_notional
        > mandate.max_order_notional
    ):
        reasons.append(
            "order notional exceeds mandate"
        )

    if not context.market_open:
        reasons.append(
            "market closed"
        )

    if not context.data_fresh:
        reasons.append(
            "stale critical data"
        )

    if not context.broker_healthy:
        reasons.append(
            "broker unhealthy"
        )

    if not context.risk_approved:
        reasons.append(
            "risk firewall rejected"
        )

    if not context.authorization_valid:
        reasons.append(
            "authorization missing or expired"
        )

    if context.kill_switch_active:
        reasons.append(
            "kill switch active"
        )

    if not context.model_eligible:
        reasons.append(
            "model not eligible"
        )

    if not context.uncertainty_acceptable:
        reasons.append(
            "uncertainty threshold exceeded"
        )

    if context.duplicate_order:
        reasons.append(
            "duplicate order"
        )

    return PolicyDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
    )