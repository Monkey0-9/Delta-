from __future__ import annotations

import hashlib
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

    B7a: the verdict is bound to the submitted order. When the evidence
    carries an ``order_hash`` it must equal ``evidence_order_hash(...)``
    computed over the FULL submitted economics (id + symbol + quantity +
    side + price + notional) — mutating any field refuses. An explicit
    ``order_id`` that disagrees with the submitted order refuses even if a
    hash happens to match. Evidence carrying only a matching ``order_id``
    (no hash) is accepted as an explicit fast path for verdicts minted
    before economics were known; whenever a hash is present it is verified
    (AND semantics). A bare ``risk_verdict="approve"`` string with no
    binding is refused — otherwise one order's approval could be replayed
    for a different order.
    """

    risk_verdict: str  # "approve" expected
    risk_decision_id: str = ""
    kill_any_active: bool = False
    order_id: str = ""
    order_hash: str = ""


def _canonical_decimal(value: Decimal) -> str:
    """Canonical decimal string: Decimal("1") and Decimal("1.0") agree."""
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
        if d.is_nan() or d.is_infinite():
            return str(d)
        return format(d.normalize(), "f")
    except Exception:
        return str(value)


def evidence_order_hash(
    *,
    client_order_id: str,
    symbol: str,
    quantity: Decimal,
    side: OrderSide,
    price: Decimal | None = None,
    notional: Decimal | None = None,
) -> str:
    """Deterministic binding hash tying a risk verdict to one order.

    Full SHA-256 digest over id + symbol + canonical quantity + side, plus
    price and notional when known. Decimals are normalized so formatting
    variants (``1`` vs ``1.0``) hash identically. Mint and execution must
    use identical fields: a hash minted without price only verifies an
    execution that also omits price.
    """
    side_value = getattr(side, "value", side)
    parts = [
        str(client_order_id),
        str(symbol),
        _canonical_decimal(quantity),
        str(side_value),
    ]
    if price is not None:
        parts.append(_canonical_decimal(price))
    if notional is not None:
        parts.append(_canonical_decimal(notional))
    raw = ":".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
        price: Decimal | None = None,
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
        # B7a fail-closed order-path gates.
        # 0. Qty/notional sanity re-check: never trust caller arithmetic.
        if quantity is None or quantity <= 0:
            return LiveExecutionResult(
                allowed=False,
                broker_order_id=None,
                reasons=("invalid_quantity: quantity must be positive",),
            )
        if notional is None or notional <= 0:
            return LiveExecutionResult(
                allowed=False,
                broker_order_id=None,
                reasons=("invalid_notional: notional must be positive",),
            )
        # P0 fail-closed cross-check: bare bools are untrusted claims.
        # When evidence objects are supplied they are authoritative; any
        # mismatch blocks. B7a: evidence is required on EVERY mode, including
        # the legacy PAPER/RECOMMENDATION path — bare-bool PAPER submission
        # is a venue bypass and is refused outright.
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
            # B7a: verdict must be bound to the submitted order.
            # An explicit order_id that disagrees with the submitted order
            # means inconsistent/tampered evidence: refuse even if a hash
            # happens to match.
            if risk_evidence.order_id and risk_evidence.order_id != client_order_id:
                return LiveExecutionResult(
                    allowed=False,
                    broker_order_id=None,
                    reasons=("risk_evidence_order_mismatch: verdict not bound to order",),
                )
            if risk_evidence.order_hash:
                # Hash binding (AND): verified against the full submitted
                # economics (id + symbol + quantity + side + price +
                # notional). Any mutation — qty, symbol, side, price,
                # notional — refuses.
                expected_hash = evidence_order_hash(
                    client_order_id=client_order_id,
                    symbol=symbol,
                    quantity=quantity,
                    side=side,
                    price=price,
                    notional=notional,
                )
                if risk_evidence.order_hash != expected_hash:
                    return LiveExecutionResult(
                        allowed=False,
                        broker_order_id=None,
                        reasons=("risk_evidence_order_mismatch: verdict not bound to order",),
                    )
            elif not (risk_evidence.order_id and risk_evidence.order_id == client_order_id):
                # Explicit-order_id fast path only: evidence minted before
                # economics were known carries no hash. No binding at all
                # (bare risk_verdict string) is refused.
                return LiveExecutionResult(
                    allowed=False,
                    broker_order_id=None,
                    reasons=("risk_evidence_order_mismatch: verdict not bound to order",),
                )
        else:
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