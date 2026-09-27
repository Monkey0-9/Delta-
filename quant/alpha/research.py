"""Alpha Research Engine - Institutional Alpha Generation

Implements the complete alpha research pipeline:
hypothesis → feature → signal → forecast → portfolio
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


class AlphaType(Enum):
    """Types of alpha signals"""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VALUE = "value"
    QUALITY = "quality"
    CARRY = "carry"
    VOLATILITY = "volatility"
    SIZE = "size"
    GROWTH = "growth"
    SENTIMENT = "sentiment"
    MICROSTRUCTURE = "microstructure"
    CROSS_ASSET = "cross_asset"


class AlphaTimeframe(Enum):
    """Timeframes for alpha signals"""
    INTRADAY = "intraday"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class AlphaQuality(Enum):
    """Quality metrics for alpha"""
    IC = "information_coefficient"
    ICIR = "information_coefficient_ir"
    SHARPE = "sharpe_ratio"
    SORTINO = "sortino_ratio"
    TURNOVER = "turnover"
    CAPACITY = "capacity"
    DECAY = "decay"
    ROBUSTNESS = "robustness"


@dataclass(frozen=True, slots=True)
class AlphaHypothesis:
    """An alpha hypothesis to test"""
    name: str
    alpha_type: AlphaType
    description: str
    hypothesis: str
    expected_ic: float
    timeframe: AlphaTimeframe
    universe: List[str]
    parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    hypothesis_id: str = ""
    
    def __post_init__(self):
        """Generate hypothesis ID"""
        import hashlib
        hypothesis_str = f"{self.name}_{self.alpha_type.value}_{self.timeframe.value}"
        hash_obj = hashlib.md5(hypothesis.encode())
        object.__setattr__(self, 'hypothesis_id', hash_obj.hexdigest()[:12])


@dataclass(frozen=True, slots=True)
class AlphaSignal:
    """An alpha signal from a hypothesis"""
    hypothesis_id: str
    symbol: str
    timestamp: datetime
    signal_value: float
    confidence: float
    expected_return: float
    predicted_risk: float
    horizon: str
    features_used: List[str]
    signal_quality: Dict[str, float]
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class AlphaResult:
    """Results from alpha research"""
    hypothesis: AlphaHypothesis
    ic: float
    icir: float
    sharpe: float
    turnover: float
    capacity: float
    decay_rate: float
    robustness_score: float
    sample_size: int
    start_date: datetime
    end_date: datetime
    recommendations: List[str]
    passed_validation: bool


class AlphaResearchEngine:
    """Main alpha research engine for institutional quant research"""
    
    def __init__(self):
        self.hypotheses: Dict[str, AlphaHypothesis] = {}
        self.alpha_history: List[AlphaSignal] = []
        self.research_results: Dict[str, AlphaResult] = {}
        self._register_default_hypotheses()
    
    def _register_default_hypotheses(self):
        """Register default alpha hypotheses"""
        # Momentum hypotheses
        self.register_hypothesis(AlphaHypothesis(
            name="momentum_12d",
            alpha_type=AlphaType.MOMENTUM,
            description="12-month price momentum",
            hypothesis="Stocks with higher 12-month returns will continue to outperform",
            expected_ic=0.05,
            timeframe=AlphaTimeframe.MONTHLY,
            universe=["SPY", "QQQ", "IWM"],
            parameters={"lookback": 12, "holding_period": 1},
        ))
        
        self.register_hypothesis(AlphaHypothesis(
            name="momentum_3d",
            alpha_type=AlphaType.MOMENTUM,
            description="3-day price momentum",
            hypothesis="Short-term momentum persists for 3 days",
            expected_ic=0.02,
            timeframe=AlphaTimeframe.DAILY,
            universe=["SPY", "QQQ", "IWM"],
            parameters={"lookback": 3, "holding_period": 1},
        ))
        
        # Mean reversion hypotheses
        self.register_hypothesis(AlphaHypothesis(
            name="mean_reversion_20d",
            alpha_type=AlphaType.MEAN_REVERSION,
            description="20-day mean reversion",
            hypothesis="Stocks far from 20-day mean will revert",
            expected_ic=0.03,
            timeframe=AlphaTimeframe.DAILY,
            universe=["SPY", "QQQ", "IWM"],
            parameters={"lookback": 20, "z_threshold": 2.0},
        ))
        
        # Value hypotheses
        self.register_hypothesis(AlphaHypothesis(
            name="value_pe_ratio",
            alpha_type=AlphaType.VALUE,
            description="P/E ratio value signal",
            hypothesis="Low P/E stocks outperform high P/E stocks",
            expected_ic=0.04,
            timeframe=AlphaTimeframe.MONTHLY,
            universe=["SPY", "QQQ", "IWM"],
            parameters={"lookback": 1, "holding_period": 3},
        ))
        
        # Quality hypotheses
        self.register_hypothesis(AlphaHypothesis(
            name="quality_roe",
            alpha_type=AlphaType.QUALITY,
            description="Return on equity quality signal",
            hypothesis="High ROE stocks outperform low ROE stocks",
            expected_ic=0.03,
            timeframe=AlphaTimeframe.QUARTERLY,
            universe=["SPY", "QQQ", "IWM"],
            parameters={"lookback": 4, "holding_period": 6},
        ))
    
    def register_hypothesis(self, hypothesis: AlphaHypothesis) -> bool:
        """Register a new alpha hypothesis"""
        self.hypotheses[hypothesis.hypothesis_id] = hypothesis
        return True
    
    def test_hypothesis(
        self,
        hypothesis_id: str,
        features: pd.DataFrame,
        returns: pd.Series,
        start_date: datetime,
        end: datetime,
    ) -> AlphaResult:
        """Test an alpha hypothesis on historical data"""
        if hypothesis_id not in self.hypotheses:
            raise ValueError(f"Hypothesis not found: {hypothesis_id}")
        
        hypothesis = self.hypotheses[hypothesis_id]
        
        # Generate alpha signal from hypothesis
        signal = self._generate_alpha_signal(hypothesis, features)
        
        # Calculate quality metrics
        ic = self._calculate_ic(signal, returns)
        icir = self._calculate_icir(signal, returns)
        sharpe = self._calculate_sharpe(signal, returns)
        turnover = self._calculate_turnover(signal)
        capacity = self._estimate_capacity(signal, returns)
        decay = self._calculate_decay(signal, returns)
        robustness = self._calculate_robustness(signal, returns)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            hypothesis, ic, icir, sharpe, turnover, decay
        )
        
        # Determine if hypothesis passes validation
        passed_validation = self._validate_hypothesis(
            hypothesis, ic, icir, sharpe, turnover, decay
        )
        
        result = AlphaResult(
            hypothesis=hypothesis,
            ic=ic,
            icir=icir,
            sharpe=sharpe,
            turnover=turnover,
            capacity=capacity,
            decay_rate=decay,
            robustness_score=robustness,
            sample_size=len(signal),
            start_date=start_date,
            end_date=end_date,
            recommendations=recommendations,
            passed_validation=passed_validation,
        )
        
        self.research_results[hypothesis_id] = result
        return result
    
    def _generate_alpha_signal(
        self,
        hypothesis: AlphaHypothesis,
        features: pd.DataFrame,
    ) -> pd.Series:
        """Generate alpha signal from hypothesis"""
        if hypothesis.alpha_type == AlphaType.MOMENTUM:
            return self._momentum_signal(hypothesis, features)
        elif hypothesis.alpha_type == AlphaType.MEAN_REVERSION:
            return self._mean_reversion_signal(hypothesis, features)
        elif hypothesis.alpha_type == AlphaType.VALUE:
            return self._value_signal(hypothesis, features)
        elif hypothesis.alpha_type == AlphaType.QUALITY:
            return self._quality_signal(hypothesis, features)
        else:
            raise ValueError(f"Unsupported alpha type: {hypothesis.alpha_type}")
    
    def _momentum_signal(self, hypothesis: AlphaHypothesis, features: pd.DataFrame) -> pd.Series:
        """Generate momentum signal"""
        lookback = hypothesis.parameters.get("lookback", 12)
        
        if f"return_{lookback}d" in features.columns:
            return features[f"return_{lookback}d"]
        elif "close" in features.columns:
            return features["close"].pct_change(lookback)
        else:
            raise ValueError("Cannot calculate momentum - no price data")
    
    def _mean_reversion_signal(self, hypothesis: AlphaHypothesis, features: pd.DataFrame) -> pd.Series:
        """Generate mean reversion signal"""
        lookback = hypothesis.parameters.get("lookback", 20)
        z_threshold = hypothesis.parameters.get("z_threshold", 2.0)
        
        if "close" in features.columns:
            mean_price = features["close"].rolling(lookback).mean()
            std_price = features["close"].rolling(lookback).std()
            z_score = (features["close"] - mean_price) / std_price
            # Negative z-score = buy (oversold), positive = sell (overbought)
            signal = -z_score / z_threshold
            return signal.clip(-1, 1)
        else:
            raise ValueError("Cannot calculate mean reversion - no price data")
    
    def _value_signal(self, hypothesis: AlphaHypothesis, features: pd.DataFrame) -> pd.Series:
        """Generate value signal"""
        if "pe_ratio" in features.columns:
            # Low P/E is good (positive signal)
            signal = -features["pe_ratio"].rank(pct=True)
            return signal
        elif "close" in features.columns and "earnings" in features.columns:
            # Simple P/E approximation
            pe_ratio = features["close"] / features["earnings"]
            signal = -pe_ratio.rank(pct=True)
            return signal
        else:
            raise ValueError("Cannot calculate value signal - no fundamental data")
    
    def _quality_signal(self, hypothesis: AlphaHypothesis, features: pd.DataFrame) -> pd.Series:
        """Generate quality signal"""
        if "roe" in features.columns:
            # High ROE is good (positive signal)
            signal = features["roe"].rank(pct=True)
            return signal
        elif "close" in features.columns and "earnings" in features.columns:
            # Simple ROE approximation
            roe = features["earnings"] / features["close"]
            signal = roe.rank(pct=True)
            return signal
        else:
            raise ValueError("Cannot calculate quality signal - no fundamental data")
    
    def _calculate_ic(self, signal: pd.Series, returns: pd.Series) -> float:
        """Calculate Information Coefficient"""
        # Align signal and returns
        aligned = pd.concat([signal, returns], axis=1).dropna()
        if len(aligned) < 2:
            return 0.0
        
        return aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
    
    def _calculate_icir(self, signal: pd.Series, returns: pd.Series) -> float:
        """Calculate Information Coefficient with Information Ratio"""
        # IC with rolling window
        aligned = pd.concat([signal, returns], axis=1).dropna()
        if len(aligned) < 30:
            return 0.0
        
        rolling_ic = aligned.iloc[:, 0].rolling(20).corr(aligned.iloc[:, 1])
        icir = rolling_ic.mean() / rolling_ic.std() if rolling_ic.std() > 0 else 0.0
        return icir
    
    def _calculate_sharpe(self, signal: pd.Series, returns: pd.Series) -> float:
        """Calculate Sharpe ratio"""
        aligned = pd.concat([signal, returns], axis=1).dropna()
        if len(aligned) < 2:
            return 0.0
        
        # Simulated portfolio based on signal
        portfolio_returns = aligned.iloc[:, 0] * aligned.iloc[:, 1]
        sharpe = portfolio_returns.mean() / portfolio_returns.std() if portfolio_returns.std() > 0 else 0.0
        return sharpe * np.sqrt(252)  # Annualized
    
    def _calculate_turnover(self, signal: pd.Series) -> float:
        """Calculate portfolio turnover"""
        # Change in signal direction
        signal_direction = signal.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        turnover = signal_direction.diff().abs().mean()
        return turnover
    
    def _estimate_capacity(self, signal: pd.Series, returns: pd.Series) -> float:
        """Estimate trading capacity"""
        # Simplified capacity estimation
        avg_daily_volume = returns.abs().mean()
        turnover = self._calculate_turnover(signal)
        capacity = avg_daily_volume / (turnover + 0.01)  # Avoid division by zero
        return capacity
    
    def _calculate_decay(self, signal: pd.Series, returns: pd.Series) -> float:
        """Calculate signal decay rate"""
        # Half-life of signal correlation
        aligned = pd.concat([signal, returns], axis=1).dropna()
        if len(aligned) < 30:
            return 0.0
        
        rolling_ic = aligned.iloc[:, 0].rolling(10).corr(aligned.iloc[:, 1])
        decay = rolling_ic.pct_change().mean()
        return decay
    
    def _calculate_robustness(self, signal: pd.Series, returns: pd.Series) -> float:
        """Calculate robustness score"""
        # Consistency across time periods
        aligned = pd.concat([signal, returns], axis=1).dropna()
        if len(aligned) < 60:
            return 0.0
        
        # Split into periods and calculate IC in each
        mid_point = len(aligned) // 2
        ic1 = aligned.iloc[:mid_point, 0].corr(aligned.iloc[:mid_point, 1])
        ic2 = aligned.iloc[mid_point:, 0].corr(aligned.iloc[mid_point:, 1])
        
        robustness = 1 - abs(ic1 - ic2) / 2  # Closer to 1 means more robust
        return robustness
    
    def _generate_recommendations(
        self,
        hypothesis: AlphaHypothesis,
        ic: float,
        icir: float,
        sharpe: float,
        turnover: float,
        decay: float,
    ) -> List[str]:
        """Generate recommendations based on metrics"""
        recommendations = []
        
        if ic > hypothesis.expected_ic:
            recommendations.append("IC exceeds expectations - strong candidate")
        elif ic > hypothesis.expected_ic * 0.8:
            recommendations.append("IC meets expectations - acceptable candidate")
        else:
            recommendations.append("IC below expectations - reconsider hypothesis")
        
        if icir > 0.5:
            recommendations.append("Good ICIR - signal is consistent")
        else:
            recommendations.append("Poor ICIR - signal is noisy")
        
        if sharpe > 1.0:
            recommendations.append("Excellent risk-adjusted returns")
        elif sharpe > 0.5:
            recommendations.append("Good risk-adjusted returns")
        else:
            recommendations.append("Poor risk-adjusted returns")
        
        if turnover > 0.5:
            recommendations.append("High turnover - may impact implementation")
        elif turnover > 0.3:
            recommendations.append("Moderate turnover - implementable")
        else:
            recommendations.append("Low turnover - easy to implement")
        
        if decay < -0.1:
            recommendations.append("Rapid signal decay - short holding period only")
        elif decay < -0.05:
            recommendations.append("Moderate signal decay - monitor closely")
        else:
            recommendations.append("Slow signal decay - suitable for longer holding")
        
        return recommendations
    
    def _validate_hypothesis(
        self,
        hypothesis: AlphaHypothesis,
        ic: float,
        icir: float,
        sharpe: float,
        turnover: float,
        decay: float,
    ) -> bool:
        """Validate if hypothesis meets criteria"""
        # Minimum IC threshold
        if ic < hypothesis.expected_ic * 0.5:
            return False
        
        # Minimum ICIR threshold
        if icir < 0.3:
            return False
        
        # Minimum Sharpe threshold
        if sharpe < 0.5:
            return False
        
        # Maximum turnover threshold
        if turnover > 0.8:
            return False
        
        # Maximum decay threshold
        if decay < -0.3:
            return False
        
        return True
    
    def get_hypothesis(self, hypothesis_id: str) -> Optional[AlphaHypothesis]:
        """Get a hypothesis by ID"""
        return self.hypotheses.get(hypothesis_id)
    
    def list_hypotheses(self, alpha_type: AlphaType = None) -> List[AlphaHypothesis]:
        """List hypotheses, optionally filtered by type"""
        if alpha_type is None:
            return list(self.hypotheses.values())
        else:
            return [h for h in self.hypotheses.values() if h.alpha_type == alpha_type]
    
    def get_research_result(self, hypothesis_id: str) -> Optional[AlphaResult]:
        """Get research result for a hypothesis"""
        return self.research_results.get(hypothesis_id)
    
    def get_alpha_statistics(self) -> Dict[str, Any]:
        """Get statistics about alpha research"""
        return {
            "total_hypotheses": len(self.hypotheses),
            "tested_hypotheses": len(self.research_results),
            "passed_hypotheses": sum(1 for r in self.research_results.values() if r.passed_validation),
            "alpha_types": {t.value: len([h for h in self.hypotheses.values() if h.alpha_type == t]) 
                         for t in AlphaType},
        }
