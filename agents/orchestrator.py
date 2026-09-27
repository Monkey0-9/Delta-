from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .contracts import (
    AgentFinding,
    AgentRole,
    ResearchPacket,
)


class ResearchAgent(Protocol):

    agent_id: str
    role: AgentRole

    def research(
        self,
        asset: str,
        world_state: object,
    ) -> AgentFinding:
        ...


@dataclass(frozen=True, slots=True)
class AgentScore:

    agent_id: str
    role: AgentRole
    confidence: float
    expected_return: float


class ResearchOrchestrator:

    def __init__(
        self,
        agents: Sequence[ResearchAgent],
    ):
        self.agents = tuple(agents)

        ids = [
            agent.agent_id
            for agent in self.agents
        ]

        if len(ids) != len(set(ids)):
            raise ValueError(
                "duplicate agent_id"
            )

    def run(
        self,
        *,
        asset: str,
        world_state: object,
        packet_id: str,
        world_state_version: int,
    ) -> ResearchPacket:

        findings = []

        for agent in self.agents:

            finding = agent.research(
                asset,
                world_state,
            )

            if finding.agent_id != agent.agent_id:
                raise ValueError(
                    "agent identity mismatch"
                )

            if finding.role != agent.role:
                raise ValueError(
                    "agent role mismatch"
                )

            findings.append(finding)

        return ResearchPacket(
            packet_id=packet_id,
            asset=asset,
            findings=tuple(findings),
            world_state_version=(
                world_state_version
            ),
        )

    @staticmethod
    def score(
        packet: ResearchPacket,
    ) -> tuple[AgentScore, ...]:

        return tuple(
            AgentScore(
                finding.agent_id,
                finding.role,
                finding.confidence,
                finding.expected_return,
            )
            for finding in packet.findings
        )