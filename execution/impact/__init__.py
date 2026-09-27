"""Non-Linear Market Impact Engine.

W100: Calibrates transient square-root impact models (γσ√(V/ADV))
using proprietary order-fill data for realistic execution simulation.
"""

from .model import MarketImpactModel, AlmgrenChrissModel, KyleLambdaModel
from .calibrator import ImpactCalibrator, CalibrationData

__all__ = [
    "MarketImpactModel",
    "AlmgrenChrissModel",
    "KyleLambdaModel",
    "ImpactCalibrator",
    "CalibrationData",
]
