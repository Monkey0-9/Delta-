from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AgentRole(str, Enum):
    MARKET = "MARKET"
    MACRO = "MACRO"
    FUNDAMENTAL = "FUNDAMENTAL"
    NEWS = "NEWS"
    QUANT = "QUANT"
    RISK = "RISK"


@dataclass(frozen=True, slots=True)
class AgentEvidence:

    evidence_id: str
    source: str
    claim: str
    timestamp: str
    reliability: float

    def __post_init__(self):

        if not self.evidence_id:
            raise ValueError(
                "evidence_id required"
            )

        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError(
                "reliability outside [0,1]"
            )


@dataclass(frozen=True, slots=True)
class AgentFinding:

    agent_id: str
    role: AgentRole
    asset: str
    thesis: str
    expected_return: float
    confidence: float
    invalidation: str
    evidence: tuple[AgentEvidence, ...]
    timestamp: str


@dataclass(frozen=True, slots=True)
class ResearchPacket:

    packet_id: str
    asset: str
    findings: tuple[AgentFinding, ...]
    world_state_version: int

    @property
    def agents(self) -> tuple[str, ...]:
        return tuple(
            finding.agent_id
            for finding in self.findings
        )

    @property
    def evidence_count(self) -> int:
        return sum(
            len(finding.evidence)
            for finding in self.findings
        )