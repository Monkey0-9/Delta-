from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class QualityReport:
    total: int
    rejected: int
    duplicates: int
    out_of_order: int
    dataset_hash: str


def dataset_hash(canonical_rows: tuple[str, ...]) -> str:
    h = sha256()
    for row in canonical_rows:
        h.update(row.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()
