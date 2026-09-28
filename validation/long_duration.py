"""W231-W250 (T) — Long-duration validation: PAPER -> SHADOW over months.

Tracks predicted vs actual price/fill/cost/risk and compares. Duration is
measured in recorded bars, honestly — no claim without the bars.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LongDurationTracker:
    stage: str = "PAPER"  # PAPER -> SHADOW
    pred_px: list[float] = field(default_factory=list)
    actual_px: list[float] = field(default_factory=list)
    pred_fill: list[float] = field(default_factory=list)
    actual_fill: list[float] = field(default_factory=list)
    pred_cost: list[float] = field(default_factory=list)
    actual_cost: list[float] = field(default_factory=list)
    pred_risk: list[float] = field(default_factory=list)
    actual_risk: list[float] = field(default_factory=list)

    def record(self, *, pp, ap, pf, af, pc, ac, pr, ar) -> None:
        self.pred_px.append(pp)
        self.actual_px.append(ap)
        self.pred_fill.append(pf)
        self.actual_fill.append(af)
        self.pred_cost.append(pc)
        self.actual_cost.append(ac)
        self.pred_risk.append(pr)
        self.actual_risk.append(ar)

    @staticmethod
    def _mae(a: list[float], b: list[float]) -> float:
        n = min(len(a), len(b))
        return sum(abs(x - y) for x, y in zip(a[:n], b[:n])) / n if n else 0.0

    def compare(self, *, required_bars: int = 10_000) -> dict:
        n = len(self.actual_px)
        return {
            "stage": self.stage,
            "bars": n,
            "sufficient_duration": n >= required_bars,
            "mae_price": self._mae(self.pred_px, self.actual_px),
            "mae_fill": self._mae(self.pred_fill, self.actual_fill),
            "mae_cost": self._mae(self.pred_cost, self.actual_cost),
            "mae_risk": self._mae(self.pred_risk, self.actual_risk),
        }

    def promote_to_shadow(self, paper_ok: bool) -> bool:
        if self.stage == "PAPER" and paper_ok:
            self.stage = "SHADOW"
            return True
        return False
