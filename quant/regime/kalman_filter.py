"""
Kalman Filter for State-Space Regime Detection.

This module implements Kalman filtering for:
- Dynamic state estimation
- Latent regime detection
- State-space models
- Real-time regime tracking
- Uncertainty quantification

Kalman filters are optimal for linear Gaussian state-space models
and provide recursive estimation with minimal computational cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, List, Tuple, Union
import numpy as np
from scipy.linalg import inv, cholesky


@dataclass(frozen=True, slots=True)
class KalmanParameters:
    """
    Parameters for Kalman filter.
    
    State-space model:
    x_t = F * x_{t-1} + B * u_t + w_t  (state transition)
    z_t = H * x_t + v_t                  (observation)
    
    where:
    - w_t ~ N(0, Q) is process noise
    - v_t ~ N(0, R) is measurement noise
    """
    n_states: int  # Number of state variables
    n_observations: int  # Number of observation variables
    
    # State transition matrix (F)
    state_transition: np.ndarray = None  # Will be initialized in __post_init__
    
    # Control input matrix (B)
    control_matrix: np.ndarray = None  # Will be initialized in __post_init__
    
    # Observation matrix (H)
    observation_matrix: np.ndarray = None  # Will be initialized in __post_init__
    
    # Process noise covariance (Q)
    process_noise_cov: np.ndarray = None  # Will be initialized in __post_init__
    
    # Measurement noise covariance (R)
    measurement_noise_cov: np.ndarray = None  # Will be initialized in __post_init__
    
    # Initial state mean (x0)
    initial_state_mean: np.ndarray = None  # Will be initialized in __post_init__
    
    # Initial state covariance (P0)
    initial_state_cov: np.ndarray = None  # Will be initialized in __post_init__
    
    def __post_init__(self) -> None:
        """Initialize matrices with reasonable defaults."""
        # Initialize state transition matrix (random walk by default)
        if self.state_transition is None:
            object.__setattr__(
                self,
                "state_transition",
                np.eye(self.n_states)
            )
        
        # Initialize control matrix (no control by default)
        if self.control_matrix is None:
            object.__setattr__(
                self,
                "control_matrix",
                np.zeros((self.n_states, 1))
            )
        
        # Initialize observation matrix (identity by default)
        if self.observation_matrix is None:
            object.__setattr__(
                self,
                "observation_matrix",
                np.eye(self.n_observations, self.n_states)
            )
        
        # Initialize process noise covariance
        if self.process_noise_cov is None:
            object.__setattr__(
                self,
                "process_noise_cov",
                np.eye(self.n_states) * 0.01
            )
        
        # Initialize measurement noise covariance
        if self.measurement_noise_cov is None:
            object.__setattr__(
                self,
                "measurement_noise_cov",
                np.eye(self.n_observations) * 0.1
            )
        
        # Initialize initial state mean
        if self.initial_state_mean is None:
            object.__setattr__(
                self,
                "initial_state_mean",
                np.zeros(self.n_states)
            )
        
        # Initialize initial state covariance
        if self.initial_state_cov is None:
            object.__setattr__(
                self,
                "initial_state_cov",
                np.eye(self.n_states)
            )


@dataclass
class KalmanState:
    """
    Current state of Kalman filter.
    
    Attributes:
        state_mean: Current state estimate (x)
        state_cov: Current state covariance (P)
        timestamp: Current timestamp
    """
    state_mean: np.ndarray
    state_cov: np.ndarray
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def state_std(self) -> np.ndarray:
        """Standard deviation of state estimate."""
        return np.sqrt(np.diag(self.state_cov))


class KalmanFilter:
    """
    Kalman filter for state-space regime detection.
    
    Features:
    - Recursive state estimation
    - Prediction and update steps
    - Real-time regime tracking
    - Uncertainty quantification
    - Missing data handling
    """
    
    def __init__(self, params: KalmanParameters) -> None:
        """
        Initialize Kalman filter.
        
        Args:
            params: Kalman filter parameters
        """
        self._params = params
        self._n_states = params.n_states
        self._n_observations = params.n_observations
        
        # Initialize state
        self._state = KalmanState(
            state_mean=params.initial_state_mean.copy(),
            state_cov=params.initial_state_cov.copy()
        )
        
        # Store history for analysis
        self._history: List[KalmanState] = []
    
    def predict(
        self,
        control_input: Optional[np.ndarray] = None
    ) -> KalmanState:
        """
        Prediction step.
        
        Args:
            control_input: Control input (u_t)
            
        Returns:
            Predicted state
        """
        # State prediction: x_pred = F * x + B * u
        if control_input is None:
            control_input = np.zeros(1)
        
        predicted_mean = (
            self._params.state_transition @ self._state.state_mean +
            self._params.control_matrix @ control_input
        )
        
        # Covariance prediction: P_pred = F * P * F' + Q
        predicted_cov = (
            self._params.state_transition @ self._state.state_cov @
            self._params.state_transition.T +
            self._params.process_noise_cov
        )
        
        # Create predicted state
        predicted_state = KalmanState(
            state_mean=predicted_mean,
            state_cov=predicted_cov,
            timestamp=datetime.now(timezone.utc)
        )
        
        return predicted_state
    
    def update(
        self,
        observation: np.ndarray,
        predicted_state: Optional[KalmanState] = None
    ) -> KalmanState:
        """
        Update step.
        
        Args:
            observation: Observation (z_t)
            predicted_state: Predicted state (if None, uses current state)
            
        Returns:
            Updated state
        """
        if predicted_state is None:
            predicted_state = self.predict()
        
        # Innovation: y = z - H * x_pred
        innovation = observation - self._params.observation_matrix @ predicted_state.state_mean
        
        # Innovation covariance: S = H * P_pred * H' + R
        innovation_cov = (
            self._params.observation_matrix @ predicted_state.state_cov @
            self._params.observation_matrix.T +
            self._params.measurement_noise_cov
        )
        
        # Kalman gain: K = P_pred * H' * S^-1
        kalman_gain = (
            predicted_state.state_cov @
            self._params.observation_matrix.T @
            inv(innovation_cov)
        )
        
        # State update: x = x_pred + K * y
        updated_mean = predicted_state.state_mean + kalman_gain @ innovation
        
        # Covariance update: P = (I - K * H) * P_pred
        updated_cov = (
            (np.eye(self._n_states) - kalman_gain @ self._params.observation_matrix) @
            predicted_state.state_cov
        )
        
        # Update state
        self._state = KalmanState(
            state_mean=updated_mean,
            state_cov=updated_cov,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Store history
        self._history.append(self._state)
        
        return self._state
    
    def filter_sequence(
        self,
        observations: np.ndarray,
        control_inputs: Optional[np.ndarray] = None
    ) -> List[KalmanState]:
        """
        Filter a sequence of observations.
        
        Args:
            observations: Sequence of observations (T x n_observations)
            control_inputs: Sequence of control inputs (T x n_controls)
            
        Returns:
            List of filtered states
        """
        states = []
        
        for t, obs in enumerate(observations):
            # Predict
            control = control_inputs[t] if control_inputs is not None else None
            predicted = self.predict(control)
            
            # Update
            updated = self.update(obs, predicted)
            states.append(updated)
        
        return states
    
    def smooth_sequence(
        self,
        observations: np.ndarray
    ) -> List[KalmanState]:
        """
        Rauch-Tung-Striebel (RTS) smoother for offline smoothing.
        
        Args:
            observations: Sequence of observations
            
        Returns:
            List of smoothed states
        """
        # Forward pass (standard Kalman filter)
        forward_states = self.filter_sequence(observations)
        
        # Backward pass (RTS smoother)
        smoothed_states = []
        
        for i in range(len(forward_states) - 1, -1, -1):
            if i == len(forward_states) - 1:
                # Last state is already smoothed
                smoothed_states.append(forward_states[i])
            else:
                # RTS smoothing equations
                current_state = forward_states[i]
                next_state = forward_states[i + 1]
                next_smoothed = smoothed_states[-1]
                
                # Smoothing gain
                C = (
                    current_state.state_cov @
                    self._params.state_transition.T @
                    inv(next_state.state_cov)
                )
                
                # Smoothed state
                smoothed_mean = (
                    current_state.state_mean +
                    C @ (next_smoothed.state_mean - next_state.state_mean)
                )
                
                # Smoothed covariance
                smoothed_cov = (
                    current_state.state_cov +
                    C @ (next_smoothed.state_cov - next_state.state_cov) @ C.T
                )
                
                smoothed_states.append(KalmanState(
                    state_mean=smoothed_mean,
                    state_cov=smoothed_cov,
                    timestamp=current_state.timestamp
                ))
        
        return smoothed_states[::-1]  # Reverse to get chronological order
    
    def get_regime_probability(
        self,
        state_index: int,
        threshold: float = 0.0
    ) -> float:
        """
        Get probability of being in a specific regime.
        
        Args:
            state_index: Index of state variable
            threshold: Threshold for regime classification
            
        Returns:
            Probability of regime
        """
        if state_index >= self._n_states:
            return 0.0
        
        state_value = self._state.state_mean[state_index]
        state_std = self._state.state_std[state_index]
        
        # Calculate probability using Gaussian CDF
        from scipy.stats import norm
        probability = 1.0 - norm.cdf(threshold, loc=state_value, scale=state_std)
        
        return probability
    
    def get_state_history(self) -> List[KalmanState]:
        """Get state history."""
        return self._history
    
    def reset(self) -> None:
        """Reset filter to initial state."""
        self._state = KalmanState(
            state_mean=self._params.initial_state_mean.copy(),
            state_cov=self._params.initial_state_cov.copy()
        )
        self._history.clear()


__all__ = [
    "KalmanParameters",
    "KalmanState",
    "KalmanFilter",
]
