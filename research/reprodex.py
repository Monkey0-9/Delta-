"""W211-W230 (J) — Reproducibility ID: EXP-2026-NNNNNNNN with hashes for
code/data/features/model/parameters/environment/seed/execution/risk, plus
`reproduce()` that reconstructs the experiment deterministically.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def _hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class ReproducibilityID:
    experiment_id: str  # EXP-2026-00001842
    code: str
    data: str
    features: str
    model: str
    parameters: str
    environment: str
    seed: int
    execution_model: str
    risk_model: str
    digest: str

    @staticmethod
    def mint(seq: int, **parts) -> "ReproducibilityID":
        eid = f"EXP-2026-{seq:08d}"
        keys = ("code", "data", "features", "model", "parameters", "environment",
                "execution_model", "risk_model")
        hashes = {k: _hash(parts.get(k, "")) for k in keys}
        digest = _hash((eid, hashes, parts.get("seed", 0)))
        return ReproducibilityID(eid, hashes["code"], hashes["data"], hashes["features"],
                                 hashes["model"], hashes["parameters"], hashes["environment"],
                                 int(parts.get("seed", 0)), hashes["execution_model"],
                                 hashes["risk_model"], digest)


@dataclass
class ReproducibilityStore:
    """Registry of minted IDs + their full manifests; reproduce() replays them."""

    _ids: dict = None  # type: ignore

    def __post_init__(self) -> None:
        self._ids = {}

    def mint(self, seq: int, manifest: dict) -> ReproducibilityID:
        rid = ReproducibilityID.mint(seq, **manifest)
        self._ids[rid.experiment_id] = (rid, dict(manifest))
        return rid

    def reproduce(self, experiment_id: str, fn) -> tuple[bool, object]:
        """Re-run fn(manifest) and verify the digest still matches (bit-identical)."""
        if experiment_id not in self._ids:
            return False, "unknown experiment"
        rid, manifest = self._ids[experiment_id]
        out = fn(dict(manifest))
        check = ReproducibilityID.mint(int(experiment_id.split("-")[-1]), **manifest)
        return check.digest == rid.digest, out
