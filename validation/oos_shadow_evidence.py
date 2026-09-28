"""W135 — Long-duration OOS + shadow evidence framework.

Deterministic walk-forward OOS ledger + shadow-vs-live divergence tracker.
No network; pure python; seed-fixed data generation for tests.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field


@dataclass
class OOSWindow:
    start: int
    end: int
    sharpe: float
    net_pnl: float


@dataclass
class OOSLedger:
    windows: list[OOSWindow] = field(default_factory=list)

    def add(self, w: OOSWindow) -> None:
        self.windows.append(w)

    def summary(self) -> dict:
        if not self.windows:
            return {"n": 0, "hit_rate": 0.0, "mean_sharpe": 0.0, "total_pnl": 0.0}
        pos = sum(1 for w in self.windows if w.net_pnl > 0)
        return {
            "n": len(self.windows),
            "hit_rate": pos / len(self.windows),
            "mean_sharpe": sum(w.sharpe for w in self.windows) / len(self.windows),
            "total_pnl": sum(w.net_pnl for w in self.windows),
        }

    def consecutive_losses(self) -> int:
        worst = cur = 0
        for w in self.windows:
            cur = cur + 1 if w.net_pnl <= 0 else 0
            worst = max(worst, cur)
        return worst


@dataclass
class ShadowTracker:
    """Compare shadow fills vs live-reference fills; divergence must stay bounded."""

    tolerance_bps: float = 5.0
    diffs_bps: list[float] = field(default_factory=list)

    def record(self, shadow_px: float, ref_px: float) -> None:
        if ref_px <= 0:
            return
        self.diffs_bps.append(abs(shadow_px - ref_px) / ref_px * 1e4)

    def report(self) -> dict:
        if not self.diffs_bps:
            return {"n": 0, "p50": 0.0, "p99": 0.0, "breaches": 0, "passed": True}
        s = sorted(self.diffs_bps)
        p50 = s[len(s) // 2]
        p99 = s[min(len(s) - 1, int(len(s) * 0.99))]
        breaches = sum(1 for d in s if d > self.tolerance_bps)
        return {"n": len(s), "p50": p50, "p99": p99, "breaches": breaches,
                "passed": breaches == 0}
