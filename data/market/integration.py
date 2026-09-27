"""Integration Layer - Connect Real Data with DELTA System

This module bridges the new real market data infrastructure with the
existing DELTA trader service, replacing demo_candidates() with real signals.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from .adapters import MarketDataAdapter, YahooFinanceAdapter, HistoricalAdapter
from .pit_store import PointInTimeStore, PITRecord, UniverseManager
from .quality import DataQualityChecker, QualityReport
from .feature_engine import FeatureEngine, FeatureType
from .signal_generator import SignalGenerator, Signal, SignalPortfolio
from quant.horizon.engines import ScanCandidate, ScanResult


@dataclass
class RealDataConfig:
    """Configuration for real data pipeline"""
    primary_adapter: str = "yahoo"  # yahoo, alphavantage, polygon
    fallback_adapters: List[str] = None
    api_keys: Dict[str, str] = None
    pit_lag_minutes: int = 15
    quality_threshold: str = "ACCEPTABLE"  # EXCELLENT, GOOD, ACCEPTABLE, POOR
    cache_enabled: bool = True
    cache_duration_hours: int = 24


class RealDataPipeline:
    """Main pipeline for real market data → features → signals"""
    
    def __init__(self, config: RealDataConfig = None):
        self.config = config or RealDataConfig()
        
        # Initialize components
        self._initialize_adapters()
        self.pit_store = PointInTimeStore()
        self.quality_checker = DataQualityChecker()
        self.feature_engine = FeatureEngine()
        self.signal_generator = SignalGenerator()
        self.universe_manager = UniverseManager(self.pit_store)
        
        # Cache for performance
        self._cache: Dict[str, Tuple[pd.DataFrame, datetime]] = {}
    
    def _initialize_adapters(self):
        """Initialize market data adapters"""
        if self.config.primary_adapter == "yahoo":
            self.primary_adapter = YahooFinanceAdapter()
        elif self.config.primary_adapter == "alphavantage":
            api_key = self.config.api_keys.get("alphavantage") if self.config.api_keys else None
            if not api_key:
                raise ValueError("Alpha Vantage API key required")
            from .adapters import AlphaVantageAdapter
            self.primary_adapter = AlphaVantageAdapter(api_key)
        else:
            raise ValueError(f"Unknown primary adapter: {self.config.primary_adapter}")
        
        # Initialize fallback adapters if specified
        self.fallback_adapters = []
        if self.config.fallback_adapters:
            for adapter_name in self.config.fallback_adapters:
                if adapter_name == "yahoo" and self.config.primary_adapter != "yahoo":
                    self.fallback_adapters.append(YahooFinanceAdapter())
                elif adapter_name == "alphavantage":
                    api_key = self.config.api_keys.get("alphavantage") if self.config.api_keys else None
                    if api_key:
                        from .adapters import AlphaVantageAdapter
                        self.fallback_adapters.append(AlphaVantageAdapter(api_key))
        
        # Create historical adapter with fallbacks
        if self.fallback_adapters:
            self.historical_adapter = HistoricalAdapter(self.primary_adapter, self.fallback_adapters)
        else:
            self.historical_adapter = self.historical_adapter = self.primary_adapter
    
    async def fetch_historical_data(
        self,
        symbols: List[str],
        start: datetime,
        end: datetime,
        store_pit: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch historical data for multiple symbols"""
        await self.historical_adapter.connect()
        
        data_dict = {}
        for symbol in symbols:
            try:
                df = await self.historical_adapter.get_historical_bars(
                    symbol=symbol,
                    start=start,
                    end=end,
                )
                
                if not df.empty:
                    # Quality check
                    quality_report = self.quality_checker.check_dataframe(df, symbol)
                    
                    if quality_report.overall_quality in ["EXCELLENT", "GOOD", "ACCEPTABLE"]:
                        # Clean data if needed
                        if quality_report.overall_quality != "EXCELLENT":
                            df = self.quality_checker.clean_dataframe(df, quality_report)
                        
                        data_dict[symbol] = df
                        
                        # Store in PIT if requested
                        if store_pit:
                            self._store_pit_data(symbol, df, quality_report)
                    else:
                        print(f"Skipping {symbol} due to poor data quality: {quality_report.overall_quality}")
                
            except Exception as e:
                print(f"Error fetching data for {symbol}: {e}")
        
        await self.historical_adapter.disconnect()
        return data_dict
    
    def fetch_historical_data_sync(
        self,
        symbols: List[str],
        start: datetime,
        end: datetime,
        store_pit: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """Synchronous wrapper for fetch_historical_data"""
        import asyncio
        return asyncio.run(self.fetch_historical_data(symbols, start, end, store_pit))
    
    def _store_pit_data(self, symbol: str, df: pd.DataFrame, quality_report: QualityReport):
        """Store data in point-in-time store"""
        for idx, row in df.iterrows():
            if isinstance(idx, pd.Timestamp):
                timestamp = idx.to_pydatetime()
            else:
                timestamp = idx
            
            record = PITRecord(
                symbol=symbol,
                timestamp=timestamp,
                pit_timestamp=timestamp,  # Historical data is available immediately
                data_type="ohlcv",
                data=row.to_dict(),
                source=self.config.primary_adapter,
            )
            self.pit_store.store_record(record)
        
        # Store quality metadata
        self.pit_store.set_metadata(
            f"quality_{symbol}",
            {
                "overall_quality": quality_report.overall_quality,
                "pass_rate": quality_report.pass_rate,
                "check_count": len(quality_report.checks),
                "timestamp": datetime.now().isoformat(),
            }
        )
    
    def get_pit_data(
        self,
        symbol: str,
        timestamp: datetime,
        data_type: str = "ohlcv",
    ) -> Optional[pd.DataFrame]:
        """Get point-in-time data for a specific timestamp"""
        record = self.pit_store.get_data_at_pit(
            symbol=symbol,
            timestamp=timestamp,
            data_type=data_type,
            max_lag_minutes=self.config.pit_lag_minutes,
        )
        
        if record:
            return pd.DataFrame([record.data])
        return None
    
    def generate_features(
        self,
        data_dict: Dict[str, pd.DataFrame],
        feature_types: List[FeatureType] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Generate features for multiple symbols"""
        features_dict = {}
        
        for symbol, df in data_dict.items():
            try:
                features = self.feature_engine.compute_all_features(df, feature_types)
                features_dict[symbol] = features
            except Exception as e:
                print(f"Error generating features for {symbol}: {e}")
        
        return features_dict
    
    def train_signal_model(
        self,
        features_dict: Dict[str, pd.DataFrame],
        model_name: str = "rank",
    ) -> bool:
        """Train signal model on historical data"""
        # Combine features from all symbols
        all_features = []
        all_returns = []
        
        for symbol, features in features_dict.items():
            if 'close' in features_dict[symbol].columns:
                # Calculate forward returns for training
                returns = features_dict[symbol]['close'].pct_change(5).shift(-5)  # 5-day forward return
                
                # Merge features with returns
                combined = features.copy()
                combined['target_return'] = returns
                
                all_features.append(combined)
        
        if not all_features:
            print("No valid data for training")
            return False
        
        # Combine all data
        combined_df = pd.concat(all_features, ignore_index=True)
        combined_df = combined_df.dropna()
        
        # Separate features and target
        feature_cols = [col for col in combined_df.columns if col != 'target_return']
        X = combined_df[feature_cols]
        y = combined_df['target_return']
        
        # Train model
        try:
            self.signal_generator.train_model(model_name, X, y)
            return True
        except Exception as e:
            print(f"Error training model: {e}")
            return False
    
    def generate_real_signals(
        self,
        symbols: List[str],
        timestamp: datetime,
        model_name: str = "rank",
        horizon: str = "1w",
    ) -> List[Signal]:
        """Generate real trading signals using the complete pipeline"""
        # 1. Fetch recent data (synchronous)
        end_date = timestamp
        start_date = timestamp - timedelta(days=90)  # 3 months of data
        
        data_dict = self.fetch_historical_data_sync(symbols, start_date, end_date)
        
        if not data_dict:
            print("No data available for signal generation")
            return []
        
        # 2. Generate features
        features_dict = self.generate_features(data_dict)
        
        if not features_dict:
            print("No features generated")
            return []
        
        # 3. Get latest features for each symbol
        latest_features = {}
        for symbol, features in features_dict.items():
            if not features.empty:
                latest_features[symbol] = features.iloc[-1]
        
        if not latest_features:
            print("No latest features available")
            return []
        
        # 4. Create feature DataFrame
        features_df = pd.DataFrame(latest_features).T
        
        # 5. Train model if not already trained
        model = self.signal_generator.models.get(model_name)
        if model and not model.is_fitted:
            self.train_signal_model(features_dict, model_name)
        
        # 6. Generate signals
        signals = self.signal_generator.generate_signals(
            features=features_df,
            symbols=symbols,
            timestamp=timestamp,
            model_name=model_name,
            horizon=horizon,
        )
        
        return signals
    
    def convert_to_scan_candidates(
        self,
        signals: List[Signal],
        timestamp: datetime,
    ) -> List[ScanCandidate]:
        """Convert real signals to ScanCandidate format for DELTA compatibility"""
        candidates = []
        
        for signal in signals:
            # Map signal strength to confidence
            confidence_map = {
                "weak": 0.4,
                "moderate": 0.6,
                "strong": 0.8,
                "very_strong": 0.95,
            }
            confidence = confidence_map.get(signal.strength.value, 0.5)
            
            # Map signal type to decision
            if signal.signal_type.value in ["long", "increase"]:
                decision = "TRADE"
            elif signal.signal_type.value in ["short", "reduce"]:
                decision = "TRADE"  # Short positions
            else:
                decision = "HOLD"
            
            # Calculate predicted risk (simplified)
            predicted_risk = abs(signal.expected_return) * 2.0
            
            candidate = ScanCandidate(
                symbol=signal.symbol,
                expected_return=float(signal.expected_return),
                predicted_risk=float(predicted_risk),
                confidence=float(confidence),
                uncertainty=1.0 - float(signal.confidence),
                liquidity=0.7,  # Default liquidity
                estimated_cost_bps=10.0,  # Default cost
                data_age_s=0.0,
                portfolio_weight=0.0,
                regime="mixed",
            )
            
            candidates.append(candidate)
        
        return candidates


def replace_demo_candidates_with_real(
    mandate,
    horizon: str,
    portfolio_weights: dict = None,
    config: RealDataConfig = None,
) -> List[ScanCandidate]:
    """
    Replacement function for demo_candidates() that uses real data.
    
    This is the key integration point that replaces the deterministic demo
    system with real market data → features → signals pipeline.
    """
    if config is None:
        config = RealDataConfig()
    
    # Initialize real data pipeline
    pipeline = RealDataPipeline(config)
    
    # Get symbols from mandate
    universe_symbols = mandate.universe
    
    # Generate real signals
    timestamp = datetime.now()
    
    # Generate signals (now synchronous)
    signals = pipeline.generate_real_signals(
        symbols=universe_symbols,
        timestamp=timestamp,
        model_name="rank",
        horizon=horizon,
    )
    
    # Convert to DELTA format
    candidates = pipeline.convert_to_scan_candidates(signals, timestamp)
    
    # If no real signals generated, fall back to demo candidates
    if not candidates:
        print("Warning: No real signals generated, falling back to demo candidates")
        from trader.service import demo_candidates
        return demo_candidates(mandate, horizon, portfolio_weights)
    
    return candidates