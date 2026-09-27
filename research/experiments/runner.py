from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

from research.ledger.experiment import ExperimentSpec
from research.ledger.result import ExperimentResult
from research.ledger.registry import ResearchRegistry


@dataclass
class ExperimentRunner:
    registry: ResearchRegistry

    def run(
        self,
        spec: ExperimentSpec,
        experiment: Callable[[ExperimentSpec], ExperimentResult],
    ) -> ExperimentResult:

        result = experiment(spec)

        self.registry.append(
            {
                "type": "experiment_result",
                "experiment": spec.to_dict(),
                "result": {
                    "experiment_id": result.experiment_id,
                    "experiment_fingerprint": result.experiment_fingerprint,
                    "validation_passed": result.validation_passed,
                    "rejection_reasons": list(
                        result.rejection_reasons
                    ),
                    "artifact_hash": result.artifact_hash,
                    "metrics": result.metrics.__dict__,
                },
            }
        )

        return result