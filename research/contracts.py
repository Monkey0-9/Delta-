"""W45 integration contracts: CLI ResearchSpec -> ExperimentSpec mapping.

Frozen contract for `delta research`. No pipeline execution here (W48).
Deterministic, fail-closed, stdlib-only (no torch/numpy).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
import json
from typing import Any


# Multi-asset universe registry (design target; W46 builds loaders).
# SP500 today, bonds/treasury/ETF/macro staged next.
SUPPORTED_UNIVERSES: tuple[str, ...] = (
    "SP500",
    "EQUITY_US",
    "ETF_US",
    "BONDS_CORP",
    "TREASURY",
    "MACRO_FX",
)

SUPPORTED_STRATEGIES: tuple[str, ...] = (
    "momentum",
    "mean_reversion",
    "value",
    "quality",
    "carry",
)

SUPPORTED_COST_MODELS: tuple[str, ...] = (
    "realistic-v1",
    "conservative-v1",
)


def _parse_date(value: str) -> date:
    try:
        y, m, d = (int(p) for p in value.split("-"))
        return date(y, m, d)
    except Exception as exc:
        raise ValueError(f"invalid date '{value}', expected YYYY-MM-DD.") from exc


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ResearchSpec:
    """CLI-level contract for `delta research` (W45)."""

    asset_universe: str
    strategy: str
    start: str  # YYYY-MM-DD
    end: str  # YYYY-MM-DD
    cost_model: str = "realistic-v1"
    seed: int = 42
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.asset_universe not in SUPPORTED_UNIVERSES:
            raise ValueError(f"unsupported universe '{self.asset_universe}'. Supported: {SUPPORTED_UNIVERSES}")
        if self.strategy not in SUPPORTED_STRATEGIES:
            raise ValueError(f"unsupported strategy '{self.strategy}'. Supported: {SUPPORTED_STRATEGIES}")
        if self.cost_model not in SUPPORTED_COST_MODELS:
            raise ValueError(f"unsupported cost_model '{self.cost_model}'.")
        start_d = _parse_date(self.start)
        end_d = _parse_date(self.end)
        if start_d >= end_d:
            raise ValueError("start must precede end (YYYY-MM-DD).")
        if self.seed < 0:
            raise ValueError("seed must be non-negative.")

    def experiment_id(self) -> str:
        digest = canonical_hash(
            {
                "universe": self.asset_universe,
                "strategy": self.strategy,
                "start": self.start,
                "end": self.end,
                "cost_model": self.cost_model,
                "seed": self.seed,
                "parameters": self.parameters,
            }
        )
        return f"EXP-{digest[:8].upper()}"

    def train_val_test_windows(self) -> dict[str, str]:
        """Deterministic 60/20/20 chronological split of [start, end]."""
        start_d = _parse_date(self.start)
        end_d = _parse_date(self.end)
        total_days = (end_d - start_d).days
        if total_days < 30:
            raise ValueError("window too short for train/val/test split (need >= 30 days).")
        train_days = int(total_days * 0.6)
        val_days = int(total_days * 0.2)
        from datetime import timedelta

        train_end = start_d + timedelta(days=train_days)
        val_end = train_end + timedelta(days=val_days)
        return {
            "train_start": start_d.isoformat(),
            "train_end": train_end.isoformat(),
            "validation_start": train_end.isoformat(),
            "validation_end": val_end.isoformat(),
            "test_start": val_end.isoformat(),
            "test_end": end_d.isoformat(),
        }

    def to_experiment_kwargs(self, *, code_commit: str, dataset_id: str, dataset_hash: str) -> dict[str, Any]:
        windows = self.train_val_test_windows()
        return {
            "experiment_id": self.experiment_id(),
            "hypothesis": f"{self.strategy} signal contains predictive information in {self.asset_universe}.",
            "code_commit": code_commit,
            "dataset_id": dataset_id,
            "dataset_hash": dataset_hash,
            "model_id": None,
            "random_seed": self.seed,
            "universe": self.asset_universe,
            "cost_model": self.cost_model,
            "parameters": {"strategy": self.strategy, **self.parameters},
            **windows,
        }

    def manifest(self, *, code_commit: str = "uncommitted", dataset_hash: str = "pending-w46") -> dict[str, Any]:
        windows = self.train_val_test_windows()
        return {
            "schema": "delta.research_manifest.v1",
            "experiment_id": self.experiment_id(),
            "universe": self.asset_universe,
            "strategy": self.strategy,
            "start": self.start,
            "end": self.end,
            "cost_model": self.cost_model,
            "seed": self.seed,
            "parameters": self.parameters,
            "windows": windows,
            "code_commit": code_commit,
            "dataset_hash": dataset_hash,
            "pit_contract": {
                "required_fields": list(PIT_REQUIRED_FIELDS),
                "rule": "research may only see effective_time <= decision_time",
            },
        }


# PIT event contract shared by data factory (W46), replay, and research.
PIT_REQUIRED_FIELDS: tuple[str, ...] = (
    "event_id",
    "event_time",
    "received_time",
    "published_time",
    "effective_time",
    "source",
    "payload",
)

# Per-asset-class bar/manifest fields staged for W46 loaders.
BAR_FIELDS_BY_ASSET: dict[str, tuple[str, ...]] = {
    "equity": ("symbol", "open", "high", "low", "close", "volume", "adj_factor", *PIT_REQUIRED_FIELDS),
    "etf": ("symbol", "open", "high", "low", "close", "volume", "adj_factor", *PIT_REQUIRED_FIELDS),
    "bond_corp": ("cusip", "price", "coupon", "maturity", *PIT_REQUIRED_FIELDS),
    "treasury": ("tenor", "yield", *PIT_REQUIRED_FIELDS),
    "macro_fx": ("pair", "rate", *PIT_REQUIRED_FIELDS),
}

RESEARCH_MANIFEST_SCHEMA = "delta.research_manifest.v1"
