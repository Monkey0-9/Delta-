"""Signal Generator - Alpha Signal Production

Transforms features into predictive signals for trading decisions.
This is the final piece that replaces demo_candidates() with real signals.
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


class SignalType(Enum):
    """Types of trading signals"""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"
    REDUCE = "reduce"
    INCREASE = "increase"
    REBALANCE = "rebalance"


class SignalStrength(Enum):
    """Strength/confidence of signals"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass(frozen=True, slots=True)
class Signal:
    """A trading signal for a specific symbol"""
    symbol: str
    timestamp: datetime
    signal_type: SignalType
    strength: SignalStrength
    expected_return: float
    confidence: float
    horizon: str  # "1d", "1w", "1m", etc.
    features_used: List[str]
    model_version: str
    signal_id: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Generate signal ID if not provided"""
        if not self.signal_id:
            signal_str = f"{self.symbol}_{self.timestamp.isoformat()}_{self.signal_type.value}"
            import hashlib
            hash_obj = hashlib.md5(signal_str.encode())
            object.__setattr__(self, 'signal_id', hash_obj.hexdigest()[:12])


@dataclass(frozen=True, slots=True)
class SignalPortfolio:
    """Portfolio of signals across multiple symbols"""
    timestamp: datetime
    signals: List[Signal]
    total_expected_return: float
    portfolio_risk: float
    sharpe_ratio: float
    turnover: float
    metadata: Optional[Dict[str, Any]] = None


class SignalModel(ABC):
    """Abstract base class for signal models"""
    
    def __init__(self, name: str, version: str = "1.0"):
        self.name = name
        self.version = version
        self.is_fitted = False
    
    @abstractmethod
    def fit(self, features: pd.DataFrame, returns: pd.Series) -> None:
        """Train the model on historical data"""
        pass
    
    @abstractmethod
    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Generate predictions from features"""
        pass
    
    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance"""
        pass


class LinearSignalModel(SignalModel):
    """Linear regression-based signal model"""
    
    def __init__(self, l2_penalty: float = 0.01):
        super().__init__("linear_signal", "1.0")
        self.l2_penalty = l2_penalty
        self.coefficients: Optional[Dict[str, float]] = None
        self.intercept: float = 0.0
        self.feature_importance: Dict[str, float] = {}
    
    def fit(self, features: pd.DataFrame, returns: pd.Series) -> None:
        """Fit linear regression with L2 regularization"""
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import StandardScaler
        
        # Handle missing values
        features_clean = features.fillna(0)
        returns_clean = returns.fillna(0)
        
        # Standardize features
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features_clean)
        
        # Fit Ridge regression
        model = Ridge(alpha=self.l2_penalty)
        model.fit(features_scaled, returns_clean)
        
        # Store coefficients
        self.coefficients = dict(zip(features.columns, model.coef_))
        self.intercept = model.intercept_
        
        # Calculate feature importance (absolute coefficient * std)
        feature_stds = features_clean.std()
        for feature, coef in self.coefficients.items():
            self.feature_importance[feature] = abs(coef * feature_stds.get(feature, 1.0))
        
        # Normalize importance
        total_importance = sum(self.feature_importance.values())
        if total_importance > 0:
            self.feature_importance = {
                k: v / total_importance 
                for k, v in self.feature_importance.items()
            }
        
        self.is_fitted = True
    
    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Generate predictions"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        features_clean = features.fillna(0)
        
        prediction = pd.Series(0.0, index=features.index)
        
        for feature, coef in self.coefficients.items():
            if feature in features_clean.columns:
                prediction += coef * features_clean[feature]
        
        prediction += self.intercept
        
        return prediction
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance"""
        return self.feature_importance


