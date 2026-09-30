from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

try:
    from risk.kill_switch.kill_switch import KillSwitch, KillSwitchBoard
except ImportError:  # installed-package layout
    from delta.risk.kill_switch.kill_switch import KillSwitch, KillSwitchBoard  # type: ignore
from risk.limits.limits import RiskLimits
from risk.pre_trade.validation import (
    RiskDecision,
    RiskVerdict,
    TradeIntent,
    validate_intent,
)

# Step 1.4 bridge: uncatchable halt + 10-criteria kernel gate. Imported lazily
# inside methods to keep this module import-cycle safe; re-exported here so
# callers have one canonical symbol.
try:
    from delta_omega.agent_ledger_gate import RiskHaltException as RiskHaltException
except ImportError:  # pragma: no cover - kernel always installed in-repo
    class RiskHaltException(RuntimeError):  # type: ignore[no-redef]
        """Uncatchable-by-policy halt (fallback if kernel unimportable)."""


def enforce_red_button(gate_state) -> None:
    """Call the kernel's 10-criteria red_button; raise RiskHaltException if tripped.

    Must be called before any trade packet is approved. Let the exception
    propagate: crossed NBBO, clock inversion, or reconciliation breaks are
    fail-closed halts, not advisory flags.
    """
    from delta_omega.agent_ledger_gate import red_button

    trips = red_button(gate_state)
    if trips:
        raise RiskHaltException(f"RED-BUTTON HALT: {trips}")


class RiskFirewall:
    """Deterministic pre-trade firewall. Fail-closed on any breach."""

    def __init__(
        self,
        limits: RiskLimits | None = None,
        kill_switch: KillSwitch | KillSwitchBoard | None = None,
    ) -> None:
        self._limits = limits or RiskLimits()
        # Triple-layer board preferred: ANY of global/strategy/broker blocks.
        # A lone KillSwitch is accepted for backward compat and wrapped.
        if kill_switch is None:
            kill_switch = KillSwitchBoard()
        elif isinstance(kill_switch, KillSwitch):
            kill_switch = KillSwitchBoard(
                glob=kill_switch, strategy=KillSwitch(), broker=KillSwitch()
            )
        self._kill = kill_switch
        self._seen_keys: set[str] = set()
        self._order_counts: list[datetime] = []

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    @property
    def kill_switch(self) -> KillSwitch:
        return self._kill

    def check(
        self,
        intent: TradeIntent,
        *,
        ref_price: Decimal | None = None,
        current_position: Decimal = Decimal("0"),
        current_position_notional: Decimal | None = None,
        data_age_s: float = 0.0,
        now: datetime | None = None,
        portfolio_var: Decimal | None = None,
    ) -> RiskDecision:
        reasons: list[str] = []
        now = now or datetime.now(timezone.utc)

        # ---------------------------------------------------------------
        # 1. Kill switch (triple-layer board)
        # ---------------------------------------------------------------
        # Independent of model confidence. RiskHaltException (kernel
        # red-button) is uncatchable-by-policy and must propagate, never
        # degrade to an advisory BLOCK verdict.
        try:
            self._kill.check()
        except RiskHaltException:
            raise
        except RuntimeError:
            return self._decide(
                intent,
                RiskVerdict.BLOCK,
                ("kill_switch_active",),
            )

        # ---------------------------------------------------------------
        # 2. Validate intent
        # ---------------------------------------------------------------
        errors = validate_intent(intent)
        reasons.extend(errors)

        # ---------------------------------------------------------------
        # 3. Idempotency
        # ---------------------------------------------------------------
        if intent.idempotency_key in self._seen_keys:
            reasons.append("duplicate_idempotency_key")

        # ---------------------------------------------------------------
        # 4. Order size / notional
        # ---------------------------------------------------------------
        if intent.quantity > self._limits.max_order_qty:
            reasons.append("max_order_qty_breach")

        if (
            ref_price is not None
            and intent.quantity * ref_price
            > self._limits.max_order_notional
        ):
            reasons.append("max_order_notional_breach")

        # ---------------------------------------------------------------
        # 5. Intraday position (QTY vs QTY) + position notional ($ vs $)
        # P0 fix: never compare shares against dollars.
        # ---------------------------------------------------------------
        signed = (
            intent.quantity
            if intent.side == "buy"
            else -intent.quantity
        )

        if (
            abs(current_position + signed)
            > self._limits.max_intraday_position
        ):
            reasons.append("intraday_position_breach")

        if ref_price is not None and ref_price > 0:
            if current_position_notional is None:
                # Backward-compatible estimate from qty position.
                current_notional = abs(current_position) * ref_price
            else:
                current_notional = abs(current_position_notional)
            new_notional = current_notional + intent.quantity * ref_price
            if new_notional > self._limits.max_position_notional:
                reasons.append("position_notional_breach")

        # ---------------------------------------------------------------
        # 6. Price tolerance
        # ---------------------------------------------------------------
        if (
            intent.limit_price is not None
            and ref_price is not None
            and ref_price > 0
        ):
            dev_bps = (
                abs(intent.limit_price - ref_price)
                / ref_price
                * Decimal("10000")
            )

            if dev_bps > self._limits.price_tolerance_bps:
                reasons.append("price_tolerance_breach")

        # ---------------------------------------------------------------
        # 7. Stale market data
        # ---------------------------------------------------------------
        if data_age_s > self._limits.stale_data_ttl_s:
            reasons.append("stale_market_data")

        # ---------------------------------------------------------------
        # 7a. W94: Reject synthetic/demo price sources
        # ---------------------------------------------------------------
        if hasattr(intent, 'price_source') and intent.price_source in ("demo_fallback", "synthetic", "hash_seeded"):
            reasons.append(f"invalid_price_source_{intent.price_source}")

        # ---------------------------------------------------------------
        # 7b. Portfolio VaR cap (wired to risk.post_trade.monitor estimators)
        # ---------------------------------------------------------------
        if (
            portfolio_var is not None
            and self._limits.max_var_notional is not None
            and portfolio_var > self._limits.max_var_notional
        ):
            reasons.append("var_limit_breach")

        # ---------------------------------------------------------------
        # 8. Final verdict
        # ---------------------------------------------------------------
        verdict = (
            RiskVerdict.BLOCK
            if reasons
            else RiskVerdict.APPROVE
        )

        # Only reserve the idempotency key after ALL checks pass.
        if verdict == RiskVerdict.APPROVE:
            self._seen_keys.add(intent.idempotency_key)

        return self._decide(
            intent,
            verdict,
            tuple(reasons),
        )

    def check_with_red_button(
        self,
        intent: TradeIntent,
        gate_state,
        **kwargs,
    ) -> RiskDecision:
        """Step 1.4 bridge: kernel red_button gate runs BEFORE any approval.

        Raises RiskHaltException (uncatchable-by-policy) when any of the 10
        criteria trip: clock inversion, crossed/zero-bid NBBO, PBO, drawdown,
        recon gap, DSR, collar, demo-path, liquidity horizon, factor drift.
        """
        enforce_red_button(gate_state)
        return self.check(intent, **kwargs)

    def _decide(
        self,
        intent: TradeIntent,
        verdict: RiskVerdict,
        reasons: tuple[str, ...],
    ) -> RiskDecision:
        return RiskDecision(
            risk_decision_id=f"rd-{uuid4().hex[:12]}",
            decision_id=str(intent.order_id),
            limits_version=self._limits.version,
            verdict=verdict,
            reasons=reasons,
        )
