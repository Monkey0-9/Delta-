"""Alpha Research Engine - W95 Foundation

Implements the complete alpha research pipeline:
hypothesis → feature → signal → forecast → portfolio
"""

from .research import AlphaResearchEngine, AlphaHypothesis, AlphaSignal
from .forecasting import ForecastEngine, ModelEnsemble
from .regime import RegimeDetector, RegimeModel, MarketRegime

__all__ = [
    "AlphaResearchEngine",
    "AlphaHypothesis", 
    "AlphaSignal",
    "ForecastEngine",
    "ModelEnsemble",
    "RegimeDetector",
    "RegimeModel",
    "MarketRegime",
]