class RankSignalModel(SignalModel):
    """Rank-based signal model (cross-sectional)"""
    
    def __init__(self, lookback_period: int = 20):
        super().__init__("rank_signal", "1.0")
        self.lookback_period = lookback_period
        self.feature_weights: Dict[str, float] = {}
        self.feature_importance: Dict[str, float] = {}
    
    def fit(self, features: pd.DataFrame, returns: pd.Series) -> None:
        """Fit rank model using IC (Information Coefficient)"""
        # Calculate IC for each feature
        feature_ics = {}
        
        for feature in features.columns:
            if feature in features.columns:
                # Rank feature and calculate IC with returns
                feature_rank = features[feature].rolling(self.lookback_period).rank(pct=True)
                ic = feature_rank.rolling(self.lookback_period).corr(returns.rolling(self.lookback_period))
                feature_ics[feature] = ic.mean()
        
        # Use IC as feature weights
        total_ic = sum(abs(ic) for ic in feature_ics.values())
        if total_ic > 0:
            self.feature_weights = {
                feature: abs(ic) / total_ic 
                for feature, ic in feature_ics.items()
            }
            self.feature_importance = self.feature_weights.copy()
        else:
            # Equal weights if no IC
            num_features = len(features.columns)
            self.feature_weights = {f: 1.0/num_features for f in features.columns}
            self.feature_importance = self.feature_weights.copy()
        
        self.is_fitted = True
    
    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Generate rank-based predictions"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        features_clean = features.fillna(0)
        
        # Calculate weighted rank score
        score = pd.Series(0.0, index=features.index)
        
        for feature, weight in self.feature_weights.items():
            if feature in features_clean.columns:
                # Cross-sectional rank at each time point
                feature_rank = features_clean[feature].rank(pct=True)
                score += weight * feature_rank
        
        return score
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance"""
        return self.feature_importance


class MomentumSignalModel(SignalModel):
    """Simple momentum-based signal model"""
    
    def __init__(self, momentum_period: int = 12):
        super().__init__("momentum_signal", "1.0")
        self.momentum_period = momentum_period
        self.feature_importance: Dict[str, float] = {}
    
    def fit(self, features: pd.DataFrame, returns: pd.Series) -> None:
        """Momentum model doesn't need fitting"""
        self.feature_importance = {
            f"momentum_{self.momentum_period}d": 1.0
        }
        self.is_fitted = True
    
    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Generate momentum predictions"""
        momentum_feature = f"momentum_{self.momentum_period}d"
        
        if momentum_feature in features.columns:
            return features[momentum_feature]
        else:
            # Calculate momentum if not in features
            if 'close' in features.columns:
                momentum = features['close'].pct_change(self.momentum_period)
                return momentum
            else:
                raise ValueError("Cannot calculate momentum - no close price or momentum feature")
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance"""
        return self.feature_importance


