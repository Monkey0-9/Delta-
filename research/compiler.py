"""Research Compiler: high-level StrategySpec -> executable research plan.

One specification drives the backtest configuration, the validation plan
(walk-forward + OOS + stress + ablation), and the experiment manifest —
reducing research-to-production mismatch to a single reviewed artifact.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategySpec:
    strategy_id: str
    universe: tuple[str, ...]
    features: tuple[str, ...]
    signal: str
    forecast_horizon: str
    position_rule: str
    risk_rule: str
    execution_rule: str
    cost_model: str = "standard"
    strategy_version: str = "v1"
    seed: int = 0

    def __post_init__(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("strategy_id required.")
        if not self.universe or not self.features:
            raise ValueError("universe and features cannot be empty.")


@dataclass(frozen=True, slots=True)
class CompiledStrategy:
    strategy_id: str
    backtest_config: dict
    validation_plan: tuple[str, ...]
    manifest: object
    plan_hash: str


def compile_strategy(
    spec: StrategySpec,
    *,
    dataset_hash: str = "unknown",
    code_version: str = "unknown",
    train: int = 252,
    test: int = 63,
    step: int = 63,
    purge: int = 5,
    embargo: int = 5,
) -> CompiledStrategy:
    import hashlib
    import json

    from research.experiments.manifest import ExperimentManifest

    backtest_config = {
        "strategy_id": spec.strategy_id,
        "universe": list(spec.universe),
        "features": list(spec.features),
        "signal": spec.signal,
        "forecast_horizon": spec.forecast_horizon,
        "position_rule": spec.position_rule,
        "risk_rule": spec.risk_rule,
        "execution_rule": spec.execution_rule,
        "cost_model": spec.cost_model,
        "seed": spec.seed,
    }
    validation_plan = (
        f"walk_forward:train={train},test={test},step={step},purge={purge},embargo={embargo}",
        "oos:immutable_window",
        "stress:canonical_matrix_11",
        "protected:seeded_15",
        "ablation:full_vs_removed",
        "shadow:min_30_obs",
    )
    manifest = ExperimentManifest.create(
        experiment_id=f"compiled-{spec.strategy_id}",
        hypothesis=f"strategy {spec.strategy_id} validates end-to-end",
        strategy_version=spec.strategy_version,
        code_version=code_version,
        dataset_hash=dataset_hash,
        universe=spec.universe,
        start="train_start",
        end="oos_end",
        seed=spec.seed,
        config={**backtest_config, "validation_plan": list(validation_plan)},
    )
    plan_hash = hashlib.sha256(
        json.dumps({"config": backtest_config, "plan": validation_plan},
                   sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return CompiledStrategy(spec.strategy_id, backtest_config, validation_plan, manifest, plan_hash)
