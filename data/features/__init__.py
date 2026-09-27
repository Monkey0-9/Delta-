"""Versioned Feature Store & Neutralization Engine.

W98: Implements rolling Winsorization, cross-sectional Z-scoring,
and analytical factor neutralization to eliminate data leakage
and ensure signal orthogonality.
"""

from .store import FeatureStore, FeatureVersion, FeatureKey
from .neutralization import (
    FeatureNeutralizer,
    WinsorizationMethod,
    NeutralizationMethod,
    FactorNeutralizer
)
from .orthogonalization import (
    OrthogonalizationEngine,
    OrthogonalizationMethod
)

__all__ = [
    "FeatureStore",
    "FeatureVersion",
    "FeatureKey",
    "FeatureNeutralizer",
    "WinsorizationMethod",
    "NeutralizationMethod",
    "FactorNeutralizer",
    "OrthogonalizationEngine",
    "OrthogonalizationMethod",
]
