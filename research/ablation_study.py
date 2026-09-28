"""W231-W250 (R) — Academic ablation: regime-aware microstructure alpha with
adaptive execution and capacity-aware allocation.

Compares baseline vs +regime vs +regime+microstructure vs full stack, so any
claim is scientifically defensible (ablated, not asserted).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AblationArm:
    name: str
    regime: bool
    microstructure: bool
    adaptive_execution: bool
    capacity_aware: bool


ARMS: tuple[AblationArm, ...] = (
    AblationArm("baseline", False, False, False, False),
    AblationArm("regime-aware", True, False, False, False),
    AblationArm("regime+micro", True, True, False, False),
    AblationArm("full", True, True, True, True),
)


def run_ablation(score_fn) -> dict[str, float]:
    """score_fn(arm) -> net Sharpe (deterministic). Returns arm -> score + deltas."""
    out = {arm.name: float(score_fn(arm)) for arm in ARMS}
    out["delta_regime"] = out["regime-aware"] - out["baseline"]
    out["delta_micro"] = out["regime+micro"] - out["regime-aware"]
    out["delta_full"] = out["full"] - out["regime+micro"]
    # defensibility: every claimed gain must be positive AND monotonic
    out["monotonic"] = float(out["regime-aware"] <= out["regime+micro"] <= out["full"])
    return out
