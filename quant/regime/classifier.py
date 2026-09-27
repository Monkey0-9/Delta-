"""Macro Regime Classifier for market environment detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4
import numpy as np


class RegimeType(StrEnum):
    """Types of market regimes."""
    LOW_VOL_BULL = "low_vol_bull"
    HIGH_VOL_MEAN_REVERSION = "high_vol_mean_reversion"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    HIGH_VOL_BULL = "high_vol_bull"
    LOW_VOL_BEAR = "low_vol_bear"
    CRASH = "crash"


@dataclass(frozen=True, slots=True)
class Regime:
    """Market regime classification."""
    regime_id: UUID = field(default_factory=uuid4)
    regime_type: RegimeType = RegimeType.LOW_VOL_BULL
    confidence: float = 0.0  # 0.0 to 1.0
    start_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: datetime | None = None
    
    # Regime characteristics
    volatility_level: str = "medium"  # low, medium, high
    liquidity_level: str = "normal"  # normal, stressed, crisis
    trend_direction: str = "neutral"  # bullish, bearish, neutral
    
    # Additional metadata
    features: dict[str, float] = field(default_factory=dict)
    transition_probabilities: dict[RegimeType, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegimeTransition:
    """Transition between regimes."""
    from_regime: RegimeType
    to_regime: RegimeType
    probability: float = 0.0
    transition_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RegimeClassifier:
    """
    Multi-regime classifier for market environment detection.
    
    Uses Hidden Markov Models and spectral filtering to identify
    regime transitions and classify current market state.
    """
    
    def __init__(self) -> None:
        self._current_regime: Regime | None = None
        self._regime_history: list[Regime] = []
        self._transition_matrix: dict[RegimeType, dict[RegimeType, float]] = {}
        self._initial_probabilities: dict[RegimeType, float] = {}
    
    def classify(
        self,
        features: dict[str, float],
        timestamp: datetime | None = None
    ) -> Regime:
        """
        Classify current market regime based on features.
        
        Features should include:
        - volatility: Current market volatility
        - liquidity: Market liquidity measure
        - trend: Price trend indicator
        - credit_spread: Credit spread indicator
        - vix: VIX level
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        
        # Simple rule-based classification (would use HMM in production)
        volatility = features.get("volatility", 0.02)
        liquidity = features.get("liquidity", 1.0)
        trend = features.get("trend", 0.0)
        vix = features.get("vix", 20.0)
        
        # Determine regime type
        if vix > 40 or liquidity < 0.5:
            regime_type = RegimeType.LIQUIDITY_CRISIS
            volatility_level = "high"
            liquidity_level = "crisis"
        elif volatility > 0.04 and trend < -0.05:
            regime_type = RegimeType.CRASH
            volatility_level = "high"
            liquidity_level = "stressed"
        elif volatility > 0.03:
            if trend > 0:
                regime_type = RegimeType.HIGH_VOL_BULL
                volatility_level = "high"
                liquidity_level = "normal"
            else:
                regime_type = RegimeType.HIGH_VOL_MEAN_REVERSION
                volatility_level = "high"
                liquidity_level = "normal"
        elif volatility < 0.015:
            if trend > 0:
                regime_type = RegimeType.LOW_VOL_BULL
                volatility_level = "low"
                liquidity_level = "normal"
            else:
                regime_type = RegimeType.LOW_VOL_BEAR
                volatility_level = "low"
                liquidity_level = "normal"
        else:
            regime_type = RegimeType.HIGH_VOL_MEAN_REVERSION
            volatility_level = "medium"
            liquidity_level = "normal"
        
        # Determine trend direction
        if trend > 0.02:
            trend_direction = "bullish"
        elif trend < -0.02:
            trend_direction = "bearish"
        else:
            trend_direction = "neutral"
        
        # Calculate confidence (simplified)
        confidence = min(1.0, max(0.0, 1.0 - abs(trend) * 5))
        
        # Create regime
        regime = Regime(
            regime_type=regime_type,
            confidence=confidence,
            start_date=timestamp,
            volatility_level=volatility_level,
            liquidity_level=liquidity_level,
            trend_direction=trend_direction,
            features=features,
            transition_probabilities=self._get_transition_probabilities(regime_type),
        )
        
        # Update state
        self._update_regime(regime)
        
        return regime
    
    def _update_regime(self, new_regime: Regime) -> None:
        """Update current regime and track transitions."""
        if self._current_regime:
            # End previous regime
            self._current_regime = Regime(
                regime_id=self._current_regime.regime_id,
                regime_type=self._current_regime.regime_type,
                confidence=self._current_regime.confidence,
                start_date=self._current_regime.start_date,
                end_date=new_regime.start_date,
                volatility_level=self._current_regime.volatility_level,
                liquidity_level=self._current_regime.liquidity_level,
                trend_direction=self._current_regime.trend_direction,
                features=self._current_regime.features,
                transition_probabilities=self._current_regime.transition_probabilities,
            )
            self._regime_history.append(self._current_regime)
        
        self._current_regime = new_regime
    
    def _get_transition_probabilities(self, current_type: RegimeType) -> dict[RegimeType, float]:
        """Get transition probabilities for current regime."""
        # Simplified transition matrix (would be learned from data)
        defaults = {
            RegimeType.LOW_VOL_BULL: {
                RegimeType.LOW_VOL_BULL: 0.7,
                RegimeType.HIGH_VOL_BULL: 0.2,
                RegimeType.LOW_VOL_BEAR: 0.1,
            },
            RegimeType.HIGH_VOL_BULL: {
                RegimeType.HIGH_VOL_BULL: 0.5,
                RegimeType.LOW_VOL_BULL: 0.3,
                RegimeType.HIGH_VOL_MEAN_REVERSION: 0.2,
            },
            RegimeType.HIGH_VOL_MEAN_REVERSION: {
                RegimeType.HIGH_VOL_MEAN_REVERSION: 0.6,
                RegimeType.LOW_VOL_BULL: 0.2,
                RegimeType.LOW_VOL_BEAR: 0.2,
            },
            RegimeType.LIQUIDITY_CRISIS: {
                RegimeType.LIQUIDITY_CRISIS: 0.4,
                RegimeType.HIGH_VOL_MEAN_REVERSION: 0.4,
                RegimeType.LOW_VOL_BULL: 0.2,
            },
            RegimeType.CRASH: {
                RegimeType.CRASH: 0.3,
                RegimeType.LIQUIDITY_CRISIS: 0.4,
                RegimeType.HIGH_VOL_MEAN_REVERSION: 0.3,
            },
            RegimeType.LOW_VOL_BEAR: {
                RegimeType.LOW_VOL_BEAR: 0.6,
                RegimeType.LOW_VOL_BULL: 0.3,
                RegimeType.HIGH_VOL_MEAN_REVERSION: 0.1,
            },
        }
        
        return defaults.get(current_type, {})
    
    def get_current_regime(self) -> Regime | None:
        """Get current market regime."""
        return self._current_regime
    
    def get_regime_history(self) -> list[Regime]:
        """Get historical regime classifications."""
        return self._regime_history.copy()
    
    def get_transition_matrix(self) -> dict[RegimeType, dict[RegimeType, float]]:
        """Get current transition probability matrix."""
        return self._transition_matrix.copy()
