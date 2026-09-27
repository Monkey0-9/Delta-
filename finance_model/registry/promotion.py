from __future__ import annotations

from enum import StrEnum

from .artifact import ModelArtifact


class ModelStatus(StrEnum):
    EXPERIMENTAL = "EXPERIMENTAL"
    CANDIDATE = "CANDIDATE"
    SHADOW = "SHADOW"
    CERTIFIED = "CERTIFIED"
    DEPLOYED = "DEPLOYED"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


class PromotionError(RuntimeError):
    pass


def promote(
    artifact: ModelArtifact,
    *,
    validation_passed: bool,
    protected_failures_passed: bool,
    temporal_integrity_passed: bool,
) -> ModelArtifact:
    if not validation_passed:
        raise PromotionError(
            "validation gate failed"
        )

    if not protected_failures_passed:
        raise PromotionError(
            "protected-failure gate failed"
        )

    if not temporal_integrity_passed:
        raise PromotionError(
            "temporal-integrity gate failed"
        )

    return ModelArtifact(
        model_id=artifact.model_id,
        version=artifact.version,
        base_model=artifact.base_model,
        dataset_hash=artifact.dataset_hash,
        code_version=artifact.code_version,
        created_at=artifact.created_at,
        task=artifact.task,
        training_config_hash=artifact.training_config_hash,
        evaluation_hash=artifact.evaluation_hash,
        status=ModelStatus.CANDIDATE,
    )