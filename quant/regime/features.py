"""Regime Features for market environment classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import numpy as np


@dataclass(frozen=True, slots=True)
class RegimeFeatures:
    """
    Features for regime classification.
    
    Includes market microstructure, macro indicators, and
    technical analysis features for regime detection.
    """
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Volatility features
    realized_volatility: float = 0.02  # Daily realized volatility
    vix: float = 20.0  # VIX index level
    volatility_regime: str = "normal"  # low, normal, high
    
    # Liquidity features
    bid_ask_spread_bps: float = 5.0  # Average bid-ask spread
    market_depth: float = 1_000_000.0  # Average market depth
    turnover_rate: float = 0.5  # Daily turnover rate
    liquidity_regime: str = "normal"  # normal, stressed, crisis
    
    # Trend features
    price_trend: float = 0.0  # Price trend (positive = bullish)
    momentum: float = 0.0  # Momentum indicator
    moving_average_ratio: float = 1.0  # Price / MA ratio
    
    # Macro features
    credit_spread: float = 100.0  # Credit spread (bps)
    yield_curve_slope: float = 1.0  # Yield curve slope
    inflation_rate: float = 2.0  # Inflation rate (%)
    interest_rate_level: float = 3.0  # Interest rate level (%)
    
    # Market breadth
    advance_decline_ratio: float = 1.0  # Advance/decline ratio
    new_highs_lows: float = 0.0  # New highs minus new lows
    
    # Cross-asset correlations
    equity_bond_correlation: float = -0.3  # Equity-bond correlation
    sector_dispersion: float = 0.02  # Sector return dispersion
    
    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary for classification."""
        return {
            "volatility": self.realized_volatility,
            "vix": self.vix,
            "liquidity": self.turnover_rate,
            "trend": self.price_trend,
            "credit_spread": self.credit_spread,
            "yield_curve": self.yield_curve_slope,
            "inflation": self.inflation_rate,
            "advance_decline": self.advance_decline_ratio,
        }
    
    def calculate_z_scores(self, historical_features: list[RegimeFeatures]) -> dict[str, float]:
        """
        Calculate z-scores relative to historical distribution.
        
        Used for detecting regime shifts through statistical anomalies.
        """
        if not historical_features:
            return {}
        
        # Extract feature arrays
        volatilities = [f.realized_volatility for f in historical_features]
        vix_values = [f.vix for f in historical_features]
        spreads = [f.bid_ask_spread_bps for f in historical_features]
        trends = [f.price_trend for f in historical_features]
        
        # Calculate z-scores
        z_scores = {}
        
        for feature_name, current_value, historical in [
            ("volatility", self.realized_volatility, volatilities),
            ("vix", self.vix, vix_values),
            ("spread", self.bid_ask_spread_bps, spreads),
            ("trend", self.price_trend, trends),
        ]:
            mean = np.mean(historical)
            std = np.std(historical)
            
            if std > 0:
                z_scores[feature_name] = (current_value - mean) / std
            else:
                z_scores[feature_name] = 0.0
        
        return z_scores
