"""Regime Detection Engine - Market Regime Identification

Implements regime detection for volatility, correlation, liquidity, and macro regimes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable
import pandas as pd
import numpy as np
from scipy import stats
from abc import ABC, abstractmethod
import json


class RegimeType(Enum):
    """Types of market regimes"""
    VOLATILITY = "volatility"
    CORRELATION = "correlation"
    LIQUIDITY = "liquidity"
    MACRO = "macro"
    RISK_ON_RISK_OFF = "risk_on_risk_off"
    STRUCTURAL_BREAK = "structural_break"


class RegimeState(Enum):
    """Regime states"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"
    BULL = "bull"
    BEAR = "bear"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"


@dataclass(frozen=True, slots=True)
class MarketRegime:
    """Current market regime"""
    regime_type: RegimeType
    state: RegimeState
    timestamp: datetime
    confidence: float
    value: float
    duration: int  # How long this regime has persisted
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class RegimeTransition:
    """A transition between regimes"""
    from_regime: MarketRegime
    to_regime: MarketRegime
    transition_timestamp: datetime
    transition_confidence: float
    metadata: Optional[Dict[str, Any]] = None


class RegimeDetector(ABC):
    """Abstract base class for regime detectors"""
    
    def __init__(self, name: str, lookback_window: int = 20):
        self.name = name
        self.lookback_window = lookback_window
        self.current_regime: Optional[MarketRegime] = None
        self.regime_history: List[MarketRegime] = []
    
    @abstractmethod
    def detect_regime(self, data: pd.DataFrame, timestamp: datetime) -> MarketRegime:
        """Detect current regime from data"""
        pass
    
    def update_regime(self, regime: MarketRegime) -> None:
        """Update current regime and track history"""
        self.current_regime = regime
        self.regime_history.append(regime)


class VolatilityRegimeDetector(RegimeDetector):
    """Detect volatility regimes (low, normal, high, extreme)"""
    
    def __init__(self, lookback_window: int = 20, vix_thresholds: Tuple[float, float] = (15, 30)):
        super().__init__("volatility_regime", lookback_window)
        self.vix_thresholds = vix_thresholds  # (low_vix, high_vix)
    
    def detect_regime(self, data: pd.DataFrame, timestamp: datetime) -> MarketRegime:
        """Detect volatility regime"""
        if "close" in data.columns:
            # Calculate realized volatility
            returns = data["close"].pct_change().dropna()
            volatility = returns.rolling(self.lookback_window).std().iloc[-1] * np.sqrt(252)
        elif "vix" in data.columns:
            volatility = data["vix"].iloc[-1]
        else:
            volatility = 0.0
        
        # Determine regime state
        low_threshold, high_threshold = self.vix_thresholds
        
        if volatility < low_threshold:
            state = RegimeState.LOW
        elif volatility < high_threshold:
            state = RegimeState.NORMAL
        elif volatility < high_threshold * 1.5:
            state = RegimeState.HIGH
        else:
            state = RegimeState.EXTREME
        
        # Calculate confidence based on how far from thresholds
        if state == RegimeState.LOW:
            confidence = 1.0 - (volatility / low_threshold)
        elif state == RegimeState.EXTREME:
            confidence = min((volatility - high_threshold * 1.5) / (high_threshold * 0.5), 1.0)
        else:
            confidence = 0.7
        
        # Calculate duration
        duration = 1
        if self.regime_history:
            last_regime = self.regime_history[-1]
            if last_regime.state == state:
                duration = last_regime.duration + 1
        
        regime = MarketRegime(
            regime_type=RegimeType.VOLATILITY,
            state=state,
            timestamp=timestamp,
            confidence=confidence,
            value=float(volatility),
            duration=duration,
            metadata={"volatility": float(volatility)},
        )
        
        self.update_regime(regime)
        return regime


class CorrelationRegimeDetector(RegimeDetector):
    """Detect correlation regimes (dispersion vs concentration)"""
    
    def __init__(self, lookback_window: int = 20, correlation_threshold: float = 0.7):
        super().__init__("correlation_regime", lookback_window)
        self.correlation_threshold = correlation_threshold
    
    def detect_regime(self, data: pd.DataFrame, timestamp: datetime) -> MarketRegime:
        """Detect correlation regime"""
        # If we have multiple assets, calculate pairwise correlations
        if len(data.columns) > 1:
            # Use close prices if available
            close_cols = [col for col in data.columns if "close" in col.lower()]
            if close_cols:
                correlation_matrix = data[close_cols].corr()
                avg_correlation = correlation_matrix.values[np.triu_indices_from(correlation_matrix, k=1)].mean()
            else:
                avg_correlation = 0.0
        else:
            avg_correlation = 0.0
        
        # Determine regime state
        if avg_correlation < 0.3:
            state = RegimeState.LOW  # High dispersion
        elif avg_correlation < self.correlation_threshold:
            state = RegimeState.NORMAL
        else:
            state = RegimeState.HIGH  # High correlation (concentration)
        
        # Confidence based on correlation level
        confidence = min(abs(avg_correlation - 0.5) * 2, 1.0)
        
        # Calculate duration
        duration = 1
        if self.regime_history:
            last_regime = self.regime_history[-1]
            if last_regime.state == state:
                duration = last_regime.duration + 1
        
        regime = MarketRegime(
            regime_type=RegimeType.CORRELATION,
            state=state,
            timestamp=timestamp,
            confidence=confidence,
            value=float(avg_correlation),
            duration=duration,
            metadata={"average_correlation": float(avg_correlation)},
        )
        
        self.update_regime(regime)
        return regime


