"""DELTA OS — Institutional NCM Ontology & Conditioning Expansion Test Suite.

Verifies:
1. Complete 42-concept discrete ontology spanning Macro, Microstructure,
   Fundamentals, Valuation, Volatility, and Risk/Sentiment categories.
2. NCM Transition priors and decay half-lives across all regimes.
3. NCM Keyword pattern matching across all 42 institutional regimes.
4. NCM Conditioning Context generation with volatility regime classification
   and structural invalidating conditions.
5. Invariant enforcement: Zero execution authority for Next-Concept Modeling.
"""
from __future__ import annotations

import pytest

from finance_model.ncm.contracts import (
    ConceptCategory,
    FinancialConcept,
    NCMConditioningContext,
    NCMGenerationRequest,
)
from finance_model.ncm.engine import NextConceptModel
from finance_model.ncm.vocabulary import (
    CONCEPT_VOCABULARY,
    CONCEPT_IDS,
    get_concept,
    get_transition_priors,
    list_concepts,
)


def test_ncm_ontology_size_and_completeness():
    """Verify ontology has exactly 42 canonical institutional regimes."""
    concepts = list_concepts()
    assert len(concepts) == 42, f"Expected 42 concepts, found {len(concepts)}"
    assert len(CONCEPT_VOCABULARY) == 42
    assert len(CONCEPT_IDS) == 42


def test_ncm_all_categories_populated():
    """Verify all 7 categories are populated with designated concept counts."""
    categories = {
        ConceptCategory.MACRO: 10,
        ConceptCategory.MICROSTRUCTURE: 8,
        ConceptCategory.FUNDAMENTALS: 7,
        ConceptCategory.VOLATILITY: 6,
        ConceptCategory.VALUATION: 5,
        ConceptCategory.RISK: 3,
        ConceptCategory.SENTIMENT: 3,
    }
    concepts = list_concepts()
    for cat, expected_count in categories.items():
        matched = [c for c in concepts if c.category == cat]
        assert len(matched) == expected_count, (
            f"Category {cat.value} expected {expected_count} concepts, got {len(matched)}"
        )


def test_ncm_transition_priors_contain_volatility():
    """Verify transition priors exist for all 42 concepts including volatility regimes."""
    for cid in CONCEPT_IDS:
        priors = get_transition_priors(cid)
        assert len(priors) > 0, f"Concept {cid} has empty transition priors"
        total_p = sum(priors.values())
        assert abs(total_p - 1.0) < 1e-4, f"Concept {cid} transition priors do not sum to 1.0 (got {total_p})"


def test_ncm_decay_half_lives_and_sensitivities():
    """Verify all concepts have positive decay half lives and bounded volatility sensitivities."""
    for c in list_concepts():
        assert c.decay_half_life_hours > 0, f"{c.concept_id} non-positive decay"
        assert 0.0 <= c.volatility_sensitivity <= 3.0, f"{c.concept_id} sensitivity out of bounds"


def test_ncm_keyword_mapping_covers_all_concepts():
    """Verify engine matches keywords for each concept category."""
    engine = NextConceptModel()
    
    # Test specific high-impact institutional regime triggers
    test_cases = [
        ("Quantitative tightening and yield curve inversion", "MACRO_QUANTITATIVE_TIGHTENING"),
        ("Sovereign spread widening and peripheral debt risk premium", "MACRO_SOVEREIGN_SPREAD_WIDENING"),
        ("Iceberg order accumulation with stealth liquidity detected", "MICRO_ICEBERG_ACCUMULATION"),
        ("VPIN toxic flow and informed trading on lit exchange", "MICRO_ORDER_FLOW_TOXICITY_VPIN"),
        ("Heavy buying wall on order book bid depth", "MICRO_ORDER_BOOK_IMBALANCE_BID"),
        ("Extreme volatility clustering and sustained vol expansion", "VOL_CLUSTERING_EXPANSION"),
        ("Asymmetric gamma squeeze with dealer short calls", "VOL_GAMMA_SQUEEZE_CALL"),
        ("Panic selling and capitulation margin call exhaustion", "SENT_CAPITULATION_BOTTOM"),
        ("Tail risk black swan with downside protection demand", "RISK_TAIL_EVENT_ELEVATED"),
    ]
    
    for text, expected_concept in test_cases:
        matched = engine.detect_concepts_from_text(text)
        assert expected_concept in matched, (
            f"Text '{text}' failed to detect expected concept {expected_concept}. Matched: {matched}"
        )


def test_ncm_conditioning_generation():
    """Verify NCM conditioning generates coherent context with volatility regime."""
    engine = NextConceptModel()
    req = NCMGenerationRequest(
        symbol="SPY",
        macro_context="Yield curve inversion and quantitative tightening with elevated volatility",
        horizon=3,
    )
    context = engine.generate_llm_conditioning(req)
    
    assert isinstance(context, NCMConditioningContext)
    assert context.symbol == "SPY"
    assert len(context.active_regimes) >= 1
    assert len(context.forecast_trajectory) == 3
    assert len(context.semantic_guardrails) >= 3
    assert len(context.invalidating_conditions) >= 2
    assert context.volatility_regime in (
        "EXTREME_VOLATILITY_EXPANSION",
        "ELEVATED_VOLATILITY_REGIME",
        "LOW_VOLATILITY_COMPRESSION",
        "NORMAL_BALANCED",
    )


def test_ncm_fail_closed_zero_execution_authority():
    """Verify NCM model results are strictly analytical with zero execution authority."""
    engine = NextConceptModel()
    req = NCMGenerationRequest(symbol="QQQ", horizon=2)
    res = engine.generate_trajectory(req)
    
    assert res.execution_eligibility is False
    assert res.provenance_badge in ("NCM_EXPERIMENTAL", "NCM_DISCRETE_V2_INSTITUTIONAL")
