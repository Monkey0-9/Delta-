"""Forecast Engine - Model-Based Predictions

Implements ensemble forecasting for alpha signals with uncertainty estimation.
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


class ModelType(Enum):
    """Types of forecasting models"""
    LINEAR = "linear"
    RIDGE = "ridge"
    LASSO = "lasso"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    NEURAL_NETWORK = "neural_network"
    LSTM = "lstm"
    TRANSFORMER = "transformer"
    ENSEMBLE = "ensemble"


class UncertaintyMethod(Enum):
    """Methods for uncertainty estimation"""
    BOOTSTRAP = "bootstrap"
    DROPOUT = "dropout"
    QUANTILE = "quantile"
    CONFORMAL = "conformal"
    BAYESIAN = "bayesian"


@dataclass(frozen=True, slots=True)
class Forecast:
    """A single forecast with uncertainty"""
    symbol: str
    timestamp: datetime
    prediction: float
    confidence_interval_low: float
    confidence_interval_high: float
    uncertainty: float
    confidence: float
    model_name: str
    model_version: str
    features_used: List[str]
    forecast_horizon: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class ForecastResult:
    """Result of forecasting operation"""
    forecasts: List[Forecast]
    model_performance: Dict[str, float]
    ensemble_weights: Dict[str, float]
    timestamp: datetime
    total_predictions: int
    average_confidence: float


class ForecastModel(ABC):
    """Abstract base class for forecast models"""
    
    def __init__(self, name: str, version: str = "1.0"):
        self.name = name
        self.version = version
        self.is_fitted = False
        self.feature_importance: Dict[str, float] = {}
    
    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Train the model"""
        pass
    
    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generate predictions"""
        pass
    
    @abstractmethod
    def predict_with_uncertainty(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Generate predictions with uncertainty estimates"""
        pass
    
    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance"""
        pass


class LinearForecastModel(ForecastModel):
    """Linear regression forecast model"""
    
    def __init__(self, l2_penalty: float = 0.01):
        super().__init__("linear_forecast", "1.0")
        self.l2_penalty = l2_penalty
        self.coefficients: Optional[Dict[str, float]] = None
        self.intercept: float = 0.0
        self.std_error: float = 0.0
    
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit linear regression with L2 regularization"""
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import StandardScaler
        
        X_clean = X.fillna(0)
        y_clean = y.fillna(0)
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_clean)
        
        model = Ridge(alpha=self.l2_penalty)
        model.fit(X_scaled, y_clean)
        
        self.coefficients = dict(zip(X.columns, model.coef_))
        self.intercept = model.intercept_
        
        # Calculate standard error of predictions
        predictions = model.predict(X_scaled)
        residuals = y_clean - predictions
        self.std_error = np.std(residuals)
        
        # Feature importance
        feature_stds = X_clean.std()
        self.feature_importance = {
            feature: abs(coef * feature_stds.get(feature, 1.0))
            for feature, coef in self.coefficients.items()
        }
        
        total_importance = sum(self.feature_importance.values())
        if total_importance > 0:
            self.feature_importance = {
                k: v / total_importance for k, v in self.feature_importance.items()
            }
        
        self.is_fitted = True
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generate predictions"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        X_clean = X.fillna(0)
        prediction = np.zeros(len(X_clean))
        
        for feature, coef in self.coefficients.items():
            if feature in X_clean.columns:
                prediction += coef * X_clean[feature].values
        
        prediction += self.intercept
        return prediction
    
    def predict_with_uncertainty(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Generate predictions with uncertainty (confidence intervals)"""
        predictions = self.predict(X)
        uncertainty = np.full(len(predictions), self.std_error)
        return predictions, uncertainty
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance"""
        return self.feature_importance


class RandomForestForecastModel(ForecastModel):
    """Random forest forecast model"""
    
    def __init__(self, n_estimators: int = 100, max_depth: int = 10):
        super().__init__("random_forest_forecast", "1.0")
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.model = None
    
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit random forest model"""
        from sklearn.ensemble import RandomForestRegressor
        
        X_clean = X.fillna(0)
        y_clean = y.fillna(0)
        
        self.model = RandomForestRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=42,
        )
        self.model.fit(X_clean, y_clean)
        
        # Feature importance
        self.feature_importance = dict(zip(
            X.columns,
            self.model.feature_importances_
        ))
        
        self.is_fitted = True
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generate predictions"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        X_clean = X.fillna(0)
        return self.model.predict(X_clean)
    
    def predict_with_uncertainty(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Generate predictions with uncertainty using bootstrap"""
        X_clean = X.fillna(0)
        
        # Get predictions from all trees
        predictions = np.array([tree.predict(X_clean) for tree in self.model.estimators_])
        
        # Mean prediction
        mean_prediction = predictions.mean(axis=0)
        
        # Uncertainty as std across trees
        uncertainty = predictions.std(axis=0)
        
        return mean_prediction, uncertainty
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance"""
        return self.feature_importance


class ModelEnsemble:
    """Ensemble of forecast models for robust predictions"""
    
    def __init__(self, models: List[ForecastModel] = None):
        self.models = models or []
        self.weights: Dict[str, float] = {}
        self.is_fitted = False
    
    def add_model(self, model: ForecastModel, weight: float = 1.0) -> None:
        """Add a model to the ensemble"""
        self.models.append(model)
        self.weights[model.name] = weight
    
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit all models in the ensemble"""
        for model in self.models:
            try:
                model.fit(X, y)
            except Exception as e:
                print(f"Error fitting model {model.name}: {e}")
        
        # Normalize weights
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            self.weights = {k: v / total_weight for k, v in self.weights.items()}
        else:
            # Equal weights if not specified
            self.weights = {model.name: 1.0 / len(self.models) for model in self.models}
        
        self.is_fitted = True
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generate ensemble predictions"""
        if not self.is_fitted:
            raise ValueError("Ensemble must be fitted before prediction")
        
        predictions = []
        for model in self.models:
            if model.is_fitted:
                pred = model.predict(X)
                weight = self.weights.get(model.name, 1.0)
                predictions.append(pred * weight)
        
        if predictions:
            return np.sum(predictions, axis=0)
        else:
            return np.zeros(len(X))
    
    def predict_with_uncertainty(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Generate ensemble predictions with uncertainty"""
        if not self.is_fitted:
            raise ValueError("Ensemble must be fitted before prediction")
        
        predictions = []
        uncertainties = []
        
        for model in self.models:
            if model.is_fitted:
                pred, unc = model.predict_with_uncertainty(X)
                weight = self.weights.get(model.name, 1.0)
                predictions.append(pred * weight)
                uncertainties.append(unc * weight)
        
        if predictions:
            mean_prediction = np.sum(predictions, axis=0)
            mean_uncertainty = np.sum(uncertainties, axis=0)
            return mean_prediction, mean_uncertainty
        else:
            return np.zeros(len(X)), np.zeros(len(X))
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get ensemble feature importance (weighted average)"""
        ensemble_importance = {}
        
        for model in self.models:
            if model.is_fitted:
                weight = self.weights.get(model.name, 1.0)
                model_importance = model.get_feature_importance()
                
                for feature, importance in model_importance.items():
                    if feature not in ensemble_importance:
                        ensemble_importance[feature] = 0.0
                    ensemble_importance[feature] += importance * weight
        
        return ensemble_importance


class ForecastEngine:
    """Main forecast engine for alpha predictions"""
    
    def __init__(self):
        self.ensemble = ModelEnsemble()
        self.forecast_history: List[Forecast] = []
        self._initialize_default_models()
    
    def _initialize_default_models(self):
        """Initialize default forecast models"""
        self.ensemble.add_model(LinearForecastModel(l2_penalty=0.01), weight=0.4)
        self.ensemble.add_model(RandomForestForecastModel(n_estimators=50, max_depth=8), weight=0.6)
    
    def train_forecast_models(
        self,
        features: pd.DataFrame,
        returns: pd.Series,
    ) -> bool:
        """Train forecast models on historical data"""
        try:
            self.ensemble.fit(features, returns)
            return True
        except Exception as e:
            print(f"Error training forecast models: {e}")
            return False
    
    def generate_forecasts(
        self,
        features: pd.DataFrame,
        symbols: List[str],
        timestamp: datetime,
        horizon: str = "1w",
        confidence_level: float = 0.95,
    ) -> List[Forecast]:
        """Generate forecasts for multiple symbols"""
        if not self.ensemble.is_fitted:
            raise ValueError("Forecast models must be trained before generating forecasts")
        
        # Generate predictions with uncertainty
        predictions, uncertainties = self.ensemble.predict_with_uncertainty(features)
        
        # Calculate confidence intervals
        z_score = stats.norm.ppf((1 + confidence_level) / 2)
        
        forecasts = []
        for i, symbol in enumerate(symbols):
            if i < len(predictions):
                pred = predictions[i]
                unc = uncertainties[i]
                
                # Confidence intervals
                ci_low = pred - z_score * unc
                ci_high = pred + z_score * unc
                
                # Confidence score (inverse of uncertainty)
                confidence = 1.0 / (1.0 + abs(unc))
                
                forecast = Forecast(
                    symbol=symbol,
                    timestamp=timestamp,
                    prediction=float(pred),
                    confidence_interval_low=float(ci_low),
                    confidence_interval_high=float(ci_high),
                    uncertainty=float(unc),
                    confidence=float(confidence),
                    model_name="ensemble",
                    model_version="1.0",
                    features_used=list(features.columns),
                    forecast_horizon=horizon,
                )
                
                forecasts.append(forecast)
                self.forecast_history.append(forecast)
        
        return forecasts
    
    def get_forecast_statistics(self) -> Dict[str, Any]:
        """Get statistics about forecasts"""
        if not self.forecast_history:
            return {}
        
        total_forecasts = len(self.forecast_history)
        avg_confidence = np.mean([f.confidence for f in self.forecast_history])
        avg_uncertainty = np.mean([f.uncertainty for f in self.forecast_history])
        
        model_weights = self.ensemble.weights
        feature_importance = self.ensemble.get_feature_importance()
        
        return {
            "total_forecasts": total_forecasts,
            "average_confidence": float(avg_confidence),
            "average_uncertainty": float(avg_uncertainty),
            "model_weights": model_weights,
            "feature_importance": feature_importance,
        }
