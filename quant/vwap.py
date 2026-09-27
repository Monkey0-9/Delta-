"""
VWAP and standard deviation bands calculator
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class VWAPResult:
    """VWAP calculation result"""
    vwap: float
    std_dev: float
    upper_1sigma: float
    lower_1sigma: float
    upper_2sigma: float
    lower_2sigma: float
    upper_3sigma: float
    lower_3sigma: float
    current_price: float
    deviation: float  # Current price deviation from VWAP in sigma


class VWAPCalculator:
    """Calculate VWAP and standard deviation bands for intraday analysis"""
    
    def __init__(self):
        self.cache: Dict[str, VWAPResult] = {}
    
    def calculate_vwap(self, bars: List[Dict[str, any]]) -> VWAPResult:
        """Calculate VWAP and sigma bands from OHLCV bars"""
        if not bars:
            raise ValueError("No bars provided")
        
        # Convert to DataFrame
        df = pd.DataFrame(bars)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Calculate VWAP
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['pv'] = df['typical_price'] * df['volume']
        
        cumulative_pv = df['pv'].cumsum()
        cumulative_volume = df['volume'].cumsum()
        
        vwap = cumulative_pv / cumulative_volume
        
        # Calculate standard deviation bands
        df['vwap'] = vwap
        df['deviation'] = (df['typical_price'] - df['vwap']).abs()
        df['weighted_deviation'] = df['deviation'] * df['volume']
        
        cumulative_weighted_deviation = df['weighted_deviation'].cumsum()
        std_dev = np.sqrt(cumulative_weighted_deviation / cumulative_volume)
        
        # Get latest values
        latest_vwap = vwap.iloc[-1]
        latest_std = std_dev.iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # Calculate bands
        upper_1sigma = latest_vwap + latest_std
        lower_1sigma = latest_vwap - latest_std
        upper_2sigma = latest_vwap + 2 * latest_std
        lower_2sigma = latest_vwap - 2 * latest_std
        upper_3sigma = latest_vwap + 3 * latest_std
        lower_3sigma = latest_vwap - 3 * latest_std
        
        # Calculate current deviation in sigma
        deviation = (current_price - latest_vwap) / latest_std if latest_std > 0 else 0
        
        return VWAPResult(
            vwap=latest_vwap,
            std_dev=latest_std,
            upper_1sigma=upper_1sigma,
            lower_1sigma=lower_1sigma,
            upper_2sigma=upper_2sigma,
            lower_2sigma=lower_2sigma,
            upper_3sigma=upper_3sigma,
            lower_3sigma=lower_3sigma,
            current_price=current_price,
            deviation=deviation
        )
    
    def calculate_rolling_vwap(self, bars: List[Dict[str, any]], window: int = 20) -> pd.DataFrame:
        """Calculate rolling VWAP over a window"""
        df = pd.DataFrame(bars)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['pv'] = df['typical_price'] * df['volume']
        
        rolling_pv = df['pv'].rolling(window=window).sum()
        rolling_volume = df['volume'].rolling(window=window).sum()
        
        rolling_vwap = rolling_pv / rolling_volume
        
        df['rolling_vwap'] = rolling_vwap
        return df
    
    def get_signal_from_bands(self, vwap_result: VWAPResult) -> str:
        """Get trading signal based on VWAP band position"""
        deviation = vwap_result.deviation
        
        if deviation <= -2.0:
            return "STRONG_BUY"  # More than 2 sigma below VWAP
        elif deviation <= -1.0:
            return "BUY"  # 1-2 sigma below VWAP
        elif deviation >= 2.0:
            return "STRONG_SELL"  # More than 2 sigma above VWAP
        elif deviation >= 1.0:
            return "SELL"  # 1-2 sigma above VWAP
        else:
            return "NEUTRAL"  # Within 1 sigma
    
    def calculate_mean_reversion_probability(self, vwap_result: VWAPResult) -> float:
        """Calculate probability of mean reversion based on deviation"""
        abs_deviation = abs(vwap_result.deviation)
        
        # Based on statistical properties of normal distribution
        if abs_deviation >= 3.0:
            return 0.85  # 85% chance of reversion from 3+ sigma
        elif abs_deviation >= 2.0:
            return 0.68  # 68% chance of reversion from 2-3 sigma
        elif abs_deviation >= 1.0:
            return 0.32  # 32% chance of reversion from 1-2 sigma
        else:
            return 0.0  # No reversion expected within 1 sigma


class VolumeProfile:
    """Calculate volume profile, Point of Control (POC), and Value Area"""
    
    def __init__(self):
        self.price_levels: Dict[float, int] = {}
    
    def calculate_volume_profile(self, bars: List[Dict[str, any]], 
                                  num_levels: int = 50) -> Dict[str, any]:
        """Calculate volume profile at different price levels"""
        if not bars:
            return {}
        
        df = pd.DataFrame(bars)
        
        # Get price range
        high = df['high'].max()
        low = df['low'].min()
        price_range = high - low
        
        if price_range == 0:
            return {}
        
        # Create price levels
        level_size = price_range / num_levels
        levels = np.arange(low, high + level_size, level_size)
        
        # Calculate volume at each level
        volume_at_level = {}
        
        for _, bar in df.iterrows():
            bar_low = bar['low']
            bar_high = bar['high']
            bar_volume = bar['volume']
            
            # Find which levels this bar covers
            for level in levels:
                if bar_low <= level <= bar_high:
                    # Distribute volume proportionally
                    level_span = min(bar_high, level + level_size) - max(bar_low, level)
                    bar_span = bar_high - bar_low
                    if bar_span > 0:
                        volume_fraction = level_span / bar_span
                        volume_at_level[level] = volume_at_level.get(level, 0) + bar_volume * volume_fraction
        
        # Find Point of Control (POC) - price level with highest volume
        if volume_at_level:
            poc = max(volume_at_level.keys(), key=lambda k: volume_at_level[k])
        else:
            poc = 0
        
        # Calculate Value Area (70% of volume)
        total_volume = sum(volume_at_level.values())
        value_area_volume = total_volume * 0.70
        
        # Find Value Area High (VAH) and Value Area Low (VAL)
        sorted_levels = sorted(volume_at_level.keys())
        cumulative_volume = 0
        vah = sorted_levels[-1]
        val = sorted_levels[0]
        
        for level in sorted_levels:
            cumulative_volume += volume_at_level[level]
            if cumulative_volume >= value_area_volume:
                val = level
                break
        
        return {
            "poc": poc,
            "vah": vah,
            "val": val,
            "volume_at_level": volume_at_level,
            "total_volume": total_volume,
            "value_area_volume": value_area_volume
        }
    
    def get_support_resistance_levels(self, volume_profile: Dict[str, any]) -> List[Dict[str, float]]:
        """Get support and resistance levels from volume profile"""
        levels = []
        
        if not volume_profile:
            return levels
        
        poc = volume_profile.get("poc", 0)
        vah = volume_profile.get("vah", 0)
        val = volume_profile.get("val", 0)
        
        if poc > 0:
            levels.append({"level": poc, "type": "POC", "strength": "high"})
        if vah > 0:
            levels.append({"level": vah, "type": "resistance", "strength": "medium"})
        if val > 0:
            levels.append({"level": val, "type": "support", "strength": "medium"})
        
        return sorted(levels, key=lambda x: x["level"])
