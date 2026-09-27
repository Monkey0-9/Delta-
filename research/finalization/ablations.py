from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Ablation:
    experiment_id: str
    component: str
    enabled: bool
    description: str


ABLATIONS = (
    Ablation(
        "W85_DELTA_STATIC",
        "full_static",
        True,
        "Complete DELTA stack without adaptive learning.",
    ),
    Ablation(
        "W86_FAILURE_LEARNING",
        "failure_learning",
        True,
        "Enable attributed failure learning.",
    ),
    Ablation(
        "W87_REGIME",
        "regime_engine",
        False,
        "Remove explicit regime information.",
    ),
    Ablation(
        "W88_UNCERTAINTY",
        "uncertainty_engine",
        False,
        "Remove uncertainty-aware decision gating.",
    ),
    Ablation(
        "W89_DIGITAL_TWIN",
        "digital_twin",
        False,
        "Remove scenario simulation before decision.",
    ),
    Ablation(
        "W90_MEMORY",
        "experience_memory",
        False,
        "Remove experience-memory retrieval.",
    ),
    Ablation(
        "W91_AGENTS",
        "multi_agent_research",
        False,
        "Remove multi-agent research aggregation.",
    ),
)


def matrix() -> list[dict[str, Any]]:
    return [
        asdict(item)
        for item in ABLATIONS
    ]


def validate_matrix() -> None:
    ids = [
        item.experiment_id
        for item in ABLATIONS
    ]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Duplicate experiment ID."
        )

    if len(ABLATIONS) != 7:
        raise AssertionError(
            "Expected W85-W91 ablation matrix."
        )
