from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


LIFECYCLE = ("RESEARCH", "VALIDATED", "PAPER", "SHADOW", "PROD", "RETIRED")

_PROMOTION: dict[str, tuple[str, ...]] = {
    "RESEARCH": ("VALIDATED",),
    "VALIDATED": ("PAPER",),
    "PAPER": ("SHADOW",),
    "SHADOW": ("PROD",),
    "PROD": ("RETIRED",),
}


@dataclass(frozen=True, slots=True)
class Experiment:
    experiment_id: str
    dataset_hash: str
    code_commit: str
    model_version: str
    strategy_version: str
    universe: str
    window: str
    cost_model: str
    metrics: str = ""
    conclusion: str = ""
    limitations: str = ""
    # W231-W250 provenance bundle (optional at registration, required at promotion)
    feature_version: str = ""
    parameter_version: str = ""
    seed: int = 0
    train_interval: str = ""
    validation_interval: str = ""
    oos_interval: str = ""
    execution_model: str = ""
    benchmark: str = ""
    state: str = "RESEARCH"

    def evidence_bundle(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "dataset_hash": self.dataset_hash,
            "code_commit": self.code_commit,
            "feature_version": self.feature_version,
            "model_version": self.model_version,
            "parameter_version": self.parameter_version,
            "seed": self.seed,
            "train_interval": self.train_interval,
            "validation_interval": self.validation_interval,
            "oos_interval": self.oos_interval,
            "cost_model": self.cost_model,
            "execution_model": self.execution_model,
            "benchmark": self.benchmark,
            "metrics": self.metrics,
            "conclusion": self.conclusion,
            "limitations": self.limitations,
            "state": self.state,
        }


@dataclass(slots=True)
class ExperimentRegistry:
    _items: dict[str, Experiment] = field(default_factory=dict)
    _history: list[tuple[str, str, str, str]] = field(default_factory=list)

    def register(self, exp: Experiment) -> None:
        if exp.experiment_id in self._items:
            raise ValueError("duplicate experiment_id.")
        if exp.state not in LIFECYCLE:
            raise ValueError(f"unknown lifecycle state: {exp.state}.")
        self._items[exp.experiment_id] = exp
        self._history.append((exp.experiment_id, "REGISTER", exp.state,
                              datetime.now(timezone.utc).isoformat()))

    def get(self, experiment_id: str) -> Experiment:
        return self._items[experiment_id]

    def promote(self, experiment_id: str, to_state: str) -> Experiment:
        """W241-W250 automated promotion gate: only adjacent transitions allowed."""
        current = self._items[experiment_id]
        allowed = _PROMOTION.get(current.state, ())
        if to_state not in allowed:
            raise ValueError(f"illegal promotion {current.state} -> {to_state}.")
        if to_state in ("VALIDATED", "PAPER", "SHADOW", "PROD") and not current.dataset_hash:
            raise ValueError("promotion requires dataset_hash provenance.")
        from dataclasses import replace
        updated = replace(current, state=to_state)
        self._items[experiment_id] = updated
        self._history.append((experiment_id, "PROMOTE", to_state,
                              datetime.now(timezone.utc).isoformat()))
        return updated

    def retire(self, experiment_id: str) -> Experiment:
        from dataclasses import replace
        current = self._items[experiment_id]
        updated = replace(current, state="RETIRED")
        self._items[experiment_id] = updated
        self._history.append((experiment_id, "RETIRE", "RETIRED",
                              datetime.now(timezone.utc).isoformat()))
        return updated
