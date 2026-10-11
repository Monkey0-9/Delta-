from __future__ import annotations

import os
import warnings
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
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


def _atomic_write_text(path: Path, text: str) -> None:
    """Atomic text write via a unique same-dir tmp file + os.replace.

    The tmp name carries pid + uuid4 hex so two writers (threads or
    processes) can never share it. Raises on failure: callers decide
    whether persistence loss warns or blocks. Kept local (not shared
    with ``delta_os.safety.atomic_write_json``) so the risk package
    stays dependency-free and handles plain text, not JSON.
    """
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


class _SeenKeySet(set):  # type: ignore[type-arg]
    """A set of idempotency keys that persists mutations best-effort.

    Scope: SINGLE-PROCESS, BEST-EFFORT. Concurrent writers in other
    processes may interleave appends (append-only, so keys are never
    lost, only reordered); a concurrent ``discard`` rewrite can drop a
    key appended mid-rewrite. For crash recovery this is fine: the
    in-memory set is authoritative within a process, the file only
    seeds restarts. Cross-process exactly-once needs an external store.

    ``add`` appends the key to the backing file; ``discard`` rewrites the
    file atomically. All I/O is swallowed (warn once) so persistence can
    never break the fail-closed check path. ``None`` path = memory only.
    """

    def __init__(self, *args: Any, _persist_path: Path | None = None) -> None:
        super().__init__(*args)
        self._persist_path = _persist_path

    def add(self, key: str) -> None:  # type: ignore[override]
        super().add(key)
        if self._persist_path is not None:
            try:
                self._persist_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._persist_path, "a", encoding="utf-8") as fh:
                    fh.write(f"{key}\n")
            except Exception as exc:
                warnings.warn(
                    f"seen-keys persist skipped ({exc}).",
                    UserWarning, stacklevel=2,
                )

    def discard(self, key: str) -> None:  # type: ignore[override]
        super().discard(key)
        if self._persist_path is not None:
            try:
                _atomic_write_text(
                    self._persist_path, "".join(f"{k}\n" for k in sorted(self)))
            except Exception as exc:
                warnings.warn(
                    f"seen-keys persist skipped ({exc}).",
                    UserWarning, stacklevel=2,
                )


def _load_seen_keys(path: Path) -> set[str]:
    """Best-effort load of a newline-delimited key file.

    Missing file -> empty (silent). Corrupt (undecodable/unreadable) ->
    warn + fresh empty set. Never raises.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    except Exception as exc:
        warnings.warn(
            f"seen-keys file unreadable ({exc}); starting fresh.",
            UserWarning, stacklevel=3,
        )
        return set()
    try:
        return {line.strip() for line in text.splitlines() if line.strip()}
    except Exception as exc:
        warnings.warn(
            f"seen-keys file corrupt ({exc}); starting fresh.",
            UserWarning, stacklevel=3,
        )
        return set()


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
        *,
        seen_keys_path: str | Path | None = None,
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
        persist_path = Path(seen_keys_path) if seen_keys_path is not None else None
        initial = _load_seen_keys(persist_path) if persist_path is not None else set()
        self._seen_keys: set[str] = _SeenKeySet(
            initial, _persist_path=persist_path)
        # Sliding-window event clocks (B7b): per-second message rate and
        # per-symbol duplicative-order cap. Keyed by `now` (injectable).
        self._msg_times: list[datetime] = []
        self._dup_events: dict[tuple[str, str, str], list[datetime]] = {}

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
        symbol: str | None = None,
        portfolio_gross: Decimal | None = None,
        portfolio_equity: Decimal | None = None,
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
        # 3a. Message rate (sliding 1s window, fail-closed refuse)
        # ---------------------------------------------------------------
        # Clock-skew guard: only events with 0 <= dt < window count. A
        # back-dated `now` (or a future-stamped event) yields dt < 0 and
        # is evicted, never counted — stale clocks fail open on rate,
        # never false-breach.
        self._msg_times = [
            t for t in self._msg_times
            if 0 <= (now - t).total_seconds() < 1.0
        ]
        if len(self._msg_times) >= self._limits.max_messages_per_s:
            reasons.append("message_rate_breach")
        self._msg_times.append(now)

        # ---------------------------------------------------------------
        # 3b. Duplicative orders per symbol+side+qty (sliding window)
        # ---------------------------------------------------------------
        # Canonical identity is ``intent.instrument_id``. The ``symbol``
        # argument is a documented grouping override (e.g. display symbol
        # shared across instrument ids): when given, buckets key on it;
        # when None, each instrument id buckets alone. Passing a symbol
        # vs omitting it therefore NEVER shares a bucket (None-vs-explicit
        # split is by design, not accident).
        dup_key = (
            symbol if symbol is not None else str(intent.instrument_id),
            str(intent.side),
            str(intent.quantity),
        )
        window = float(self._limits.duplicative_window_s)
        recent = [
            t for t in self._dup_events.get(dup_key, [])
            if 0 <= (now - t).total_seconds() < window
        ]
        if len(recent) >= self._limits.max_duplicative_orders:
            reasons.append("duplicative_order_breach")
        recent.append(now)
        self._dup_events[dup_key] = recent
        # Bound memory: drop buckets that aged fully empty, and compact
        # the whole map once it grows past a safety cap.
        if len(self._dup_events) > 4096:
            self._dup_events = {
                k: v for k, v in self._dup_events.items() if v
            }

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
        # 5b. Portfolio ceilings: gross exposure + leverage (H-item, P2).
        # Enforced when the caller supplies portfolio context; without it
        # the decision CANNOT evaluate these ceilings (noted in reasons
        # namespace below via evaluated_ceilings in the audit entry —
        # callers must prefer passing context; see gateway.submit).
        # ---------------------------------------------------------------
        if portfolio_gross is not None or portfolio_equity is not None:
            if ref_price is None or ref_price <= 0:
                reasons.append("portfolio_ceiling_unevaluable_no_ref_price")
            elif portfolio_gross is None or portfolio_equity is None:
                reasons.append("portfolio_ceiling_unevaluable_missing_input")
            elif portfolio_equity <= 0:
                reasons.append("portfolio_ceiling_unevaluable_no_equity")
            else:
                new_gross = portfolio_gross + intent.quantity * ref_price
                if new_gross > self._limits.max_gross_exposure:
                    reasons.append("gross_exposure_breach")
                if new_gross / portfolio_equity > self._limits.max_leverage:
                    reasons.append("leverage_breach")

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
