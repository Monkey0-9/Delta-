"""DELTA OS — Next-Concept Modeling (NCM) Formal Domain Contracts.

Institutional contracts defining discrete financial concepts, conceptual trajectories,
generation requests, experimental results, and standardized multi-model benchmark reporting.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field


class ConceptCategory(StrEnum):
    MACRO = "macro"
    MICROSTRUCTURE = "microstructure"
    FUNDAMENTALS = "fundamentals"
    VALUATION = "valuation"
    VOLATILITY = "volatility"
    RISK = "risk"
    SENTIMENT = "sentiment"


class FinancialConcept(BaseModel):
    """Atomic latent financial concept representing a discrete structural market state."""
    model_config = ConfigDict(extra="forbid")

    concept_id: str = Field(min_length=1)
    category: ConceptCategory
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    embedding: List[float] = Field(min_length=4)
    decay_half_life_hours: float = Field(gt=0.0)
    volatility_sensitivity: float = Field(ge=0.0, le=2.0)


class ConceptTransition(BaseModel):
    """Directed transition probability from one concept to the next."""
    model_config = ConfigDict(extra="forbid")

    from_concept_id: str
    to_concept_id: str
    probability: float = Field(ge=0.0, le=1.0)
    evidence_score: float = Field(ge=0.0, le=1.0)


class ConceptTrajectory(BaseModel):
    """Sequenced multi-step conceptual progression with predictive likelihoods and uncertainty."""
    model_config = ConfigDict(extra="forbid")

    trajectory_id: str
    symbol: str
    observed_concepts: List[str]
    predicted_concepts: List[Tuple[str, float]]  # (concept_id, probability)
    horizon_steps: int = Field(ge=1, le=10)
    entropy: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    created_at_utc: str


class NCMGenerationRequest(BaseModel):
    """Input payload for Next-Concept generation."""
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    macro_context: str = ""
    news_headlines: List[str] = Field(default_factory=list)
    quant_metrics: Dict[str, float] = Field(default_factory=dict)
    horizon: int = Field(default=3, ge=1, le=10)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_k: int = Field(default=5, ge=1, le=20)


class NCMGenerationResult(BaseModel):
    """Institutional Next-Concept reasoning output.
    
    NON-NEGOTIABLE SAFETY INVARIANT:
    execution_eligibility is ALWAYS False. NCM is an analytical/synthesis tool
    and has NO authority to set risk limits or execute broker orders.
    """
    model_config = ConfigDict(extra="forbid")

    symbol: str
    model_version: str = "ncm-fin-v1.0-institutional"
    provenance_badge: str = "NCM_EXPERIMENTAL"
    trajectory: ConceptTrajectory
    synthesized_thesis: str
    invalidating_conditions: List[str]
    execution_eligibility: bool = False
    hardware_acceleration: str = "numpy"  # "rust" or "numpy"


class NCMModelBenchmarkMetrics(BaseModel):
    """Measured benchmark performance metrics across 10 institutional dimensions."""
    model_config = ConfigDict(extra="forbid")

    model_name: str
    model_type: str  # "NCM", "LLM", "SLM", "NO_MODEL"
    factuality_score: float = Field(ge=0.0, le=1.0)
    source_coverage_score: float = Field(ge=0.0, le=1.0)
    omission_rate: float = Field(ge=0.0, le=1.0)
    hallucination_rate: float = Field(ge=0.0, le=1.0)
    schema_validity_score: float = Field(ge=0.0, le=1.0)
    prompt_injection_resistance: float = Field(ge=0.0, le=1.0)
    latency_p50_us: float = Field(ge=0.0)
    latency_p95_us: float = Field(ge=0.0)
    latency_p99_us: float = Field(ge=0.0)
    ram_mb: float = Field(ge=0.0)
    cost_per_1k_queries_usd: float = Field(ge=0.0)
    safety_violation_count: int = 0


class NCMConditioningContext(BaseModel):
    """Priors passed into Financial LLM reasoning to bound search space.
    
    Prevents token-drift and macroeconomic hallucination by grounding the LLM
    in discrete, mathematically verified regime trajectories.
    """
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    active_regimes: List[str]
    forecast_trajectory: List[Tuple[str, float]]  # (concept_id, probability)
    systemic_entropy: float = Field(ge=0.0)
    volatility_regime: str = "NORMAL"
    invalidating_conditions: List[str] = Field(default_factory=list)
    semantic_guardrails: List[str] = Field(default_factory=list)


class CrisisReplayScenario(BaseModel):
    """Historical market crisis scenario for stress-testing and benchmark replays."""
    model_config = ConfigDict(extra="forbid")

    crisis_id: str
    name: str
    historical_date: str
    macro_backdrop: str
    microstructure_state: str
    expected_concept_activations: List[str]
    forbidden_claims: List[str]  # Statements that would violate truth/lookahead


class NCMBenchmarkReport(BaseModel):
    """Comparative benchmark report across NCM, LLM, SLM, and No-Model baselines."""
    model_config = ConfigDict(extra="forbid")

    report_id: str
    timestamp_utc: str
    total_samples: int
    winner_for_latency: str
    winner_for_factuality: str
    winner_for_cost: str
    models: Dict[str, NCMModelBenchmarkMetrics]
    safety_verdict: str = "COMPLIANT_ZERO_EXECUTION_AUTHORITY"
