"""Feature Engine - Institutional Feature Store

Generates versioned, point-in-time safe features for quantitative research.
Features are the building blocks for alpha signals and predictive models.
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
import hashlib


class FeatureType(Enum):
    """Types of features"""
    PRICE = "price"
    RETURN = "return"
    VOLATILITY = "volatility"
    MOMENTUM = "momentum"
    VALUE = "value"
    QUALITY = "quality"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    MACRO = "macro"
    SENTIMENT = "sentiment"
    CUSTOM = "custom"


class NeutralizationMethod(Enum):
    """Methods for neutralizing features"""
    NONE = "none"
    MARKET = "market"  # Subtract market return
    SECTOR = "sector"  # Subtract sector return
    INDUSTRY = "industry"  # Subtract industry return
    BETA = "beta"  # Beta-adjusted
    ORTHOGONAL = "orthogonal"  # Gram-Schmidt orthogonalization


@dataclass(slots=True)
class FeatureDefinition:
    """Definition of a feature"""
    name: str
    feature_type: FeatureType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    author: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    feature_id: str = field(default="")
    
    def __post_init__(self):
        """Generate feature ID"""
        if not self.feature_id:
            feature_str = f"{self.name}_{self.version}_{self.feature_type.value}"
            hash_obj = hashlib.md5(feature_str.encode())
            self.feature_id = hash_obj.hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class FeatureValue:
    """A single feature value with metadata"""
    symbol: str
    timestamp: datetime
    feature_name: str
    value: float
    feature_id: str
    pit_timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class Feature(ABC):
    """Abstract base class for features"""
    
    def __init__(self, definition: FeatureDefinition):
        self.definition = definition
    
    @abstractmethod
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute the feature from input data"""
        pass
    
    @abstractmethod
    def validate(self, data: pd.DataFrame) -> bool:
        """Validate that input data has required columns"""
        pass


class ReturnFeature(Feature):
    """Return-based features"""
    
    def __init__(self, period: int = 1, log_return: bool = False):
        definition = FeatureDefinition(
            name=f"return_{period}d",
            feature_type=FeatureType.RETURN,
            description=f"{period}-day return",
            parameters={'period': period, 'log_return': log_return},
        )
        super().__init__(definition)
        self.period = period
        self.log_return = log_return
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute returns"""
        if not self.validate(data):
            raise ValueError("Invalid data for return calculation")
        
        if self.log_return:
            return np.log(data['close'] / data['close'].shift(self.period))
        else:
            return data['close'].pct_change(self.period)
    
    def validate(self, data: pd.DataFrame) -> bool:
        """Validate data has close column"""
        return 'close' in data.columns


class VolatilityFeature(Feature):
    """Volatility-based features"""
    
    def __init__(self, period: int = 20, method: str = "std"):
        definition = FeatureDefinition(
            name=f"volatility_{period}d_{method}",
            feature_type=FeatureType.VOLATILITY,
            description=f"{period}-day volatility using {method}",
            parameters={'period': period, 'method': method},
        )
        super().__init__(definition)
        self.period = period
        self.method = method
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute volatility"""
        if not self.validate(data):
            raise ValueError("Invalid data for volatility calculation")
        
        returns = data['close'].pct_change()
        
        if self.method == "std":
            return returns.rolling(window=self.period).std()
        elif self.method == "parkinson":
            # Parkinson volatility estimator using high/low
            hl = data['high'] / data['low']
            return np.sqrt(1 / (4 * np.log(2)) * (np.log(hl) ** 2).rolling(window=self.period).mean())
        elif self.method == "yang_zhang":
            # Yang-Zhang estimator (more robust)
            log_ho = np.log(data['high'] / data['open'])
            log_lo = np.log(data['low'] / data['open'])
            log_co = np.log(data['close'] / data['open'])
            log_oc = np.log(data['open'] / data['close'].shift(1))
            
            rs = log_ho * (log_ho - log_co) + log_lo * (log_lo - log_co)
            close_open = log_oc ** 2
            
            volatility = np.sqrt((rs.rolling(window=self.period).sum() + close_open.rolling(window=self.period).sum()) / (self.period - 1))
            return volatility
        else:
            raise ValueError(f"Unknown volatility method: {self.method}")
    
    def validate(self, data: pd.DataFrame) -> bool:
        """Validate data has required columns"""
        required = ['close', 'high', 'low']
        return all(col in data.columns for col in required)


