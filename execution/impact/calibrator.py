"""Market Impact Calibrator for model parameter estimation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4
import numpy as np
from scipy.optimize import minimize

from .model import ImpactParameters, AlmgrenChrissModel


@dataclass(frozen=True, slots=True)
class CalibrationData:
    """Historical execution data for impact calibration."""
    trade_id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    order_size: float = 0.0
    execution_price: float = 0.0
    arrival_price: float = 0.0
    adv: float = 1_000_000.0
    volatility: float = 0.02
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def price_impact(self) -> float:
        """Calculate price impact."""
        if self.arrival_price == 0:
            return 0.0
        return (self.execution_price - self.arrival_price) / self.arrival_price
    
    @property
    def participation_rate(self) -> float:
        """Calculate participation rate."""
        return self.order_size / self.adv if self.adv > 0 else 0.0


class ImpactCalibrator:
    """
    Calibrates market impact models from historical execution data.
    
    Estimates model parameters (γ, η) by fitting to historical
    execution data using least squares optimization.
    """
    
    def __init__(self) -> None:
        self._calibration_data: list[CalibrationData] = []
    
    def add_execution(self, data: CalibrationData) -> None:
        """Add execution data for calibration."""
        self._calibration_data.append(data)
    
    def calibrate_almgren_chriss(self) -> ImpactParameters:
        """
        Calibrate Almgren-Chriss model parameters.
        
        Uses least squares to fit:
            ΔP/P = γσ√(V/ADV) + ησ(V/ADV)
        """
        if len(self._calibration_data) < 10:
            # Return default parameters if insufficient data
            return ImpactParameters()
        
        # Extract data
        participation_rates = []
        price_impacts = []
        volatilities = []
        
        for data in self._calibration_data:
            participation_rates.append(data.participation_rate)
            price_impacts.append(data.price_impact)
            volatilities.append(data.volatility)
        
        # Convert to numpy arrays
        X = np.array(participation_rates)
        y = np.array(price_impacts)
        sigma = np.array(volatilities)
        
        # Define objective function
        def objective(params):
            gamma, eta = params
            predicted = gamma * sigma * np.sqrt(X) + eta * sigma * X
            error = y - predicted
            return np.sum(error ** 2)
        
        # Optimize
        initial_guess = [0.1, 0.05]
        bounds = [(0.0, 1.0), (0.0, 1.0)]
        result = minimize(objective, initial_guess, bounds=bounds)
        
        gamma_opt, eta_opt = result.x
        
        # Calculate average volatility and ADV
        avg_sigma = np.mean(sigma)
        avg_adv = np.mean([data.adv for data in self._calibration_data])
        
        return ImpactParameters(
            gamma=float(gamma_opt),
            eta=float(eta_opt),
            sigma=float(avg_sigma),
            adv=float(avg_adv),
        )
    
    def validate_model(
        self,
        model: AlmgrenChrissModel,
        test_data: list[CalibrationData] | None = None
    ) -> dict[str, Any]:
        """
        Validate calibrated model against test data.
        
        Returns performance metrics.
        """
        if test_data is None:
            test_data = self._calibration_data
        
        if not test_data:
            return {}
        
        predicted_impacts = []
        actual_impacts = []
        
        for data in test_data:
            result = model.calculate_impact(data.order_size, data.arrival_price)
            predicted_impacts.append(result["total_impact_bps"] / 10000)
            actual_impacts.append(data.price_impact)
        
        # Calculate metrics
        predicted = np.array(predicted_impacts)
        actual = np.array(actual_impacts)
        
        mae = np.mean(np.abs(predicted - actual))
        rmse = np.sqrt(np.mean((predicted - actual) ** 2))
        correlation = np.corrcoef(predicted, actual)[0, 1] if len(predicted) > 1 else 0
        
        return {
            "mae": float(mae),
            "rmse": float(rmse),
            "correlation": float(correlation) if not np.isnan(correlation) else 0.0,
            "sample_size": len(test_data),
        }
