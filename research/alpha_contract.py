"""ONE AlphaContract / Registry / Metadata (Stream B P0).

Unifies research/alpha_factory (G1), alpha_factory_v2 (G2), quant/alpha/families,
research/alpha_lab into a single contract. Legacy factories delegate here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json

from core.domain.canonical import ResearchGrade


@dataclass(frozen=True, slots=True)
class AlphaMetadata:
    factor_id: str
    formula: str
    hypothesis: str
    data_dependencies: tuple[str, ...]
    pit_requirement: str
    universe: str
    frequency: str
    decay_days: float = 0.0
    turnover: float = 0.0
    capacity_usd: float = 0.0
    neutralization: tuple[str, ...] = ()
    ic_is: float | None = None
    icir: float | None = None
    ic_oos: float | None = None
    cost_adjusted_sharpe: float | None = None
    n_trials: int = 1
    failure_modes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AlphaContract:
    alpha_id: str
    metadata: AlphaMetadata
    grade: ResearchGrade = ResearchGrade.UNTESTED
    dataset_hash: str = ""
    seed: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def content_hash(self) -> str:
        return sha256(json.dumps({
            "alpha_id": self.alpha_id, "formula": self.metadata.formula,
            "dataset": self.dataset_hash, "seed": self.seed,
        }, sort_keys=True).encode()).hexdigest()[:16]


class AlphaRegistry:
    """Single registry. Only VALIDATED+ grades with dataset_hash are promotable."""

    def __init__(self) -> None:
        self._items: dict[str, AlphaContract] = {}

    def register(self, contract: AlphaContract) -> None:
        if contract.alpha_id in self._items:
            raise ValueError(f"duplicate alpha {contract.alpha_id}")
        self._items[contract.alpha_id] = contract

    def promote(self, alpha_id: str, grade: ResearchGrade) -> AlphaContract:
        cur = self._items[alpha_id]
        order = list(ResearchGrade)
        if order.index(grade) < order.index(cur.grade):
            raise ValueError("no demotion via promote()")
        if grade in (ResearchGrade.VALIDATED, ResearchGrade.OOS_VALIDATED,
                     ResearchGrade.SHADOW_VALIDATED, ResearchGrade.CERTIFIED) and not cur.dataset_hash:
            raise ValueError("dataset_hash required for VALIDATED+")
        nxt = AlphaContract(alpha_id=cur.alpha_id, metadata=cur.metadata,
                            grade=grade, dataset_hash=cur.dataset_hash,
                            seed=cur.seed, created_at=cur.created_at)
        self._items[alpha_id] = nxt
        return nxt

    def certified(self) -> tuple[AlphaContract, ...]:
        return tuple(a for a in self._items.values() if a.grade == ResearchGrade.CERTIFIED)


def rank_ic(scores: list[float], forwards: list[float]) -> float:
    """Spearman rank IC helper (deterministic, no LLM)."""
    assert len(scores) == len(forwards) and len(scores) > 2
    rs = sorted(range(len(scores)), key=lambda i: scores[i])
    rf = sorted(range(len(scores)), key=lambda i: forwards[i])
    pr = [0.0] * len(scores)
    pf = [0.0] * len(scores)
    for r, i in enumerate(rs):
        pr[i] = float(r)
    for r, i in enumerate(rf):
        pf[i] = float(r)
    n = len(scores)
    mr = sum(pr) / n
    mf = sum(pf) / n
    cov = sum((a - mr) * (b - mf) for a, b in zip(pr, pf))
    vr = sum((a - mr) ** 2 for a in pr) ** 0.5
    vf = sum((b - mf) ** 2 for b in pf) ** 0.5
    return cov / (vr * vf) if vr and vf else 0.0


__all__ = ["AlphaMetadata", "AlphaContract", "AlphaRegistry", "rank_ic"]