class MomentumFeature(Feature):
    """Momentum-based features"""
    
    def __init__(self, period: int = 12, method: str = "price"):
        definition = FeatureDefinition(
            name=f"momentum_{period}d_{method}",
            feature_type=FeatureType.MOMENTUM,
            description=f"{period}-day momentum using {method}",
            parameters={'period': period, 'method': method},
        )
        super().__init__(definition)
        self.period = period
        self.method = method
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute momentum"""
        if not self.validate(data):
            raise ValueError("Invalid data for momentum calculation")
        
        if self.method == "price":
            # Price momentum
            return (data['close'] / data['close'].shift(self.period) - 1)
        elif self.method == "ma_cross":
            # Moving average crossover
            ma_short = data['close'].rolling(window=self.period // 2).mean()
            ma_long = data['close'].rolling(window=self.period).mean()
            return (ma_short / ma_long - 1)
        elif self.method == "roc":
            # Rate of change
            return data['close'].diff(self.period) / data['close'].shift(self.period)
        else:
            raise ValueError(f"Unknown momentum method: {self.method}")
    
    def validate(self, data: pd.DataFrame) -> bool:
        """Validate data has close column"""
        return 'close' in data.columns


class ValueFeature(Feature):
    """Value-based features (fundamental ratios)"""
    
    def __init__(self, ratio: str = "pe"):
        definition = FeatureDefinition(
            name=f"value_{ratio}",
            feature_type=FeatureType.VALUE,
            description=f"{ratio} ratio value feature",
            parameters={'ratio': ratio},
        )
        super().__init__(definition)
        self.ratio = ratio
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute value feature"""
        if not self.validate(data):
            raise ValueError("Invalid data for value calculation")
        
        if self.ratio in data.columns:
            return data[self.ratio]
        else:
            # Placeholder - in real implementation, would fetch fundamental data
            return pd.Series(np.nan, index=data.index)
    
    def validate(self, data: pd.DataFrame) -> bool:
        """Validate data has the ratio column or fallback"""
        return True  # Fundamental data may be added later


