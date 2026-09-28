"""
Historical Scenario Database for DELTA OS.

This module implements a comprehensive historical scenario database for:
- Major market crashes and stress events
- Historical replay for backtesting
- Stress testing and risk analysis
- Scenario-based validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Any, Tuple
import pandas as pd
import numpy as np
from pathlib import Path


class ScenarioType(Enum):
    """Historical scenario types."""
    CRASH_1987 = "crash_1987"
    LTCM_1998 = "ltcm_1998"
    DOT_COM_2000 = "dot_com_2000"
    CRISIS_2008 = "crisis_2008"
    FLASH_CRASH_2010 = "flash_crash_2010"
    VOLATILITY_2015 = "volatility_2015"
    VOLATILITY_2018 = "volatility_2018"
    COVID_2020 = "covid_2020"
    RATES_2022 = "rates_2022"
    RECENT_2023_2026 = "recent_2023_2026"


@dataclass
class Scenario:
    """
    Historical market scenario definition.
    
    Attributes:
        scenario_id: Unique scenario identifier
        scenario_type: Type of scenario
        name: Scenario name
        description: Scenario description
        start_date: Scenario start date
        end_date: Scenario end date
        characteristics: Market characteristics during scenario
        data_path: Path to scenario data
        metadata: Additional metadata
    """
    scenario_id: str
    scenario_type: ScenarioType
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    characteristics: Dict[str, Any] = field(default_factory=dict)
    data_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_days(self) -> int:
        """Scenario duration in days."""
        return (self.end_date - self.start_date).days


class ScenarioDatabase:
    """
    Database of historical market scenarios.
    
    Features:
    - Major historical market events
    - Stress testing scenarios
    - Scenario replay capability
    - Risk analysis under stress
    """
    
    def __init__(self, data_path: Optional[Path] = None):
        """
        Initialize scenario database.
        
        Args:
            data_path: Path to scenario data directory
        """
        self._data_path = data_path or Path("data/scenarios/data")
        self._scenarios: Dict[str, Scenario] = {}
        
        # Initialize built-in scenarios
        self._initialize_builtin_scenarios()
    
    def _initialize_builtin_scenarios(self) -> None:
        """Initialize built-in historical scenarios."""
        # 1987 Crash
        self._scenarios["1987_crash"] = Scenario(
            scenario_id="1987_crash",
            scenario_type=ScenarioType.CRASH_1987,
            name="1987 Stock Market Crash",
            description="Black Monday - largest one-day market crash in history",
            start_date=datetime(1987, 10, 19, tzinfo=timezone.utc),
            end_date=datetime(1987, 10, 20, tzinfo=timezone.utc),
            characteristics={
                "max_drawdown": -0.22,  # -22%
                "volatility_spike": 5.0,  # 5x normal volatility
                "liquidity_dry_up": True,
                "market_cap_impact": -20,  # -20% market cap loss
            }
        )
        
        # 1998 LTCM Crisis
        self._scenarios["1998_ltcm"] = Scenario(
            scenario_id="1998_ltcm",
            scenario_type=ScenarioType.LTCM_1998,
            name="1998 LTCM Crisis",
            description="Long-Term Capital Management collapse and market contagion",
            start_date=datetime(1998, 8, 17, tzinfo=timezone.utc),
            end_date=datetime(1998, 10, 15, tzinfo=timezone.utc),
            characteristics={
                "volatility_spike": 3.0,
                "correlation_breakdown": True,
                "liquidity_crisis": True,
                "flight_to_quality": True
            }
        )
        
        # 2000-2002 Dot-com Bubble
        self._scenarios["2000_dotcom"] = Scenario(
            scenario_id="2000_dotcom",
            scenario_type=ScenarioType.DOT_COM_2000,
            name="2000-2002 Dot-com Bubble Burst",
            description="Dot-com bubble burst and subsequent bear market",
            start_date=datetime(2000, 3, 10, tzinfo=timezone.utc),
            end_date=datetime(2002, 10, 9, tzinfo=timezone.utc),
            characteristics={
                "max_drawdown": -0.78,  # -78% NASDAQ
                "volatility_elevated": 2.5,
                "sector_specific": True,
                "tech_sector_impact": -0.85
            }
        )
        
        # 2008 Financial Crisis
        self._scenarios["2008_crisis"] = Scenario(
            scenario_id="2008_crisis",
            scenario_type=ScenarioType.CRISIS_2008,
            name="2008 Global Financial Crisis",
            description="Global financial crisis and market collapse",
            start_date=datetime(2008, 9, 15, tzinfo=timezone.utc),
            end_date=datetime(2009, 3, 9, tzinfo=timezone.utc),
            characteristics={
                "max_drawdown": -0.57,  # -57% S&P 500
                "volatility_spike": 4.0,
                "correlation_breakdown": True,
                "liquidity_freeze": True,
                "systemic_risk": True
            }
        )
        
        # 2010 Flash Crash
        self._scenarios["2010_flash_crash"] = Scenario(
            scenario_id="2010_flash_crash",
            scenario_type=ScenarioType.FLASH_CRASH_2010,
            name="2010 Flash Crash",
            description="Rapid market decline and recovery in minutes",
            start_date=datetime(2010, 5, 6, 14, 30, tzinfo=timezone.utc),
            end_date=datetime(2010, 5, 6, 15, 0, tzinfo=timezone.utc),
            characteristics={
                "max_drawdown": -0.09,  # -9% in minutes
                "intraday_volatility": 10.0,
                "liquidity_mismatch": True,
                "algo_trading_impact": True
            }
        )
        
        # 2015 Volatility Shock
        self._scenarios["2015_volatility"] = Scenario(
            scenario_id="2015_volatility",
            scenario_type=ScenarioType.VOLATILITY_2015,
            name="2015 Volatility Shock",
            description="China market volatility and global contagion",
            start_date=datetime(2015, 8, 24, tzinfo=timezone.utc),
            end_date=datetime(2015, 8, 28, tzinfo=timezone.utc),
            characteristics={
                "volatility_spike": 3.5,
                "gap_risk": True,
                "global_contagion": True
            }
        )
        
        # 2018 Volatility Shock
        self._scenarios["2018_volatility"] = Scenario(
            scenario_id="2018_volatility",
            scenario_type=ScenarioType.VOLATILITY_2018,
            name="2018 Volatility Shock",
            description="VIX spike and market volatility surge",
            start_date=datetime(2018, 2, 5, tzinfo=timezone.utc),
            end_date=datetime(2018, 2, 9, tzinfo=timezone.utc),
            characteristics={
                "volatility_spike": 2.8,
                "vix_peak": 50.0,
                "equity_volatility": 4.0
            }
        )
        
        # 2020 COVID Crash
        self._scenarios["2020_covid"] = Scenario(
            scenario_id="2020_covid",
            scenario_type=ScenarioType.COVID_2020,
            name="2020 COVID-19 Market Crash",
            description="COVID-19 pandemic and global market crash",
            start_date=datetime(2020, 2, 19, tzinfo=timezone.utc),
            end_date=datetime(2020, 3, 23, tzinfo=timezone.utc),
            characteristics={
                "max_drawdown": -0.34,  # -34% S&P 500
                "volatility_spike": 5.0,
                "liquidity_stress": True,
                "sector_rotation": True,
                "flight_to_safety": True
            }
        )
        
        # 2022 Rates/Inflation Shock
        self._scenarios["2022_rates"] = Scenario(
            scenario_id="2022_rates",
            scenario_type=ScenarioType.RATES_2022,
            name="2022 Rates and Inflation Shock",
            description="Rapid interest rate increases and inflation concerns",
            start_date=datetime(2022, 4, 1, tzinfo=timezone.utc),
            end_date=datetime(2022, 10, 14, tzinfo=timezone.utc),
            characteristics={
                "rate_volatility": 3.0,
                "inflation_uncertainty": True,
                "bond_market_stress": True,
                "growth_stock_impact": -0.25
            }
        )
        
        # 2023-2026 Recent Events
        self._scenarios["2023_2026_recent"] = Scenario(
            scenario_id="2023_2026_recent",
            scenario_type=ScenarioType.RECENT_2023_2026,
            name="2023-2026 Recent Market Events",
            description="Recent market events and regime changes",
            start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 9, 28, tzinfo=timezone.utc),
            characteristics={
                "ai_sector_rotation": True,
                "tech_volatility": 2.0,
                "regime_uncertainty": True
            }
        )
    
    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """
        Get scenario by ID.
        
        Args:
            scenario_id: Scenario identifier
            
        Returns:
            Scenario if found, None otherwise
        """
        return self._scenarios.get(scenario_id)
    
    def get_scenarios_by_type(self, scenario_type: ScenarioType) -> List[Scenario]:
        """
        Get scenarios by type.
        
        Args:
            scenario_type: Scenario type
            
        Returns:
            List of matching scenarios
        """
        return [s for s in self._scenarios.values() if s.scenario_type == scenario_type]
    
    def list_scenarios(self) -> List[str]:
        """List all scenario IDs."""
        return list(self._scenarios.keys())
    
    def replay_scenario(
        self,
        scenario_id: str,
        strategy_function,
        initial_capital: Decimal = Decimal("1000000")
    ) -> Dict[str, Any]:
        """
        Replay historical scenario for strategy testing.
        
        Args:
            scenario_id: Scenario to replay
            strategy_function: Strategy function to test
            initial_capital: Initial capital for backtest
            
        Returns:
            Backtest results
        """
        scenario = self.get_scenario(scenario_id)
        if scenario is None:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        # Load scenario data (in production, this would load actual historical data)
        # For now, we'll simulate the scenario characteristics
        
        # Simulate scenario data based on characteristics
        dates = pd.date_range(
            start=scenario.start_date,
            end=scenario.end_date,
            freq='D'
        )
        
        # Generate synthetic data with scenario characteristics
        n_days = len(dates)
        returns = np.random.normal(
            loc=scenario.characteristics.get('max_drawdown', 0) / n_days,
            scale=scenario.characteristics.get('volatility_spike', 1.0) * 0.02,
            size=n_days
        )
        
        # Apply correlation breakdown if specified
        if scenario.characteristics.get('correlation_breakdown'):
            returns += np.random.normal(0, 0.01, n_days)
        
        # Create price series
        prices = initial_capital * (1 + np.cumsum(returns))
        
        # Run strategy (simplified)
        if strategy_function:
            results = strategy_function(prices, scenario.characteristics)
        else:
            results = {
                'final_capital': Decimal(str(prices[-1])),
                'total_return': float((prices[-1] / prices[0] - 1)),
                'max_drawdown': scenario.characteristics.get('max_drawdown', 0),
            }
        
        return {
            'scenario_id': scenario_id,
            'scenario_name': scenario.name,
            'results': results,
            'dates': dates.tolist(),
            'prices': prices.tolist(),
            'returns': returns.tolist(),
        }


class StressTestEngine:
    """
    Stress testing engine using historical scenarios.
    
    Features:
    - Scenario-based stress testing
    - Portfolio stress analysis
    - Risk factor stress testing
    - Liquidity stress testing
    """
    
    def __init__(self, scenario_db: ScenarioDatabase):
        """
        Initialize stress test engine.
        
        Args:
            scenario_db: Scenario database
        """
        self._scenario_db = scenario_db
    
    def stress_test_portfolio(
        self,
        portfolio_weights: Dict[str, float],
        scenario_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Stress test portfolio against historical scenarios.
        
        Args:
            portfolio_weights: Portfolio weights by asset
            scenario_ids: Scenarios to test
            
        Returns:
            Stress test results
        """
        results = {}
        
        for scenario_id in scenario_ids:
            scenario = self._scenario_db.get_scenario(scenario_id)
            if scenario is None:
                continue
            
            # Calculate portfolio impact under scenario
            scenario_drawdown = scenario.characteristics.get('max_drawdown', 0)
            
            # Apply drawdown to portfolio (simplified)
            portfolio_impact = scenario_drawdown * sum(portfolio_weights.values())
            
            results[scenario_id] = {
                'scenario_name': scenario.name,
                'portfolio_impact': portfolio_impact,
                'stress_level': self._classify_stress(portfolio_impact),
                'characteristics': scenario.characteristics
            }
        
        return results
    
    def _classify_stress(self, impact: float) -> str:
        """Classify stress level."""
        if impact < -0.20:
            return "SEVERE"
        elif impact < -0.10:
            return "HIGH"
        elif impact < -0.05:
            return "MODERATE"
        else:
            return "LOW"


__all__ = [
    "ScenarioType",
    "Scenario",
    "ScenarioDatabase",
    "StressTestEngine",
]
