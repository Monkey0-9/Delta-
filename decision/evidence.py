from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from core.domain.timestamp import ensure_utc


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    source: str
    observation: str
    weight: Decimal = Decimal("1")
    timestamp: datetime | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.source or not self.observation:
            raise ValueError("evidence ref requires id/source/observation.")


def evidence_ids(refs: tuple[EvidenceRef, ...]) -> tuple[str, ...]:
    return tuple(r.evidence_id for r in refs)
