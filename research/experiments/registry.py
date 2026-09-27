from __future__ import annotations

from dataclasses import dataclass, field


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


@dataclass(slots=True)
class ExperimentRegistry:
    _items: dict[str, Experiment] = field(default_factory=dict)

    def register(self, exp: Experiment) -> None:
        if exp.experiment_id in self._items:
            raise ValueError("duplicate experiment_id.")
        self._items[exp.experiment_id] = exp

    def get(self, experiment_id: str) -> Experiment:
        return self._items[experiment_id]
