"""Hidden Markov Model for regime detection."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from typing import Any


@dataclass(frozen=True, slots=True)
class HMMParameters:
    """Parameters for Hidden Markov Model."""
    n_states: int = 3  # Number of hidden states (regimes)
    n_observations: int = 5  # Number of observable features
    
    # Transition matrix: A[i,j] = P(state_j | state_i)
    transition_matrix: np.ndarray = None  # Will be initialized in __post_init__
    
    # Emission matrix: B[i,j] = P(observation_j | state_i)
    emission_matrix: np.ndarray = None  # Will be initialized in __post_init__
    
    # Initial state distribution
    initial_distribution: np.ndarray = None  # Will be initialized in __post_init__
    
    def __post_init__(self) -> None:
        """Initialize matrices with reasonable defaults."""
        if self.transition_matrix is None:
            # Initialize with uniform transitions
            object.__setattr__(
                self,
                "transition_matrix",
                np.ones((self.n_states, self.n_states)) / self.n_states
            )
        
        if self.emission_matrix is None:
            # Initialize with uniform emissions
            object.__setattr__(
                self,
                "emission_matrix",
                np.ones((self.n_states, self.n_observations)) / self.n_observations
            )
        
        if self.initial_distribution is None:
            # Initialize with uniform distribution
            object.__setattr__(
                self,
                "initial_distribution",
                np.ones(self.n_states) / self.n_states
            )


class HiddenMarkovModel:
    """
    Hidden Markov Model for regime detection.
    
    Models market regimes as hidden states with observable features
    (volatility, liquidity, trend, etc.) as emissions.
    """
    
    def __init__(self, params: HMMParameters) -> None:
        self._params = params
        self._n_states = params.n_states
        self._n_observations = params.n_observations
    
    def forward_algorithm(self, observations: np.ndarray) -> np.ndarray:
        """
        Forward algorithm for computing forward probabilities.
        
        α_t(i) = P(O_1, ..., O_t, q_t = S_i | λ)
        """
        T = len(observations)
        alpha = np.zeros((T, self._n_states))
        
        # Initialization
        alpha[0] = self._params.initial_distribution * self._params.emission_matrix[:, observations[0]]
        
        # Induction
        for t in range(1, T):
            for j in range(self._n_states):
                alpha[t, j] = self._params.emission_matrix[j, observations[t]] * np.sum(
                    alpha[t-1] * self._params.transition_matrix[:, j]
                )
        
        return alpha
    
    def backward_algorithm(self, observations: np.ndarray) -> np.ndarray:
        """
        Backward algorithm for computing backward probabilities.
        
        β_t(i) = P(O_{t+1}, ..., O_T | q_t = S_i, λ)
        """
        T = len(observations)
        beta = np.zeros((T, self._n_states))
        
        # Initialization
        beta[T-1] = 1.0
        
        # Induction
        for t in range(T-2, -1, -1):
            for i in range(self._n_states):
                beta[t, i] = np.sum(
                    self._params.transition_matrix[i, :] *
                    self._params.emission_matrix[:, observations[t+1]] *
                    beta[t+1]
                )
        
        return beta
    
    def viterbi(self, observations: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Viterbi algorithm for most likely state sequence.
        
        Returns (state_sequence, probability_sequence)
        """
        T = len(observations)
        delta = np.zeros((T, self._n_states))
        psi = np.zeros((T, self._n_states), dtype=int)
        
        # Initialization
        delta[0] = self._params.initial_distribution * self._params.emission_matrix[:, observations[0]]
        psi[0] = 0
        
        # Recursion
        for t in range(1, T):
            for j in range(self._n_states):
                max_val = -np.inf
                max_state = 0
                
                for i in range(self._n_states):
                    val = delta[t-1, i] * self._params.transition_matrix[i, j]
                    if val > max_val:
                        max_val = val
                        max_state = i
                
                delta[t, j] = max_val * self._params.emission_matrix[j, observations[t]]
                psi[t, j] = max_state
        
        # Termination
        state_sequence = np.zeros(T, dtype=int)
        state_sequence[T-1] = np.argmax(delta[T-1])
        
        # Backtracking
        for t in range(T-2, -1, -1):
            state_sequence[t] = psi[t+1, state_sequence[t+1]]
        
        return state_sequence, delta
    
    def baum_welch(self, observations: np.ndarray, max_iter: int = 100) -> HMMParameters:
        """
        Baum-Welch algorithm for parameter estimation.
        
        Estimates transition and emission matrices from observations.
        """
        T = len(observations)
        
        for iteration in range(max_iter):
            # E-step: compute forward and backward probabilities
            alpha = self.forward_algorithm(observations)
            beta = self.backward_algorithm(observations)
            
            # Compute gamma and xi
            gamma = np.zeros((T, self._n_states))
            xi = np.zeros((T-1, self._n_states, self._n_states))
            
            for t in range(T):
                gamma[t] = alpha[t] * beta[t]
                gamma[t] /= np.sum(gamma[t])
            
            for t in range(T-1):
                for i in range(self._n_states):
                    for j in range(self._n_states):
                        xi[t, i, j] = (
                            alpha[t, i] *
                            self._params.transition_matrix[i, j] *
                            self._params.emission_matrix[j, observations[t+1]] *
                            beta[t+1, j]
                        )
                xi[t] /= np.sum(xi[t])
            
            # M-step: update parameters
            # Update initial distribution
            self._params.initial_distribution = gamma[0]
            
            # Update transition matrix
            for i in range(self._n_states):
                denominator = np.sum(gamma[:-1, i])
                if denominator > 0:
                    self._params.transition_matrix[i] = np.sum(xi[:, i, :], axis=0) / denominator
            
            # Update emission matrix
            for j in range(self._n_states):
                for k in range(self._n_observations):
                    numerator = np.sum(gamma[observations == k, j])
                    denominator = np.sum(gamma[:, j])
                    if denominator > 0:
                        self._params.emission_matrix[j, k] = numerator / denominator
        
        return self._params
