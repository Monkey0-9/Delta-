"""G13/G14/G15 — Lake manifests + quality gate + reference versioning (thin truthful slice)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def manifest_hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class QualityVerdict:
    ok: bool
    reason: str
    score: float = 1.0


def quality_gate(missing: int, dup: int, stale: bool, threshold: float = 0.7) -> QualityVerdict:
    score = 1.0 - 0.2 * min(missing, 5) - 0.2 * min(dup, 5) - (0.5 if stale else 0.0)
    score = max(0.0, score)
    if score < threshold:
        return QualityVerdict(False, "below-threshold data blocks promotion", score)
    return QualityVerdict(True, "pass", score)


def reference_version(table: dict) -> str:
    return manifest_hash(table)[:16]
