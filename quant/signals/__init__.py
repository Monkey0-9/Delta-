from __future__ import annotations

from quant.signals.signal_library import (
    SignalCategory,
    SignalHorizon,
    SignalMetadata,
    SignalResult,
    BaseSignal,
    SimpleMomentumSignal,
    EWMA_MomentumSignal,
    ZScoreSignal,
    RSISignal,
    MovingAverageCrossoverSignal,
    RollingVolatilitySignal,
    SignalLibrary,
    get_signal_library,
    rsi,
    momentum,
)
from quant.signals.orthogonal_gate import (
    MIN_RESIDUAL_RATIO,
    build_factor_basis,
    orthogonalize_alpha,
)

__all__ = [
    "SignalCategory",
    "SignalHorizon",
    "SignalMetadata",
    "SignalResult",
    "BaseSignal",
    "SimpleMomentumSignal",
    "EWMA_MomentumSignal",
    "ZScoreSignal",
    "RSISignal",
    "MovingAverageCrossoverSignal",
    "RollingVolatilitySignal",
    "SignalLibrary",
    "get_signal_library",
    "rsi",
    "momentum",
    "orthogonalize_alpha",
    "build_factor_basis",
    "MIN_RESIDUAL_RATIO",
]
