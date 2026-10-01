"""Model zoo for DELTA OS: registry, factory, and evaluation."""

from models.model_zoo.registry import ModelRegistry
from models.model_zoo.factory import make_model
from models.model_zoo.evaluation import (
    FINANCE_PROTOCOLS,
    require_finance_protocol,
    score_finance_model,
    cross_val_score_model,
    compare_models,
)

__all__ = [
    "ModelRegistry",
    "make_model",
    "FINANCE_PROTOCOLS",
    "require_finance_protocol",
    "score_finance_model",
    "cross_val_score_model",
    "compare_models",
]
