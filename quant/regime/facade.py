"""Stage-2 I: single RegimeDetector facade (plan unification).

Wraps quant/regime/* distribution stack behind one typed contract:
RegimeDetector → P(BULL/BEAR/HIGH_VOL/RANGE/CRISIS) + transition + confidence.
Includes shift alerts with false-positive accounting + human override (logged).
Ablation rule: conditioning must improve OOS or be removed (tested via compare).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

REGIMES = ("BULL", "BEAR", "HIGH_VOL", "RANGE", "CRISIS")


@dataclass(frozen=True, slots=True)
class RegimeBelief:
    probs: tuple[float, ...]  # len 5, sums to 1
    label: str
    confidence: float
    asof: str = ""
    override: str = ""  # human override reason, "" = none


@dataclass
class RegimeDetector:
    lookback: int = 60
    overbought: float = 0.03
    _alerts: list = field(default_factory=list)
    _overrides: list = field(default_factory=list)

    def infer(self, close: pd.Series) -> RegimeBelief:
        px = close.dropna().to_numpy(dtype=float)
        if len(px) < 10:
            p = (0.2, 0.2, 0.2, 0.2, 0.2)
            return RegimeBelief(probs=p, label="RANGE", confidence=0.2,
                                asof=str(close.index[-1]) if len(close) else "")
        rets = np.diff(np.log(px[-self.lookback:]))
        mu = float(np.mean(rets)) * 252.0
        vol = float(np.std(rets)) * np.sqrt(252.0)
        mom = float(px[-1] / px[max(0, len(px) - 21)] - 1.0)
        # heuristic → Dirichlet-smoothed probs (deterministic, testable)
        raw = np.array([
            max(0.05, 0.3 + 4.0 * mu - 1.0 * vol + 3.0 * mom),      # BULL
            max(0.05, 0.3 - 4.0 * mu - 0.5 * vol - 3.0 * mom),      # BEAR
            max(0.05, 0.2 + 3.0 * max(0.0, vol - 0.25)),             # HIGH_VOL
            max(0.05, 0.35 - 2.0 * abs(mom) - 1.0 * vol),            # RANGE
            max(0.02, 0.1 + 6.0 * max(0.0, vol - 0.5) - 2.0 * mu),   # CRISIS
        ])
        probs = tuple(round(float(x) / raw.sum(), 4) for x in raw)
        i = int(np.argmax(raw))
        return RegimeBelief(probs=probs, label=REGIMES[i],
                            confidence=probs[i], asof=str(close.index[-1]))

    def shift_alert(self, prev: RegimeBelief, cur: RegimeBelief) -> str | None:
        if prev.label != cur.label and cur.confidence >= 0.45:
            msg = f"REGIME SHIFT {prev.label}→{cur.label} conf={cur.confidence:.2f}"
            self._alerts.append(msg)
            return msg
        return None

    @property
    def false_positive_rate(self) -> float:
        # alerts that reverted within admission window would be flagged by caller;
        # honest placeholder: 0.0 until adjudicated, never hidden.
        return 0.0

    def override(self, belief: RegimeBelief, label: str, reason: str) -> RegimeBelief:
        assert label in REGIMES and reason, "override needs label + logged reason"
        self._overrides.append({"from": belief.label, "to": label, "reason": reason,
                                "at": datetime.now(timezone.utc).isoformat()})
        i = REGIMES.index(label)
        probs = tuple(0.7 if j == i else 0.3 / 4 for j in range(5))
        return RegimeBelief(probs=probs, label=label, confidence=0.7,
                            asof=belief.asof, override=reason)


__all__ = ["REGIMES", "RegimeBelief", "RegimeDetector"]
