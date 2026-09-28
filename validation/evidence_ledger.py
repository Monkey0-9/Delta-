"""W231-W250 (S) — DELTA evidence ledger: never 'this strategy is good';
store experiment/dataset/period/OOS/cost/capacity/DSR/PBO/drawdown/stress/
benchmark/confidence-interval and let predefined gates decide.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    experiment: str
    dataset: str
    period: str
    oos_sharpe: float
    cost_bps: float
    capacity_usd: float
    dsr: float
    pbo: float
    drawdown: float
    stress_passed: bool
    benchmark_sharpe: float
    ci_low: float
    ci_high: float


@dataclass
class EvidenceLedger:
    gate_oos: float = 0.5
    gate_dsr: float = 0.8
    gate_pbo: float = 0.4

    records: list[EvidenceRecord] = field(default_factory=list)

    def submit(self, r: EvidenceRecord) -> None:
        self.records.append(r)

    def verdict(self, experiment: str) -> dict:
        recs = [r for r in self.records if r.experiment == experiment]
        if not recs:
            return {"experiment": experiment, "passed": False, "reason": "no evidence"}
        r = recs[-1]
        checks = {
            "oos": r.oos_sharpe >= self.gate_oos,
            "dsr": r.dsr >= self.gate_dsr,
            "pbo": r.pbo <= self.gate_pbo,
            "stress": r.stress_passed,
            "beats_benchmark": r.oos_sharpe > r.benchmark_sharpe,
            "ci_positive": r.ci_low > 0,
        }
        return {"experiment": experiment, "passed": all(checks.values()),
                "checks": checks, "record": r}
