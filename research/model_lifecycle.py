"""W211-W230 (K) — Formal model lifecycle state machine + drift monitor.

RESEARCH -> VALIDATED -> PAPER -> SHADOW -> PRODUCTION -> DEGRADED -> RETIRED.
No manual jumps. Drift: feature/prediction/IC/PnL/execution/regime/distribution
monitors drive NORMAL -> WARNING -> DEGRADED -> PAUSED -> RETRAIN.
"""
from __future__ import annotations

from dataclasses import dataclass, field

STATES: tuple[str, ...] = ("RESEARCH", "VALIDATED", "PAPER", "SHADOW",
                           "PRODUCTION", "DEGRADED", "RETIRED")

ALLOWED: dict[str, tuple[str, ...]] = {
    "RESEARCH": ("VALIDATED", "RETIRED"),
    "VALIDATED": ("PAPER", "RETIRED"),
    "PAPER": ("SHADOW", "RETIRED"),
    "SHADOW": ("PRODUCTION", "RETIRED"),
    "PRODUCTION": ("DEGRADED", "RETIRED"),
    "DEGRADED": ("SHADOW", "RETIRED"),  # recover via re-shadow, never direct to PROD
    "RETIRED": (),
}

DRIFT_LEVELS: tuple[str, ...] = ("NORMAL", "WARNING", "DEGRADED", "PAUSED", "RETRAIN")

DRIFT_SIGNALS: tuple[str, ...] = ("feature", "prediction", "ic", "pnl",
                                  "execution", "regime", "distribution")


@dataclass
class ModelLifecycle:
    model_id: str
    state: str = "RESEARCH"
    trail: list[str] = field(default_factory=list)

    def transition(self, to: str, *, gate_passed: bool) -> tuple[bool, str]:
        if to not in ALLOWED.get(self.state, ()):
            return False, f"illegal jump {self.state}->{to}"
        if to != "RETIRED" and not gate_passed:
            return False, "gate failed: fail-closed"
        self.trail.append(f"{self.state}->{to}")
        self.state = to
        return True, f"now {to}"


@dataclass
class DriftMonitor:
    """Per-signal z-score vs baseline; worst signal drives the level."""

    baselines: dict[str, tuple[float, float]] = field(default_factory=dict)  # signal -> (mean, std)
    state: str = "NORMAL"

    def set_baseline(self, signal: str, mean: float, std: float) -> None:
        if signal not in DRIFT_SIGNALS:
            raise ValueError(f"bad signal {signal}")
        self.baselines[signal] = (mean, max(std, 1e-12))

    def observe(self, readings: dict[str, float]) -> str:
        worst = 0.0
        for sig, val in readings.items():
            if sig not in self.baselines:
                continue
            mean, std = self.baselines[sig]
            worst = max(worst, abs(val - mean) / std)
        if worst >= 5:
            self.state = "RETRAIN"
        elif worst >= 4:
            self.state = "PAUSED"
        elif worst >= 3:
            self.state = "DEGRADED"
        elif worst >= 2:
            self.state = "WARNING"
        else:
            self.state = "NORMAL"
        return self.state
