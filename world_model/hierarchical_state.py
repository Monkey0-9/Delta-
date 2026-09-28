"""W191-W210 (E) — Hierarchical market state (world model extension).

GLOBAL -> macro / volatility / liquidity / correlation / sector / asset-specific,
with P(state_t+1 | state_t, observations). Complements (not replaces)
world_model/probabilistic_world.py flat regime models.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

LEVELS: tuple[str, ...] = ("macro", "volatility", "liquidity", "correlation", "sector", "asset")


@dataclass
class LevelBelief:
    level: str
    states: tuple[str, ...]
    probs: list[float]  # sum to 1
    trans: list[list[float]]  # rows sum to 1

    def predict(self, horizon: int = 1) -> list[float]:
        b = list(self.probs)
        for _ in range(horizon):
            b = [sum(b[p] * self.trans[p][s] for p in range(len(b))) for s in range(len(b))]
        return b

    def update(self, likelihood: list[float]) -> None:
        pred = self.predict(1)
        un = [p * l for p, l in zip(pred, likelihood)]
        tot = sum(un) or 1.0
        self.probs = [u / tot for u in un]


@dataclass
class HierarchicalState:
    levels: dict[str, LevelBelief] = field(default_factory=dict)

    @staticmethod
    def uniform() -> "HierarchicalState":
        specs = {
            "macro": ("EXPANSION", "SLOWDOWN", "RECESSION", "CRISIS"),
            "volatility": ("LOW", "NORMAL", "HIGH", "EXTREME"),
            "liquidity": ("DEEP", "NORMAL", "THIN", "STRESSED"),
            "correlation": ("LOW", "NORMAL", "HIGH"),
            "sector": ("ROTATION", "TREND", "DISPERSED"),
            "asset": ("CALM", "ACTIVE", "DISLOCATED"),
        }
        hs = HierarchicalState()
        for lvl, states in specs.items():
            k = len(states)
            hs.levels[lvl] = LevelBelief(lvl, states, [1 / k] * k,
                                         [[(0.85 if i == j else 0.15 / (k - 1))
                                           for j in range(k)] for i in range(k)])
        return hs

    def joint_stress_prob(self) -> float:
        """P(bad joint state): macro in {RECESSION,CRISIS} AND vol HIGH/EXTREME AND liq THIN/STRESSED."""
        m = self.levels["macro"].probs
        v = self.levels["volatility"].probs
        lq = self.levels["liquidity"].probs
        return (m[2] + m[3]) * (v[2] + v[3]) * (lq[2] + lq[3])

    def entropy(self) -> float:
        tot = 0.0
        for lv in self.levels.values():
            tot += -sum(p * math.log(max(p, 1e-12)) for p in lv.probs)
        return tot
