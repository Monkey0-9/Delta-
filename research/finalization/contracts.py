from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class WaveResult:
    wave: str
    name: str
    status: str
    evidence: str
    measured: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentManifest:
    experiment_id: str
    hypothesis: str
    strategy_version: str
    code_version: str
    dataset_id: str
    dataset_hash: str
    universe: tuple[str, ...]
    start_date: str
    end_date: str
    seed: int
    configuration: dict[str, Any]
    created_at: str

    @property
    def manifest_hash(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class MetricResult:
    strategy: str
    observations: int
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    hit_rate: float
    var_95: float
    cvar_95: float
    mean_return: float
    t_stat: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    implementation: str
    iterations: int
    elapsed_seconds: float
    operations_per_second: float
    measured: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReleaseGate:
    name: str
    status: str
    required: bool
    evidence: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalReport:
    release: str
    generated_at: str
    waves: tuple[WaveResult, ...]
    gates: tuple[ReleaseGate, ...]
    artifacts: tuple[str, ...]
    research_claims_allowed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "release": self.release,
            "generated_at": self.generated_at,
            "waves": [
                wave.to_dict()
                for wave in self.waves
            ],
            "gates": [
                gate.to_dict()
                for gate in self.gates
            ],
            "artifacts": list(self.artifacts),
            "research_claims_allowed": (
                self.research_claims_allowed
            ),
        }
