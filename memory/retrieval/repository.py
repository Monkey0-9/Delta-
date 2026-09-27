from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    record_id: UUID
    kind: str
    text: str
    regime: str | None
    instrument_id: UUID | None
    score: Decimal


class MemoryRepository:
    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def add(self, record: MemoryRecord) -> None:
        self._records.append(record)

    def all(self) -> tuple[MemoryRecord, ...]:
        return tuple(self._records)

    def search(
        self,
        *,
        kind: str | None = None,
        regime: str | None = None,
        instrument_id: UUID | None = None,
        limit: int = 10,
    ) -> tuple[MemoryRecord, ...]:

        if limit <= 0:
            raise ValueError("limit must be positive")

        candidates: Iterable[MemoryRecord] = self._records

        if kind is not None:
            candidates = (
                record
                for record in candidates
                if record.kind == kind
            )

        if regime is not None:
            candidates = (
                record
                for record in candidates
                if record.regime == regime
            )

        if instrument_id is not None:
            candidates = (
                record
                for record in candidates
                if record.instrument_id == instrument_id
            )

        return tuple(
            sorted(
                candidates,
                key=lambda record: record.score,
                reverse=True,
            )[:limit]
        )