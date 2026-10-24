"""DELTA OS — Next-Concept Modeling (NCM) Package.

Institutional discrete financial concept space reasoning, native tensor acceleration,
and standardized multi-model benchmarking.
"""
from finance_model.ncm.contracts import (
    ConceptCategory,
    FinancialConcept,
    ConceptTransition,
    ConceptTrajectory,
    NCMGenerationRequest,
    NCMGenerationResult,
    NCMModelBenchmarkMetrics,
    NCMBenchmarkReport,
)
from finance_model.ncm.vocabulary import (
    CONCEPT_IDS,
    CONCEPT_VOCABULARY,
    get_concept,
    list_concepts,
    get_embedding_matrix,
    get_concept_index,
    get_transition_priors,
)
from finance_model.ncm.engine import NextConceptModel
from finance_model.ncm.benchmarking import NCMBenchmarkSuite

__all__ = [
    "ConceptCategory",
    "FinancialConcept",
    "ConceptTransition",
    "ConceptTrajectory",
    "NCMGenerationRequest",
    "NCMGenerationResult",
    "NCMModelBenchmarkMetrics",
    "NCMBenchmarkReport",
    "CONCEPT_IDS",
    "CONCEPT_VOCABULARY",
    "get_concept",
    "list_concepts",
    "get_embedding_matrix",
    "get_concept_index",
    "get_transition_priors",
    "NextConceptModel",
    "NCMBenchmarkSuite",
]
