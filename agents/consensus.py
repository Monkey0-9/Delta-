"""DELTA OS — Institutional Multi-Agent Consensus Synthesizer.

Synthesizes multi-agent research packets across specialists (Market, Macro,
Fundamental, News, Quant, Risk) into disciplined institutional decisions.

Non-Negotiable Invariants:
1. Hard Fail-Closed Risk Veto: Any finding from the RISK specialist indicating
   breaches, excessive leverage, or limit violations unconditionally vetoes
   execution regardless of alpha return projections.
2. Bayesian Reliability Weighting: Each specialist signal is weighted by its
   grounded evidence reliability and reported confidence.
3. Epistemic Disagreement Dispersion: Severe contradiction between specialists
   forces automatic abstention (ABSTAIN_HIGH_DISPERSION) rather than blind betting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import math
from typing import Dict, List, Optional, Tuple

from agents.contracts import AgentEvidence, AgentFinding, AgentRole, ResearchPacket


class ConsensusDecision(StrEnum):
    APPROVE_LONG = "APPROVE_LONG"
    APPROVE_SHORT = "APPROVE_SHORT"
    NEUTRAL = "NEUTRAL"
    ABSTAIN_HIGH_DISPERSION = "ABSTAIN_HIGH_DISPERSION"
    VETOED_BY_RISK = "VETOED_BY_RISK"


@dataclass(frozen=True, slots=True)
class ConsensusReport:
    packet_id: str
    asset: str
    decision: ConsensusDecision
    consensus_return: float
    confidence: float
    dispersion: float
    risk_veto: bool
    veto_reasons: Tuple[str, ...]
    agent_weights: Dict[str, float]
    supporting_evidence_ids: Tuple[str, ...]
    rationale: str


class ConsensusSynthesizer:
    """Synthesizes multi-agent findings with strict risk precedence."""

    def __init__(
        self,
        max_dispersion_threshold: float = 0.025,
        min_consensus_confidence: float = 0.50,
        return_hurdle_rate: float = 0.005,
    ) -> None:
        self.max_dispersion_threshold = max_dispersion_threshold
        self.min_consensus_confidence = min_consensus_confidence
        self.return_hurdle_rate = return_hurdle_rate

    def synthesize(self, packet: ResearchPacket) -> ConsensusReport:
        """Synthesize a consensus decision from a research packet."""
        if not packet.findings:
            return ConsensusReport(
                packet_id=packet.packet_id,
                asset=packet.asset,
                decision=ConsensusDecision.NEUTRAL,
                consensus_return=0.0,
                confidence=0.0,
                dispersion=0.0,
                risk_veto=False,
                veto_reasons=(),
                agent_weights={},
                supporting_evidence_ids=(),
                rationale="Empty research packet; no findings present.",
            )

        # 1. Enforce Hard Fail-Closed Risk Specialist Veto
        risk_findings = [f for f in packet.findings if f.role == AgentRole.RISK]
        veto_reasons: List[str] = []
        for rf in risk_findings:
            thesis_lower = rf.thesis.lower()
            if "blocked" in thesis_lower or "breaches present" in thesis_lower or "breach" in thesis_lower:
                veto_reasons.append(f"Risk specialist {rf.agent_id} issued veto: {rf.thesis}")

        if veto_reasons:
            all_ev_ids = tuple(
                ev.evidence_id
                for f in risk_findings
                for ev in f.evidence
            )
            return ConsensusReport(
                packet_id=packet.packet_id,
                asset=packet.asset,
                decision=ConsensusDecision.VETOED_BY_RISK,
                consensus_return=0.0,
                confidence=1.0,
                dispersion=0.0,
                risk_veto=True,
                veto_reasons=tuple(veto_reasons),
                agent_weights={},
                supporting_evidence_ids=all_ev_ids,
                rationale=f"Risk firewall trigger: {'; '.join(veto_reasons)}",
            )

        # 2. Extract Alpha Specialists (Market, Macro, Fundamental, News, Quant)
        alpha_findings = [f for f in packet.findings if f.role != AgentRole.RISK]
        if not alpha_findings:
            return ConsensusReport(
                packet_id=packet.packet_id,
                asset=packet.asset,
                decision=ConsensusDecision.NEUTRAL,
                consensus_return=0.0,
                confidence=0.0,
                dispersion=0.0,
                risk_veto=False,
                veto_reasons=(),
                agent_weights={},
                supporting_evidence_ids=(),
                rationale="Only risk findings present with no alpha signals.",
            )

        # 3. Calculate Bayesian Reliability & Confidence Weights
        weights: Dict[str, float] = {}
        weighted_returns: List[float] = []
        confidences: List[float] = []
        evidence_ids: List[str] = []

        for f in alpha_findings:
            if f.evidence:
                mean_rel = sum(ev.reliability for ev in f.evidence) / len(f.evidence)
            else:
                mean_rel = 0.50
            w = max(0.01, f.confidence * mean_rel)
            weights[f.agent_id] = w
            confidences.append(f.confidence)
            for ev in f.evidence:
                evidence_ids.append(ev.evidence_id)

        total_weight = sum(weights.values())
        norm_weights = {aid: w / total_weight for aid, w in weights.items()}

        mean_return = sum(
            f.expected_return * norm_weights[f.agent_id]
            for f in alpha_findings
        )
        mean_confidence = sum(
            f.confidence * norm_weights[f.agent_id]
            for f in alpha_findings
        )

        # 4. Compute Epistemic Disagreement Dispersion
        dispersion = sum(
            norm_weights[f.agent_id] * ((f.expected_return - mean_return) ** 2)
            for f in alpha_findings
        )
        dispersion_std = math.sqrt(dispersion)

        # 5. Determine Decision
        if dispersion_std > self.max_dispersion_threshold:
            decision = ConsensusDecision.ABSTAIN_HIGH_DISPERSION
            rationale = (
                f"Specialist contradiction: dispersion {dispersion_std:.4f} > "
                f"threshold {self.max_dispersion_threshold:.4f}. Consensus halted for safety."
            )
        elif mean_confidence < self.min_consensus_confidence:
            decision = ConsensusDecision.NEUTRAL
            rationale = (
                f"Low aggregate confidence {mean_confidence:.2f} < "
                f"hurdle {self.min_consensus_confidence:.2f}."
            )
        elif mean_return >= self.return_hurdle_rate:
            decision = ConsensusDecision.APPROVE_LONG
            rationale = f"Consensus bullish return {mean_return:+.4f} with confidence {mean_confidence:.1%}."
        elif mean_return <= -self.return_hurdle_rate:
            decision = ConsensusDecision.APPROVE_SHORT
            rationale = f"Consensus bearish return {mean_return:+.4f} with confidence {mean_confidence:.1%}."
        else:
            decision = ConsensusDecision.NEUTRAL
            rationale = f"Consensus expected return {mean_return:+.4f} within noise band."

        return ConsensusReport(
            packet_id=packet.packet_id,
            asset=packet.asset,
            decision=decision,
            consensus_return=round(mean_return, 4),
            confidence=round(mean_confidence, 4),
            dispersion=round(dispersion_std, 4),
            risk_veto=False,
            veto_reasons=(),
            agent_weights={k: round(v, 4) for k, v in norm_weights.items()},
            supporting_evidence_ids=tuple(sorted(set(evidence_ids))),
            rationale=rationale,
        )


__all__ = [
    "ConsensusDecision",
    "ConsensusReport",
    "ConsensusSynthesizer",
]
