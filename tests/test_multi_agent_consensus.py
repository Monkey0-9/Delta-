"""Test suite for Multi-Agent Consensus Synthesizer and Risk Precedence."""
from agents.contracts import AgentEvidence, AgentFinding, AgentRole, ResearchPacket
from agents.consensus import (
    ConsensusDecision,
    ConsensusReport,
    ConsensusSynthesizer,
)
from agents.orchestrator import ResearchOrchestrator


def _ev(eid: str, rel: float = 0.8) -> AgentEvidence:
    return AgentEvidence(eid, "source", "claim", "2026-10-25T12:00:00Z", rel)


def test_hard_risk_specialist_veto():
    # If the risk specialist reports breaches, the consensus MUST veto
    findings = (
        AgentFinding(
            "quant-01", AgentRole.QUANT, "AAPL", "strong bullish momentum",
            0.04, 0.9, "inv", (_ev("e1", 0.85),), "2026-10-25T12:00:00Z"
        ),
        AgentFinding(
            "risk-01", AgentRole.RISK, "AAPL", "risk BLOCKED: breaches present",
            0.0, 0.95, "inv", (_ev("r1", 0.95),), "2026-10-25T12:00:00Z"
        ),
    )
    packet = ResearchPacket("p1", "AAPL", findings, 1)

    syn = ConsensusSynthesizer()
    rep = syn.synthesize(packet)

    assert rep.decision == ConsensusDecision.VETOED_BY_RISK
    assert rep.risk_veto is True
    assert rep.consensus_return == 0.0
    assert len(rep.veto_reasons) > 0


def test_epistemic_dispersion_forces_abstention():
    # If alpha specialists strongly contradict each other, system must abstain
    findings = (
        AgentFinding(
            "quant-01", AgentRole.QUANT, "TSLA", "bullish momentum",
            0.08, 0.85, "inv", (_ev("e1", 0.8),), "2026-10-25T12:00:00Z"
        ),
        AgentFinding(
            "fund-01", AgentRole.FUNDAMENTAL, "TSLA", "deeply overvalued bubble",
            -0.08, 0.85, "inv", (_ev("e2", 0.8),), "2026-10-25T12:00:00Z"
        ),
    )
    packet = ResearchPacket("p2", "TSLA", findings, 1)

    syn = ConsensusSynthesizer(max_dispersion_threshold=0.03)
    rep = syn.synthesize(packet)

    assert rep.decision == ConsensusDecision.ABSTAIN_HIGH_DISPERSION
    assert rep.dispersion > 0.03


def test_aligned_consensus_approval():
    findings = (
        AgentFinding(
            "quant-01", AgentRole.QUANT, "MSFT", "positive drift",
            0.02, 0.8, "inv", (_ev("e1", 0.8),), "2026-10-25T12:00:00Z"
        ),
        AgentFinding(
            "macro-01", AgentRole.MACRO, "MSFT", "favorable rates",
            0.015, 0.75, "inv", (_ev("e2", 0.75),), "2026-10-25T12:00:00Z"
        ),
        AgentFinding(
            "risk-01", AgentRole.RISK, "MSFT", "risk within limits",
            0.0, 0.9, "inv", (_ev("r1", 0.9),), "2026-10-25T12:00:00Z"
        ),
    )
    packet = ResearchPacket("p3", "MSFT", findings, 1)

    rep = ResearchOrchestrator.synthesize_consensus(packet)

    assert rep.decision == ConsensusDecision.APPROVE_LONG
    assert rep.consensus_return > 0.01
    assert rep.risk_veto is False
