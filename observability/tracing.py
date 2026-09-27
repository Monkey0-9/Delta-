from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class TraceContext:
    trace_id: UUID
    correlation_id: UUID
    causation_id: UUID | None = None

    @classmethod
    def create(
        cls,
        *,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> "TraceContext":
        return cls(
            trace_id=uuid4(),
            correlation_id=correlation_id or uuid4(),
            causation_id=causation_id,
        )