class RiskOnRiskOffDetector(RegimeDetector):
    """Detect risk-on vs risk-off regimes"""
    
    def __init__(self, lookback_window: int = 20):
        super().__init__("risk_on_risk_off", lookback_window)
    
    def detect_regime(self, data: pd.DataFrame, timestamp: datetime) -> MarketRegime:
        """Detect risk-on vs risk-off regime"""
        # Use SPY and TLT as proxies
        spy_return = 0.0
        tlt_return = 0.0
        
        if "SPY" in data.columns:
            spy_return = data["SPY"].pct_change().iloc[-1]
        elif "close" in data.columns:
            spy_return = data["close"].pct_change().iloc[-1]
        
        if "TLT" in data.columns:
            tlt_return = data["TLT"].pct_change().iloc[-1]
        
        # Risk-on: stocks up, bonds down
        # Risk-off: stocks down, bonds up
        risk_on_score = spy_return - tlt_return
        
        if risk_on_score > 0.01:
            state = RegimeState.RISK_ON
        elif risk_on_score < -0.01:
            state = RegimeState.RISK_OFF
        else:
            state = RegimeState.NORMAL
        
        confidence = min(abs(risk_on_score) * 50, 1.0)
        
        # Calculate duration
        duration = 1
        if self.regime_history:
            last_regime = self.regime_history[-1]
            if last_regime.state == state:
                duration = last_regime.duration + 1
        
        regime = MarketRegime(
            regime_type=RegimeType.RISK_ON_RISK_OFF,
            state=state,
            timestamp=timestamp,
            confidence=confidence,
            value=float(risk_on_score),
            duration=duration,
            metadata={"risk_on_score": float(risk_on_score)},
        )
        
        self.update_regime(regime)
        return regime


class RegimeModel:
    """Hierarchical regime model combining multiple detectors"""
    
    def __init__(self):
        self.detectors: List[RegimeDetector] = []
        self.current_regimes: Dict[RegimeType, MarketRegime] = {}
        self.transition_history: List[RegimeTransition] = []
        self._initialize_default_detectors()
    
    def _initialize_default_detectors(self):
        """Initialize default regime detectors"""
        self.detectors.append(VolatilityRegimeDetector(lookback_window=20))
        self.detectors.append(CorrelationRegimeDetector(lookback_window=20))
        self.detectors.append(RiskOnRiskOffDetector(lookback_window=20))
    
    def add_detector(self, detector: RegimeDetector) -> None:
        """Add a regime detector"""
        self.detectors.append(detector)
    
    def detect_all_regimes(
        self,
        data: pd.DataFrame,
        timestamp: datetime,
    ) -> Dict[RegimeType, MarketRegime]:
        """Detect all regimes using registered detectors"""
        previous_regimes = self.current_regimes.copy()
        
        for detector in self.detectors:
            try:
                regime = detector.detect_regime(data, timestamp)
                self.current_regimes[regime.regime_type] = regime
                
                # Track transitions
                if regime.regime_type in previous_regimes:
                    prev_regime = previous_regimes[regime.regime_type]
                    if prev_regime.state != regime.state:
                        transition = RegimeTransition(
                            from_regime=prev_regime,
                            to_regime=regime,
                            transition_timestamp=timestamp,
                            transition_confidence=min(prev_regime.confidence, regime.confidence),
                        )
                        self.transition_history.append(transition)
            except Exception as e:
                print(f"Error in detector {detector.name}: {e}")
        
        return self.current_regimes
    
    def get_current_regime_summary(self) -> Dict[str, Any]:
        """Get summary of current regimes"""
        summary = {}
        
        for regime_type, regime in self.current_regimes.items():
            summary[regime_type.value] = {
                "state": regime.state.value,
                "confidence": regime.confidence,
                "value": regime.value,
                "duration": regime.duration,
            }
        
        return summary
    
    def get_regime_transitions(
        self,
        regime_type: RegimeType = None,
        limit: int = 10,
    ) -> List[RegimeTransition]:
        """Get recent regime transitions"""
        transitions = self.transition_history
        
        if regime_type:
            transitions = [t for t in transitions if t.from_regime.regime_type == regime_type]
        
        return transitions[-limit:]
    
    def get_regime_statistics(self) -> Dict[str, Any]:
        """Get statistics about regime detection"""
        if not self.current_regimes:
            return {}
        
        total_transitions = len(self.transition_history)
        avg_duration = np.mean([r.duration for r in self.current_regimes.values()])
        
        # Count transitions by type
        transition_counts = {}
        for transition in self.transition_history:
            regime_type = transition.from_regime.regime_type.value
            transition_counts[regime_type] = transition_counts.get(regime_type, 0) + 1
        
        return {
            "total_transitions": total_transitions,
            "average_regime_duration": float(avg_duration),
            "transition_counts": transition_counts,
            "active_detectors": len(self.detectors),
        }
