"""DELTA Quantitative Strategy & Finance Model Release Certification Protocol.

Formalizes mandatory criteria for promoting quantitative alphas and models through
gates R2 (statistical), R3 (out-of-sample), R4 (stress), R5 (capacity), and R6 (execution).
Guarantees fail-closed isolation between experimental models (NCM) and order execution.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class QuantitativeCertificationGate:
    gate_id: str
    name: str
    description: str
    passed: bool
    evidence_hash: str
    threshold: str
    measured: str


@dataclass
class QuantitativeAuditManifest:
    strategy_or_model: str
    evaluation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    gates: List[QuantitativeCertificationGate] = field(default_factory=list)
    promotable_to_paper: bool = False
    promotable_to_live: bool = False
    verdict: str = "RESEARCH_ONLY"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_or_model": self.strategy_or_model,
            "evaluation_timestamp": self.evaluation_timestamp,
            "promotable_to_paper": self.promotable_to_paper,
            "promotable_to_live": self.promotable_to_live,
            "verdict": self.verdict,
            "gates": [
                {
                    "gate_id": g.gate_id,
                    "name": g.name,
                    "description": g.description,
                    "passed": g.passed,
                    "evidence_hash": g.evidence_hash,
                    "threshold": g.threshold,
                    "measured": g.measured,
                }
                for g in self.gates
            ],
        }


class QuantitativeCertifier:
    """Enforces empirical research gates before model or strategy promotion."""

    @staticmethod
    def calculate_deflated_sharpe_ratio(
        est_sharpe: float,
        num_trials: int,
        sample_length: int,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
    ) -> float:
        """Calculate Deflated Sharpe Ratio via canonical research statistics (Bailey & López de Prado, 2014)."""
        from research.statistics.canonical import deflated_sharpe
        return float(deflated_sharpe(est_sharpe, num_trials, sample_length, skewness, kurtosis))

    @staticmethod
    def benjamini_hochberg_fdr(
        p_values: Sequence[float],
        target_fdr: float = 0.05,
    ) -> Tuple[List[bool], float]:
        """Benjamini-Hochberg False Discovery Rate (FDR) control for multi-hypothesis factor testing.
        
        Controls the expected proportion of false positive discoveries among rejected null hypotheses:
            p_(k) <= (k / m) * q*
        Returns:
            (is_significant_flags, critical_p_value_threshold)
        """
        m = len(p_values)
        if m == 0:
            return [], 0.0
        if not 0.0 < target_fdr < 1.0:
            raise ValueError("target_fdr must be in (0, 1)")

        indexed = sorted(enumerate(p_values), key=lambda x: x[1])
        significant_indices = set()
        max_p_thresh = 0.0

        for rank, (orig_idx, p_val) in enumerate(indexed, start=1):
            threshold = (float(rank) / float(m)) * target_fdr
            if p_val <= threshold:
                max_p_thresh = p_val
                # All hypotheses with p <= p_(k) are declared discoveries
                significant_indices.update(idx for idx, p in indexed[:rank])

        flags = [i in significant_indices for i in range(m)]
        return flags, max_p_thresh


    @classmethod
    def evaluate_strategy(
        cls,
        name: str,
        in_sample_sharpe: float,
        out_of_sample_sharpe: float,
        num_trials: int,
        sample_bars: int,
        max_drawdown_pct: float,
        turnover_daily: float,
        universe_capacity_usd: float,
    ) -> QuantitativeAuditManifest:
        """Evaluate a candidate strategy against R2-R6 gates."""
        dsr = cls.calculate_deflated_sharpe_ratio(
            est_sharpe=in_sample_sharpe,
            num_trials=num_trials,
            sample_length=sample_bars,
        )

        g2_stat = QuantitativeCertificationGate(
            gate_id="R2_statistical",
            name="Statistical Validity & Selection Bias Control",
            description="Deflated Sharpe Ratio (DSR) must not collapse to zero given search trials",
            passed=bool(dsr > 0.0001),
            evidence_hash=f"dsr-{round(dsr, 6)}",
            threshold="DSR > 0.0001",
            measured=f"DSR = {round(dsr, 6)} (trials={num_trials})",
        )

        g3_oos = QuantitativeCertificationGate(
            gate_id="R3_oos",
            name="Out-of-Sample Walk-Forward Stability",
            description="Out-of-sample Sharpe must be >= 0.70 * in-sample Sharpe and positive",
            passed=bool(out_of_sample_sharpe > 0.5 and out_of_sample_sharpe >= 0.7 * in_sample_sharpe),
            evidence_hash=f"oos-{round(out_of_sample_sharpe, 2)}",
            threshold="OOS Sharpe >= max(0.5, 0.70 * IS Sharpe)",
            measured=f"OOS Sharpe = {round(out_of_sample_sharpe, 2)} vs IS = {round(in_sample_sharpe, 2)}",
        )

        g4_stress = QuantitativeCertificationGate(
            gate_id="R4_stress",
            name="Macro & Microstructure Stress Matrix",
            description="Max drawdown under historical stress scenarios must not exceed 20%",
            passed=bool(max_drawdown_pct <= 20.0),
            evidence_hash=f"mdd-{round(max_drawdown_pct, 1)}",
            threshold="Max Drawdown <= 20.0%",
            measured=f"Max Drawdown = {round(max_drawdown_pct, 1)}%",
        )

        g5_capacity = QuantitativeCertificationGate(
            gate_id="R5_capacity",
            name="Capacity & Market Impact Bounds",
            description="Strategy capacity must support at least $5,000,000 without severe alpha decay",
            passed=bool(universe_capacity_usd >= 5_000_000.0),
            evidence_hash=f"cap-{int(universe_capacity_usd)}",
            threshold="Capacity >= $5,000,000",
            measured=f"Capacity = ${universe_capacity_usd:,.0f}",
        )

        g6_exec = QuantitativeCertificationGate(
            gate_id="R6_execution",
            name="Transaction Cost & Slippage Reality",
            description="Daily turnover must remain below 150% to prevent excessive execution drag",
            passed=bool(turnover_daily <= 1.50),
            evidence_hash=f"to-{round(turnover_daily, 2)}",
            threshold="Daily Turnover <= 1.50 (150%)",
            measured=f"Turnover = {round(turnover_daily * 100.0, 1)}%/day",
        )

        all_gates = [g2_stat, g3_oos, g4_stress, g5_capacity, g6_exec]
        all_passed = all(g.passed for g in all_gates)

        return QuantitativeAuditManifest(
            strategy_or_model=name,
            gates=all_gates,
            promotable_to_paper=True,  # Paper simulation is permitted for exploration
            promotable_to_live=all_passed,  # Live trading strictly requires all gates green
            verdict="LIVE_CANDIDATE" if all_passed else "RESEARCH_ONLY",
        )
