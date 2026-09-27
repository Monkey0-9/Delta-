"""Alpha Research Factory: hypothesis -> features -> signal -> backtest -> registry.

Orchestrates existing DELTA pieces (walk-forward splits with purge/embargo,
experiment manifest + registry). Strategy math arrives via callables so the
factory never hard-codes alpha assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    feature_family: str
    signal_name: str
    universe: tuple[str, ...]
    strategy_version: str = "v1"

    def __post_init__(self) -> None:
        if not self.hypothesis_id.strip() or not self.statement.strip():
            raise ValueError("hypothesis_id and statement required.")
        if not self.universe:
            raise ValueError("universe cannot be empty.")


@dataclass(frozen=True, slots=True)
class AlphaResult:
    hypothesis_id: str
    experiment_id: str
    n_windows: int
    mean_score: float
    oos_score: float
    passed: bool
    manifest_hash: str


class AlphaFactory:
    """End-to-end hypothesis test with chronological discipline."""

    def __init__(self, registry=None) -> None:
        from research.experiments.registry import ExperimentRegistry

        self._registry = registry or ExperimentRegistry()

    def run(
        self,
        hypothesis: Hypothesis,
        *,
        n: int,
        train: int,
        test: int,
        step: int,
        purge: int = 0,
        embargo: int = 0,
        backtest_fn: Callable[[int, int, int, int], float],
        oos_fn: Callable[[], float] | None = None,
        min_mean_score: float = 0.0,
        min_oos_score: float = 0.0,
        dataset_hash: str = "unknown",
        code_version: str = "unknown",
        seed: int = 0,
    ) -> AlphaResult:
        from research.experiments.manifest import ExperimentManifest
        from research.experiments.registry import Experiment
        from validation.walk_forward.splitter import walk_forward_splits

        splits = walk_forward_splits(n, train=train, test=test, step=step, purge=purge, embargo=embargo)
        scores = [float(backtest_fn(s.train_start, s.train_end, s.test_start, s.test_end)) for s in splits]
        mean_score = sum(scores) / len(scores)
        oos_score = float(oos_fn()) if oos_fn else mean_score
        passed = mean_score >= min_mean_score and oos_score >= min_oos_score

        experiment_id = f"alpha-{hypothesis.hypothesis_id}"
        manifest = ExperimentManifest.create(
            experiment_id=experiment_id,
            hypothesis=hypothesis.statement,
            strategy_version=hypothesis.strategy_version,
            code_version=code_version,
            dataset_hash=dataset_hash,
            universe=hypothesis.universe,
            start=str(splits[0].train_start),
            end=str(splits[-1].test_end),
            seed=seed,
            config={"train": train, "test": test, "step": step, "purge": purge, "embargo": embargo,
                    "mean_score": mean_score, "oos_score": oos_score},
        )
        self._registry.register(Experiment(
            experiment_id=experiment_id,
            dataset_hash=dataset_hash,
            code_commit=code_version,
            model_version=hypothesis.signal_name,
            strategy_version=hypothesis.strategy_version,
            universe=",".join(hypothesis.universe),
            window=f"{splits[0].train_start}:{splits[-1].test_end}",
            cost_model="standard",
            metrics=f"mean={mean_score:.6f} oos={oos_score:.6f} windows={len(splits)}",
            conclusion="PASS" if passed else "FAIL",
            limitations="research-only; paper validation required",
        ))
        return AlphaResult(hypothesis.hypothesis_id, experiment_id, len(splits), mean_score, oos_score, passed, manifest.manifest_hash)
