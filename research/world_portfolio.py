"""G24/G25/G26/G27 — World regimes + ML registry + portfolio hard caps + risk limits (thin slice)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RegimeState:
    regime: str = "mixed"  # calm|stress|crisis|mixed
    confidence: float = 0.5


def classify_regime(vol: float, corr: float) -> RegimeState:
    if vol > 0.35 or corr > 0.7:
        return RegimeState("stress", 0.7)
    if vol < 0.15 and corr < 0.4:
        return RegimeState("calm", 0.65)
    return RegimeState("mixed", 0.5)


@dataclass
class ModelCard:
    model_id: str
    data_sha: str
    calibrated: bool = False
    limits: str = ""


@dataclass
class ModelRegistry:
    models: dict[str, ModelCard] = field(default_factory=dict)

    def promote(self, m: ModelCard) -> None:
        if not m.calibrated:
            raise ValueError("uncalibrated models cannot size positions")
        self.models[m.model_id] = m


def enforce_caps(weights: dict[str, float], gross_cap: float = 1.0, name_cap: float = 0.2) -> dict[str, float]:
    out = {k: max(-name_cap, min(name_cap, v)) for k, v in weights.items()}
    gross = sum(abs(v) for v in out.values())
    if gross > gross_cap:
        scale = gross_cap / gross
        out = {k: v * scale for k, v in out.items()}
    return out


def risk_limits(gross: float, var99: float, gross_cap: float = 2.0, var_cap: float = 0.05) -> dict:
    breaches = []
    if gross > gross_cap:
        breaches.append("gross")
    if var99 > var_cap:
        breaches.append("var99")
    return {"ok": not breaches, "breaches": breaches}
