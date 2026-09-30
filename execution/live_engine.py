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

try:
    from risk.kill_switch.kill_switch import KillSwitch, KillSwitchBoard
except ImportError:  # installed-package layout
    from delta.risk.kill_switch.kill_switch import KillSwitch, KillSwitchBoard  # type: ignore


@dataclass(frozen=True)
class VerifiedRiskEvidence:
    """Verified pre-trade evidence that must back the bool flags.

    P0 fix 2026-09-30: the previous ``execute()`` accepted bare bools
    (``risk_approved=True``) from any caller, so a compromised AI path could
    spoof approval. Evidence-backed execution requires the actual
    ``RiskDecision`` and the live ``KillSwitchBoard``; mismatches fail closed.
    """

    risk_verdict: str  # "approve" expected
    risk_decision_id: str = ""
    kill_any_active: bool = False


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
        risk_evidence: VerifiedRiskEvidence | None = None,
        kill_board: KillSwitch | KillSwitchBoard | None = None,
    ) -> LiveExecutionResult:
        # P0 fail-closed cross-check: bare bools are untrusted claims.
        # When evidence objects are supplied they are authoritative; any
        # mismatch blocks. For live modes without evidence, block outright
        # (legacy bool path remains only for PAPER/RECOMMENDATION tests).
        evidence_reasons: list[str] = []
        effective_kill_active = kill_switch_active
        if kill_board is not None:
            try:
                kill_board.check()
                board_active = False
            except Exception:
                board_active = True
            if board_active:
                effective_kill_active = True
            if board_active != kill_switch_active:
                return LiveExecutionResult(
                    allowed=False,
                    broker_order_id=None,
                    reasons=("kill_evidence_mismatch",),
                )
        if risk_evidence is not None:
            approved_by_evidence = risk_evidence.risk_verdict == "approve"
            if approved_by_evidence != risk_approved:
                return LiveExecutionResult(
                    allowed=False,
                    broker_order_id=None,
                    reasons=("risk_evidence_mismatch",),
                )
            if risk_evidence.kill_any_active:
                effective_kill_active = True
        elif mode not in (AutonomyMode.PAPER, AutonomyMode.RECOMMENDATION):
            return LiveExecutionResult(
                allowed=False,
                broker_order_id=None,
                reasons=("risk_evidence_missing",),
            )

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
                effective_kill_active
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