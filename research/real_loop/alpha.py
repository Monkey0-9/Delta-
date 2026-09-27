"""W95 alpha research engine: multi-factor signals, blending, IC/decay/turnover."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MODEL_VERSION = "alpha-v2"

# factor groupings over feature columns
GROUPS = {
    "momentum": ["mom_5d", "mom_12d", "mom_20d", "trend_12d", "trend_20d", "ret_5d"],
    "mean_reversion": ["mr_z_10d", "mr_z_20d", "rsi_14d"],
    "volatility": ["vol_10d", "vol_20d", "range_10d"],
    "liquidity": ["turnover_20d"],
    "trend": ["mom_60d", "trend_60d", "ret_1d"],
}


@dataclass(frozen=True, slots=True)
class AlphaResult:
    symbol: str
    expected_return: float  # per-horizon decimal
    confidence: float
    uncertainty: float
    ic: float
    model_version: str
    components: dict
    evidence_id: str


def _ic(scores: pd.Series, fwds: pd.Series) -> float:
    s = pd.concat([scores, fwds], axis=1).dropna()
    if len(s) < 10:
        return 0.0
    c = s.iloc[:, 0].corr(s.iloc[:, 1], method="spearman")
    return float(c) if c == c else 0.0


def score_symbol(feat: pd.DataFrame, fwd_days: int = 5) -> AlphaResult | None:
    """Walk-forward-free single-name score: IC-weighted factor blend on trailing data."""
    f = feat.dropna()
    if len(f) < 80:
        return None
    closes = None
    # forward returns need raw closes: reconstruct not available here, use ret columns
    # use ret_1d shifted back as proxy for realized fwd
    realized = f["ret_1d"].shift(-fwd_days)  # what WAS predictable fwd_days ago... PIT-safe for IC only
    comps: dict[str, float] = {}
    ics: dict[str, float] = {}
    for g, cols in GROUPS.items():
        avail = [c for c in cols if c in f.columns]
        if not avail:
            continue
        gscore = f[avail].mean(axis=1)
        ic = _ic(gscore.iloc[:-fwd_days], realized.iloc[:-fwd_days])
        comps[g] = float(gscore.iloc[-1])
        ics[g] = ic
    if not comps:
        return None
    tot = sum(abs(v) for v in ics.values()) or 1.0
    blended = sum(comps[g] * abs(ics.get(g, 0.0)) / tot for g in comps)
    # scale to expected return: cross-sectional z * vol proxy * horizon
    vol = float(f["vol_20d"].iloc[-1]) if "vol_20d" in f.columns else 0.02
    vol = min(max(abs(vol), 0.002), 0.08)
    er = float(np.clip(blended * vol * np.sqrt(fwd_days) * 2.0, -0.08, 0.08))
    mean_ic = float(np.mean(list(ics.values()))) if ics else 0.0
    conf = float(min(0.9, max(0.3, 0.5 + abs(mean_ic) * 4 + min(abs(blended) * 0.4, 0.25))))
    unc = float(round(1 - conf + 0.15, 4))
    return AlphaResult("", er, round(conf, 4), unc, round(mean_ic, 4), MODEL_VERSION,
                       {k: round(float(v), 4) for k, v in comps.items()}, "")


def blend_cross_section(results: list[AlphaResult]) -> list[AlphaResult]:
    """Cross-sectional neutralization: z-score ERs so market-neutral tilt."""
    if not results:
        return results
    ers = np.array([r.expected_return for r in results])
    mu, sd = ers.mean(), ers.std() or 1.0
    out = []
    for r in results:
        z = (r.expected_return - mu) / sd
        er = float(np.clip(z * 0.015, -0.05, 0.05))
        out.append(AlphaResult(r.symbol, er, r.confidence, r.uncertainty, r.ic,
                               r.model_version, r.components, r.evidence_id))
    return out