class MeanReversionSignalModel(SignalModel):
    """Mean reversion signal model"""
    
    def __init__(self, lookback_period: int = 20, z_threshold: float = 2.0):
        super().__init__("mean_reversion_signal", "1.0")
        self.lookback_period = lookback_period
        self.z_threshold = z_threshold
        self.feature_importance: Dict[str, float] = {}
    
    def fit(self, features: pd.DataFrame, returns: pd.Series) -> None:
        """Mean reversion model doesn't need fitting"""
        self.feature_importance = {
            f"mean_reversion_{self.lookback_period}d": 1.0
        }
        self.is_fitted = True
    
    def predict(self, features: pd.DataFrame) -> pd.Series:
        """Generate mean reversion predictions"""
        if 'close' in features.columns:
            # Calculate z-score of price relative to moving average
            mean_price = features['close'].rolling(self.lookback_period).mean()
            std_price = features['close'].rolling(self.lookback_period).std()
            z_score = (features['close'] - mean_price) / std_price
            
            # Signal: negative z-score = buy (oversold), positive = sell (overbought)
            signal = -z_score / self.z_threshold
            return signal.clip(-1, 1)
        else:
            raise ValueError("Cannot calculate mean reversion - no close price")
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance"""
        return self.feature_importance


class SignalGenerator:
    """Main signal generator combining models and features"""
    
    def __init__(self):
        self.models: Dict[str, SignalModel] = {}
        self.active_model: Optional[str] = None
        self.signal_history: List[Signal] = []
        self._register_default_models()
    
    def _register_default_models(self):
        """Register default signal models"""
        self.register_model("linear", LinearSignalModel())
        self.register_model("rank", RankSignalModel())
        self.register_model("momentum", MomentumSignalModel(momentum_period=12))
        self.register_model("mean_reversion", MeanReversionSignalModel(lookback_period=20))
        
        # Set default active model
        self.active_model = "rank"
    
    def register_model(self, name: str, model: SignalModel) -> bool:
        """Register a new signal model"""
        self.models[name] = model
        return True
    
    def set_active_model(self, model_name: str) -> bool:
        """Set the active model for signal generation"""
        if model_name in self.models:
            self.active_model = model_name
            return True
        return False
    
    def train_model(
        self,
        model_name: str,
        features: pd.DataFrame,
        returns: pd.Series,
    ) -> bool:
        """Train a specific model"""
        if model_name not in self.models:
            raise ValueError(f"Model not found: {model_name}")
        
        model = self.models[model_name]
        model.fit(features, returns)
        return True
    
    def generate_signals(
        self,
        features: pd.DataFrame,
        symbols: List[str],
        timestamp: datetime,
        model_name: Optional[str] = None,
        horizon: str = "1w",
        min_confidence: float = 0.3,
    ) -> List[Signal]:
        """Generate trading signals for multiple symbols"""
        model_name = model_name or self.active_model
        if model_name is None:
            raise ValueError("No active model set")
        
        model = self.models[model_name]
        if not model.is_fitted:
            raise ValueError(f"Model {model_name} must be fitted before signal generation")
        
        # Generate predictions
        predictions = model.predict(features)
        
        # Convert predictions to signals
        signals = []
        
        for symbol in symbols:
            if symbol in features.index:
                pred_value = predictions.loc[symbol]
                
                # Determine signal type and strength
                signal_type, strength = self._prediction_to_signal(pred_value)
                
                # Calculate confidence based on prediction magnitude
                confidence = min(abs(pred_value) * 2, 1.0)
                
                if confidence < min_confidence:
                    continue
                
                # Get features used
                features_used = list(features.columns)
                
                signal = Signal(
                    symbol=symbol,
                    timestamp=timestamp,
                    signal_type=signal_type,
                    strength=strength,
                    expected_return=float(pred_value),
                    confidence=float(confidence),
                    horizon=horizon,
                    features_used=features_used,
                    model_version=model.version,
                    signal_id="",
                )
                
                signals.append(signal)
                self.signal_history.append(signal)
        
        return signals
    
    def _prediction_to_signal(
        self,
        prediction: float,
    ) -> Tuple[SignalType, SignalStrength]:
        """Convert prediction to signal type and strength"""
        abs_pred = abs(prediction)
        
        if abs_pred < 0.01:
            return SignalType.FLAT, SignalStrength.WEAK
        elif abs_pred < 0.03:
            if prediction > 0:
                return SignalType.LONG, SignalStrength.WEAK
            else:
                return SignalType.SHORT, SignalStrength.WEAK
        elif abs_pred < 0.05:
            if prediction > 0:
                return SignalType.LONG, SignalStrength.MODERATE
            else:
                return SignalType.SHORT, SignalStrength.MODERATE
        elif abs_pred < 0.08:
            if prediction > 0:
                return SignalType.LONG, SignalStrength.STRONG
            else:
                return SignalType.SHORT, SignalStrength.STRONG
        else:
            if prediction > 0:
                return SignalType.LONG, SignalStrength.VERY_STRONG
            else:
                return SignalType.SHORT, SignalStrength.VERY_STRONG
    
    def generate_signal_portfolio(
        self,
        features: pd.DataFrame,
        symbols: List[str],
        timestamp: datetime,
        max_positions: int = 10,
        model_name: Optional[str] = None,
        horizon: str = "1w",
    ) -> SignalPortfolio:
        """Generate a portfolio of signals"""
        signals = self.generate_signals(
            features=features,
            symbols=symbols,
            timestamp=timestamp,
            model_name=model_name,
            horizon=horizon,
        )
        
        # Sort by expected return and confidence
        signals_sorted = sorted(
            signals,
            key=lambda s: s.expected_return * s.confidence,
            reverse=True,
        )
        
        # Take top signals
        top_signals = signals_sorted[:max_positions]
        
        # Calculate portfolio metrics
        if top_signals:
            total_expected_return = sum(s.expected_return for s in top_signals) / len(top_signals)
            portfolio_risk = np.std([s.expected_return for s in top_signals])
            sharpe_ratio = total_expected_return / portfolio_risk if portfolio_risk > 0 else 0.0
        else:
            total_expected_return = 0.0
            portfolio_risk = 0.0
            sharpe_ratio = 0.0
        
        # Calculate turnover (simplified)
        turnover = len(top_signals) / len(symbols) if symbols else 0.0
        
        return SignalPortfolio(
            timestamp=timestamp,
            signals=top_signals,
            total_expected_return=float(total_expected_return),
            portfolio_risk=float(portfolio_risk),
            sharpe_ratio=float(sharpe_ratio),
            turnover=float(turnover),
        )
    
    def get_model_performance(self, model_name: str) -> Dict[str, Any]:
        """Get performance metrics for a model"""
        if model_name not in self.models:
            raise ValueError(f"Model not found: {model_name}")
        
        model = self.models[model_name]
        
        return {
            "name": model.name,
            "version": model.version,
            "is_fitted": model.is_fitted,
            "feature_importance": model.get_feature_importance(),
        }
    
    def get_signal_statistics(self) -> Dict[str, Any]:
        """Get statistics about generated signals"""
        if not self.signal_history:
            return {}
        
        total_signals = len(self.signal_history)
        signal_types = {}
        strengths = {}
        
        for signal in self.signal_history:
            signal_types[signal.signal_type.value] = signal_types.get(signal.signal_type.value, 0) + 1
            strengths[signal.strength.value] = strengths.get(signal.strength.value, 0) + 1
        
        avg_confidence = np.mean([s.confidence for s in self.signal_history])
        avg_expected_return = np.mean([s.expected_return for s in self.signal_history])
        
        return {
            "total_signals": total_signals,
            "signal_types": signal_types,
            "strengths": strengths,
            "average_confidence": float(avg_confidence),
            "average_expected_return": float(avg_expected_return),
        }
