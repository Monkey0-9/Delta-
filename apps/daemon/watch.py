"""Daemon portfolio watch (P2).

Pure, testable verdict logic for continuous monitoring:

  MONITOR -> DETECT -> PROPOSE -> RISK -> AUTH -> EXECUTE-or-ALERT -> RECONCILE

States: OK / APPROACHING (80% of cap) / BREACH / HALTED (stale/unauthorized/kill).
EXECUTE is True ONLY when mode==AUTONOMOUS + BREACH + fresh + auth + no kill.
Everything else alerts. Threading lives in WatchLoop.tick(); logic is pure.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WatchInput:
    top_weight: float = 0.0
    sector_weight: float = 0.0
    max_position_pct: float = 0.10
    sector_cap: float = 0.40
    data_fresh: bool = True
    authorization_valid: bool = False
    kill_switch_active: bool = False
    execution_mode: str = "SUPERVISED"


@dataclass(frozen=True, slots=True)
class WatchVerdict:
    state: str  # OK | APPROACHING | BREACH | HALTED
    execute: bool
    actions: tuple[str, ...]


def evaluate_watch(inp: WatchInput) -> WatchVerdict:
    if inp.kill_switch_active:
        return WatchVerdict("HALTED", False, ("Kill switch active: halt all autonomous action.",))
    if not inp.data_fresh:
        return WatchVerdict("HALTED", False, ("Stale market data: monitoring only, no action.",))
    breached = inp.top_weight > inp.max_position_pct or inp.sector_weight > inp.sector_cap
    approaching = (
        inp.top_weight > 0.8 * inp.max_position_pct
        or inp.sector_weight > 0.8 * inp.sector_cap
    )
    if breached:
        if inp.execution_mode == "AUTONOMOUS" and inp.authorization_valid:
            return WatchVerdict(
                "BREACH",
                True,
                (
                    "Risk limit breach: reduce exposure per approved policy.",
                    f"Risk approval: PASS. Execution policy: {inp.execution_mode}. Broker: check health before submit.",
                ),
            )
        return WatchVerdict(
            "BREACH",
            False,
            (
                "Risk limit breach detected. No trade executed.",
                "Reason: mandate does not authorize automatic reduction.",
                "Recommendation: review concentration; consider trim/diversify/hedge.",
            ),
        )
    if approaching:
        return WatchVerdict(
            "APPROACHING",
            False,
            (
                f"Risk threshold approaching (position {inp.top_weight:.0%} vs cap "
                f"{inp.max_position_pct:.0%}; sector {inp.sector_weight:.0%} vs cap "
                f"{inp.sector_cap:.0%}). No action yet. Monitoring.",
            ),
        )
    return WatchVerdict("OK", False, ("Within mandate. Monitoring.",))