class TechnicalFeature(Feature):
    """Technical analysis features"""
    
    def __init__(self, indicator: str = "rsi", period: int = 14):
        definition = FeatureDefinition(
            name=f"technical_{indicator}_{period}",
            feature_type=FeatureType.TECHNICAL,
            description=f"{indicator} indicator with period {period}",
            parameters={'indicator': indicator, 'period': period},
        )
        super().__init__(definition)
        self.indicator = indicator
        self.period = period
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute technical indicator"""
        if not self.validate(data):
            raise ValueError("Invalid data for technical calculation")
        
        if self.indicator == "rsi":
            # Relative Strength Index
            delta = data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        
        elif self.indicator == "macd":
            # MACD (simplified)
            ema_12 = data['close'].ewm(span=12).mean()
            ema_26 = data['close'].ewm(span=26).mean()
            return ema_12 - ema_26
        
        elif self.indicator == "bollinger":
            # Bollinger Bands position
            sma = data['close'].rolling(window=self.period).mean()
            std = data['close'].rolling(window=self.period).std()
            upper_band = sma + (2 * std)
            lower_band = sma - (2 * std)
            return (data['close'] - lower_band) / (upper_band - lower_band)
        
        else:
            raise ValueError(f"Unknown technical indicator: {self.indicator}")
    
    def validate(self, data: pd.DataFrame) -> bool:
        """Validate data has close column"""
        return 'close' in data.columns


class FeatureEngine:
    """Main feature engine for generating and managing features"""
    
    def __init__(self):
        self.features: Dict[str, Feature] = {}
        self.feature_history: Dict[str, List[FeatureDefinition]] = {}
        self._register_default_features()
    
    def _register_default_features(self):
        """Register default feature implementations"""
        # Common return periods
        for period in [1, 5, 10, 20, 60]:
            self.register_feature(ReturnFeature(period=period))
            self.register_feature(ReturnFeature(period=period, log_return=True))
        
        # Common volatility periods
        for period in [10, 20, 60]:
            for method in ["std", "parkinson"]:
                self.register_feature(VolatilityFeature(period=period, method=method))
        
        # Common momentum periods
        for period in [3, 6, 12]:
            for method in ["price", "ma_cross"]:
                self.register_feature(MomentumFeature(period=period, method=method))
        
        # Technical indicators
        for period in [14, 21]:
            self.register_feature(TechnicalFeature(indicator="rsi", period=period))
        
        self.register_feature(TechnicalFeature(indicator="macd"))
        self.register_feature(TechnicalFeature(indicator="bollinger", period=20))
    
    def register_feature(self, feature: Feature) -> bool:
        """Register a new feature"""
        feature_id = feature.definition.feature_id
        self.features[feature_id] = feature
        
        # Track version history
        if feature.definition.name not in self.feature_history:
            self.feature_history[feature.definition.name] = []
        self.feature_history[feature.definition.name].append(feature.definition)
        
        return True
    
    def compute_feature(
        self,
        data: pd.DataFrame,
        feature_name: str,
        parameters: Dict[str, Any] = None,
    ) -> pd.Series:
        """Compute a specific feature"""
        # Find matching feature
        for feature_id, feature in self.features.items():
            if feature.definition.name == feature_name:
                return feature.compute(data)
        
        raise ValueError(f"Feature not found: {feature_name}")
    
    def compute_all_features(
        self,
        data: pd.DataFrame,
        feature_types: List[FeatureType] = None,
    ) -> pd.DataFrame:
        """Compute all features or specific types"""
        if feature_types is None:
            feature_types = list(FeatureType)
        
        result = pd.DataFrame(index=data.index)
        
        for feature_id, feature in self.features.items():
            if feature.definition.feature_type in feature_types:
                try:
                    feature_values = feature.compute(data)
                    result[feature.definition.name] = feature_values
                except Exception as e:
                    print(f"Error computing feature {feature.definition.name}: {e}")
        
        return result
    
    def neutralize_feature(
        self,
        feature: pd.Series,
        method: NeutralizationMethod = NeutralizationMethod.MARKET,
        market_returns: Optional[pd.Series] = None,
        sector_returns: Optional[pd.Series] = None,
    ) -> pd.Series:
        """Neutralize a feature using specified method"""
        if method == NeutralizationMethod.NONE:
            return feature
        
        elif method == NeutralizationMethod.MARKET:
            if market_returns is None:
                raise ValueError("Market returns required for market neutralization")
            # Remove market component
            beta = feature.rolling(window=60).cov(market_returns) / market_returns.rolling(window=60).var()
            neutralized = feature - beta * market_returns
            return neutralized
        
        elif method == NeutralizationMethod.SECTOR:
            if sector_returns is None:
                raise ValueError("Sector returns required for sector neutralization")
            # Remove sector component
            beta = feature.rolling(window=60).cov(sector_returns) / sector_returns.rolling(window=60).var()
            neutralized = feature - beta * sector_returns
            return neutralized
        
        elif method == NeutralizationMethod.BETA:
            if market_returns is None:
                raise ValueError("Market returns required for beta neutralization")
            # Beta-adjusted
            beta = feature.rolling(window=60).cov(market_returns) / market_returns.rolling(window=60).var()
            beta_adj = feature / beta
            return beta_adj
        
        elif method == NeutralizationMethod.ORTHOGONAL:
            # Gram-Schmidt orthogonalization (simplified)
            if market_returns is not None:
                # Remove market component
                feature = feature - (feature.mean() + 
                                   (feature - feature.mean()).cov(market_returns - market_returns.mean()) / 
                                   market_returns.var() * (market_returns - market_returns.mean()))
            return feature
        
        else:
            raise ValueError(f"Unknown neutralization method: {method}")
    
    def winsorize_feature(
        self,
        feature: pd.Series,
        lower: float = 0.01,
        upper: float = 0.99,
    ) -> pd.Series:
        """Winsorize feature to handle outliers"""
        lower_bound = feature.quantile(lower)
        upper_bound = feature.quantile(upper)
        
        return feature.clip(lower=lower_bound, upper=upper_bound)
    
    def normalize_feature(
        self,
        feature: pd.Series,
        method: str = "zscore",
    ) -> pd.Series:
        """Normalize feature using specified method"""
        if method == "zscore":
            return (feature - feature.mean()) / feature.std()
        elif method == "minmax":
            return (feature - feature.min()) / (feature.max() - feature.min())
        elif method == "rank":
            return feature.rank(pct=True)
        else:
            raise ValueError(f"Unknown normalization method: {method}")
    
    def get_feature_definition(self, feature_name: str) -> Optional[FeatureDefinition]:
        """Get definition for a feature"""
        for feature in self.features.values():
            if feature.definition.name == feature_name:
                return feature.definition
        return None
    
    def list_features(self, feature_type: FeatureType = None) -> List[str]:
        """List available features, optionally filtered by type"""
        if feature_type is None:
            return [f.definition.name for f in self.features.values()]
        else:
            return [f.definition.name for f in self.features.values() 
                   if f.definition.feature_type == feature_type]
    
    def get_feature_lineage(self, feature_name: str) -> List[FeatureDefinition]:
        """Get version history for a feature"""
        return self.feature_history.get(feature_name, [])
