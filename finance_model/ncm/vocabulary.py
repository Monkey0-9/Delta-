"""DELTA OS — Next-Concept Modeling (NCM) Concept Ontology & Vocabulary.

Defines the canonical discrete financial concept vocabulary spanning Macro,
Microstructure, Fundamentals, Valuation, Risk, and Sentiment domains.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple
import numpy as np

from finance_model.ncm.contracts import ConceptCategory, FinancialConcept


# Canonical Concept Definitions with pinned orthogonal-basis concept embeddings (dim=8)
_RAW_CONCEPTS: List[Dict] = [
    # 1. Macro Concepts
    {
        "concept_id": "MACRO_INFLATION_SURGE",
        "category": ConceptCategory.MACRO,
        "name": "Inflation Acceleration",
        "description": "Headline and core inflation measures expanding faster than consensus expectations.",
        "embedding": [0.8, 0.2, -0.4, 0.1, 0.6, 0.1, 0.2, 0.0],
        "decay_half_life_hours": 168.0,
        "volatility_sensitivity": 0.85,
    },
    {
        "concept_id": "MACRO_RATE_HIKE_CYCLE",
        "category": ConceptCategory.MACRO,
        "name": "Monetary Tightening",
        "description": "Central bank actively raising policy rates or signaling hawkish forward guidance.",
        "embedding": [0.7, 0.5, -0.5, 0.0, 0.4, 0.2, 0.1, 0.0],
        "decay_half_life_hours": 336.0,
        "volatility_sensitivity": 0.90,
    },
    {
        "concept_id": "MACRO_RATE_CUT_EXPECTED",
        "category": ConceptCategory.MACRO,
        "name": "Monetary Easing",
        "description": "Forward curve pricing aggressive rate cuts due to slowing growth or cooling inflation.",
        "embedding": [-0.6, -0.4, 0.5, 0.2, -0.3, -0.2, -0.1, 0.1],
        "decay_half_life_hours": 240.0,
        "volatility_sensitivity": 0.70,
    },
    {
        "concept_id": "MACRO_RECESSIONARY_DRAG",
        "category": ConceptCategory.MACRO,
        "name": "Economic Contraction",
        "description": "Broad macroeconomic slowdown signaled by negative GDP revisions and declining PMIs.",
        "embedding": [-0.8, -0.6, 0.2, -0.4, 0.3, -0.5, 0.1, -0.2],
        "decay_half_life_hours": 504.0,
        "volatility_sensitivity": 1.20,
    },
    {
        "concept_id": "MACRO_LIQUIDITY_EXPANSION",
        "category": ConceptCategory.MACRO,
        "name": "Central Bank Balance Sheet Expansion",
        "description": "Surplus systemic bank reserves and expanding central bank balance sheet fueling asset multiples.",
        "embedding": [-0.3, 0.8, 0.6, 0.5, -0.5, 0.3, -0.2, 0.4],
        "decay_half_life_hours": 336.0,
        "volatility_sensitivity": 0.50,
    },
    {
        "concept_id": "MACRO_YIELD_CURVE_INVERSION",
        "category": ConceptCategory.MACRO,
        "name": "10Y-2Y Yield Curve Inversion",
        "description": "Short-term sovereign yields exceeding long-term benchmark yields signaling recession probability.",
        "embedding": [0.5, -0.3, -0.6, -0.2, 0.8, -0.4, 0.3, -0.1],
        "decay_half_life_hours": 720.0,
        "volatility_sensitivity": 1.10,
    },
    {
        "concept_id": "MACRO_QUANTITATIVE_TIGHTENING",
        "category": ConceptCategory.MACRO,
        "name": "Balance Sheet Runoff / QT",
        "description": "Central bank actively reducing bond holdings, draining excess liquidity from commercial banking.",
        "embedding": [0.6, 0.4, -0.5, -0.3, 0.5, 0.1, -0.2, -0.3],
        "decay_half_life_hours": 360.0,
        "volatility_sensitivity": 0.95,
    },
    {
        "concept_id": "MACRO_YIELD_CURVE_STEEPENING",
        "category": ConceptCategory.MACRO,
        "name": "Curve Steepener Dislocation",
        "description": "Long-term rates rising significantly faster than short rates reflecting term premium expansion.",
        "embedding": [0.4, 0.1, -0.3, 0.4, 0.2, -0.2, 0.5, 0.1],
        "decay_half_life_hours": 480.0,
        "volatility_sensitivity": 0.80,
    },
    {
        "concept_id": "MACRO_SOVEREIGN_SPREAD_WIDENING",
        "category": ConceptCategory.MACRO,
        "name": "Sovereign Debt Risk Premium",
        "description": "Peripheral or emerging sovereign yield spreads widening sharply against benchmark reference bonds.",
        "embedding": [0.3, -0.5, -0.6, -0.5, 0.7, -0.6, 0.2, -0.4],
        "decay_half_life_hours": 240.0,
        "volatility_sensitivity": 1.35,
    },
    {
        "concept_id": "MACRO_DOLLAR_LIQUIDITY_SQUEEZE",
        "category": ConceptCategory.MACRO,
        "name": "Global USD Funding Squeeze",
        "description": "Cross-currency basis swaps widening as global entities scramble for US dollar liquidity.",
        "embedding": [0.5, -0.4, -0.7, -0.6, 0.8, -0.5, 0.1, -0.5],
        "decay_half_life_hours": 120.0,
        "volatility_sensitivity": 1.45,
    },

    # 2. Microstructure Concepts
    {
        "concept_id": "MICRO_ORDER_BOOK_IMBALANCE_BID",
        "category": ConceptCategory.MICROSTRUCTURE,
        "name": "Bid-Side Depth Accumulation",
        "description": "Heavy institutional limit order absorption and liquidity depth skewed heavily on bid levels.",
        "embedding": [0.1, 0.7, 0.3, 0.8, -0.2, 0.4, 0.0, 0.5],
        "decay_half_life_hours": 4.0,
        "volatility_sensitivity": 0.40,
    },
    {
        "concept_id": "MICRO_ORDER_BOOK_IMBALANCE_ASK",
        "category": ConceptCategory.MICROSTRUCTURE,
        "name": "Ask-Side Supply Pressure",
        "description": "Persistent selling pressure and heavy limit supply blocking upward price progression.",
        "embedding": [-0.2, -0.7, -0.4, -0.8, 0.3, -0.4, 0.1, -0.5],
        "decay_half_life_hours": 4.0,
        "volatility_sensitivity": 0.50,
    },
    {
        "concept_id": "MICRO_SPREAD_COMPRESSION",
        "category": ConceptCategory.MICROSTRUCTURE,
        "name": "Spread Compression",
        "description": "Tight continuous quoting spreads indicating peak intraday market liquidity and stable quoting.",
        "embedding": [0.0, 0.3, 0.2, 0.6, -0.4, 0.1, -0.1, 0.3],
        "decay_half_life_hours": 2.0,
        "volatility_sensitivity": 0.20,
    },
    {
        "concept_id": "MICRO_LIQUIDITY_VACUUM",
        "category": ConceptCategory.MICROSTRUCTURE,
        "name": "Liquidity Void / Flash Gap",
        "description": "Thinning book depth and widening spreads creating elevated slippage and gap vulnerability.",
        "embedding": [-0.4, -0.5, -0.2, -0.6, 0.7, -0.6, 0.4, -0.3],
        "decay_half_life_hours": 1.5,
        "volatility_sensitivity": 1.60,
    },
    {
        "concept_id": "MICRO_ORDER_FLOW_TOXICITY_VPIN",
        "category": ConceptCategory.MICROSTRUCTURE,
        "name": "Informed Toxic Order Flow / VPIN Spike",
        "description": "Volume-synchronized probability of toxicity indicating aggressive informed order flow executing.",
        "embedding": [-0.3, -0.6, -0.5, -0.7, 0.8, -0.7, 0.3, -0.4],
        "decay_half_life_hours": 1.0,
        "volatility_sensitivity": 1.70,
    },
    {
        "concept_id": "MICRO_ICEBERG_ACCUMULATION",
        "category": ConceptCategory.MICROSTRUCTURE,
        "name": "Hidden Iceberg Order Accumulation",
        "description": "Persistent native limit replenishment executing substantial hidden size without moving quote.",
        "embedding": [0.2, 0.5, 0.4, 0.7, -0.3, 0.5, 0.1, 0.6],
        "decay_half_life_hours": 3.0,
        "volatility_sensitivity": 0.30,
    },
    {
        "concept_id": "MICRO_ADVERSE_SELECTION_SPIKE",
        "category": ConceptCategory.MICROSTRUCTURE,
        "name": "Adverse Selection Risk Elevation",
        "description": "Passive fills immediately followed by unfavorable price moves against market maker inventory.",
        "embedding": [-0.2, -0.4, -0.3, -0.5, 0.6, -0.5, 0.2, -0.3],
        "decay_half_life_hours": 1.5,
        "volatility_sensitivity": 1.40,
    },
    {
        "concept_id": "MICRO_CANCEL_REPLACE_CASCADE",
        "category": ConceptCategory.MICROSTRUCTURE,
        "name": "High-Frequency Cancel/Replace Wave",
        "description": "Extreme quoting flicker with cancel-to-fill ratios exceeding 100:1 as algorithmic quotes re-peg.",
        "embedding": [0.0, -0.3, -0.2, -0.4, 0.5, -0.3, 0.4, -0.2],
        "decay_half_life_hours": 0.5,
        "volatility_sensitivity": 1.30,
    },

    # 3. Fundamentals Concepts
    {
        "concept_id": "FUND_EARNINGS_ACCELERATION",
        "category": ConceptCategory.FUNDAMENTALS,
        "name": "EPS Growth Acceleration",
        "description": "Quarterly operating earnings growth beating prior rate of change and analyst expectations.",
        "embedding": [0.3, 0.6, 0.8, 0.4, -0.3, 0.5, 0.2, 0.4],
        "decay_half_life_hours": 720.0,
        "volatility_sensitivity": 0.60,
    },
    {
        "concept_id": "FUND_EARNINGS_CONTRACTION",
        "category": ConceptCategory.FUNDAMENTALS,
        "name": "Margin & Earnings Deterioration",
        "description": "Compressed operating margins and negative earnings revisions across forward guidance.",
        "embedding": [-0.5, -0.6, -0.7, -0.4, 0.4, -0.6, -0.2, -0.4],
        "decay_half_life_hours": 720.0,
        "volatility_sensitivity": 0.95,
    },
    {
        "concept_id": "FUND_CASH_FLOW_SURPLUS",
        "category": ConceptCategory.FUNDAMENTALS,
        "name": "Free Cash Flow Inflection",
        "description": "High free cash flow conversion yield enabling debt reduction, share buybacks, and dividend safety.",
        "embedding": [0.2, 0.4, 0.7, 0.3, -0.4, 0.4, 0.3, 0.2],
        "decay_half_life_hours": 1080.0,
        "volatility_sensitivity": 0.35,
    },
    {
        "concept_id": "FUND_DEBT_ROLLOVER_CLIFF",
        "category": ConceptCategory.FUNDAMENTALS,
        "name": "Debt Refinancing Cliff Risk",
        "description": "Significant portion of enterprise debt maturing in near term under higher prevailing interest rates.",
        "embedding": [-0.6, -0.5, -0.8, -0.5, 0.7, -0.7, -0.1, -0.5],
        "decay_half_life_hours": 1440.0,
        "volatility_sensitivity": 1.25,
    },
    {
        "concept_id": "FUND_WORKING_CAPITAL_STRAIN",
        "category": ConceptCategory.FUNDAMENTALS,
        "name": "Working Capital Bloat / Cash Burn",
        "description": "Ballooning inventory and days sales outstanding (DSO) draining liquid operating reserves.",
        "embedding": [-0.4, -0.3, -0.6, -0.3, 0.5, -0.5, -0.1, -0.3],
        "decay_half_life_hours": 720.0,
        "volatility_sensitivity": 0.85,
    },
    {
        "concept_id": "FUND_SOLVENCY_DETERIORATION",
        "category": ConceptCategory.FUNDAMENTALS,
        "name": "Altman Z-Score Solvency Distress",
        "description": "Credit risk metrics and interest coverage ratios decaying into distressed financial reorganization territory.",
        "embedding": [-0.7, -0.8, -0.9, -0.6, 0.8, -0.8, 0.2, -0.6],
        "decay_half_life_hours": 2160.0,
        "volatility_sensitivity": 1.75,
    },
    {
        "concept_id": "FUND_CAPEX_SUPERCYCLE",
        "category": ConceptCategory.FUNDAMENTALS,
        "name": "Productive Capex Supercycle",
        "description": "Large-scale capital expenditures into high-ROIC capacity expanding future competitive moat.",
        "embedding": [0.4, 0.5, 0.6, 0.3, -0.2, 0.6, 0.3, 0.3],
        "decay_half_life_hours": 2160.0,
        "volatility_sensitivity": 0.55,
    },

    # 4. Valuation Concepts
    {
        "concept_id": "VAL_DISCOUNT_TO_INTRINSIC",
        "category": ConceptCategory.VALUATION,
        "name": "Deep Value Discount",
        "description": "Multiple standard deviations below historical median valuation metrics and DCF fair value.",
        "embedding": [0.4, 0.2, 0.5, 0.2, -0.2, 0.6, 0.5, 0.1],
        "decay_half_life_hours": 720.0,
        "volatility_sensitivity": 0.50,
    },
    {
        "concept_id": "VAL_EXTREME_PREMIUM",
        "category": ConceptCategory.VALUATION,
        "name": "Multiple Expansion Peak",
        "description": "EV/Sales and P/E ratios at extreme historical percentiles pricing perfection with zero margin of safety.",
        "embedding": [-0.3, 0.1, -0.3, 0.1, 0.6, -0.3, -0.5, 0.2],
        "decay_half_life_hours": 480.0,
        "volatility_sensitivity": 1.15,
    },
    {
        "concept_id": "VAL_TERMINAL_GROWTH_COMPRESSION",
        "category": ConceptCategory.VALUATION,
        "name": "Terminal Growth Multiple Compression",
        "description": "Long-term revenue growth expectations cut sharply as market maturity and saturation set in.",
        "embedding": [-0.5, -0.3, -0.5, -0.2, 0.4, -0.5, -0.3, -0.2],
        "decay_half_life_hours": 960.0,
        "volatility_sensitivity": 0.90,
    },
    {
        "concept_id": "VAL_HISTORICAL_QUINTILE_LOW",
        "category": ConceptCategory.VALUATION,
        "name": "Valuation Quintile 1 Floor",
        "description": "Price-to-book and enterprise value multiples residing in bottom 5% decile of 10-year trading range.",
        "embedding": [0.5, 0.3, 0.6, 0.3, -0.3, 0.7, 0.4, 0.2],
        "decay_half_life_hours": 840.0,
        "volatility_sensitivity": 0.60,
    },
    {
        "concept_id": "VAL_BUBBLE_EXHAUSTION",
        "category": ConceptCategory.VALUATION,
        "name": "Speculative Bubble Exhaustion",
        "description": "Extreme valuation dislocation detaching completely from underlying fundamental cash flow reality.",
        "embedding": [-0.4, 0.0, -0.4, 0.0, 0.8, -0.5, -0.7, 0.1],
        "decay_half_life_hours": 168.0,
        "volatility_sensitivity": 1.65,
    },

    # 5. Volatility & Derivatives Concepts
    {
        "concept_id": "VOL_VARIANCE_PREMIUM_SPIKE",
        "category": ConceptCategory.VOLATILITY,
        "name": "Variance Risk Premium Expansion",
        "description": "Implied volatility trading at massive spread over realized trailing volatility.",
        "embedding": [-0.2, -0.3, -0.3, -0.4, 0.8, -0.4, 0.4, -0.2],
        "decay_half_life_hours": 48.0,
        "volatility_sensitivity": 1.50,
    },
    {
        "concept_id": "VOL_SKEW_STEEPENING",
        "category": ConceptCategory.VOLATILITY,
        "name": "Downside Skew Steepening",
        "description": "Out-of-the-money put options commanding heavy volatility premium over at-the-money options.",
        "embedding": [-0.4, -0.5, -0.4, -0.5, 0.9, -0.6, 0.3, -0.4],
        "decay_half_life_hours": 36.0,
        "volatility_sensitivity": 1.60,
    },
    {
        "concept_id": "VOL_GAMMA_SQUEEZE_CALL",
        "category": ConceptCategory.VOLATILITY,
        "name": "Positive Delta Call Gamma Squeeze",
        "description": "Short-dated call option volume forcing dealer hedging into underlying asset spot buying.",
        "embedding": [0.1, 0.5, 0.2, 0.7, 0.5, 0.1, -0.4, 0.7],
        "decay_half_life_hours": 18.0,
        "volatility_sensitivity": 1.40,
    },
    {
        "concept_id": "VOL_GAMMA_SQUEEZE_PUT",
        "category": ConceptCategory.VOLATILITY,
        "name": "Negative Delta Put Gamma Cascade",
        "description": "Dealer short put inventory forcing systematic delta selling as underlying price falls into strikes.",
        "embedding": [-0.5, -0.7, -0.5, -0.7, 0.9, -0.7, 0.4, -0.7],
        "decay_half_life_hours": 18.0,
        "volatility_sensitivity": 1.90,
    },
    {
        "concept_id": "VOL_CLUSTERING_EXPANSION",
        "category": ConceptCategory.VOLATILITY,
        "name": "Autoregressive Volatility Clustering",
        "description": "High return dispersion regimes triggering sustained elevated volatility persistence.",
        "embedding": [-0.3, -0.4, -0.4, -0.5, 0.7, -0.5, 0.3, -0.3],
        "decay_half_life_hours": 96.0,
        "volatility_sensitivity": 1.45,
    },
    {
        "concept_id": "VOL_IMPLIED_REALIZED_DIVERGENCE",
        "category": ConceptCategory.VOLATILITY,
        "name": "IV/RV Divergence Dislocation",
        "description": "Realized price volatility decoupling sharply from options implied volatility surfaces.",
        "embedding": [0.0, -0.2, -0.2, -0.3, 0.6, -0.3, 0.2, -0.1],
        "decay_half_life_hours": 48.0,
        "volatility_sensitivity": 1.20,
    },

    # 6. Risk Concepts
    {
        "concept_id": "RISK_TAIL_EVENT_ELEVATED",
        "category": ConceptCategory.RISK,
        "name": "Elevated Left-Tail Risk",
        "description": "Implied volatility skew and option surface pricing severe downside tail probability.",
        "embedding": [-0.6, -0.8, -0.4, -0.7, 0.9, -0.8, 0.5, -0.6],
        "decay_half_life_hours": 48.0,
        "volatility_sensitivity": 1.80,
    },
    {
        "concept_id": "RISK_CORRELATION_BREAKDOWN",
        "category": ConceptCategory.RISK,
        "name": "Cross-Asset Correlation Spike",
        "description": "Loss of diversification benefit as cross-asset correlations approach 1.0 in liquidity crunch.",
        "embedding": [-0.5, -0.7, -0.5, -0.5, 0.8, -0.7, 0.3, -0.4],
        "decay_half_life_hours": 72.0,
        "volatility_sensitivity": 1.50,
    },
    {
        "concept_id": "RISK_LIQUIDITY_BLACK_HOLE",
        "category": ConceptCategory.RISK,
        "name": "Systemic Liquidity Black Hole",
        "description": "Simultaneous evaporation of liquidity providers across cash, futures, and repo markets.",
        "embedding": [-0.8, -0.9, -0.7, -0.8, 0.95, -0.9, 0.6, -0.8],
        "decay_half_life_hours": 36.0,
        "volatility_sensitivity": 2.00,
    },

    # 7. Sentiment Concepts
    {
        "concept_id": "SENT_CAPITULATION_BOTTOM",
        "category": ConceptCategory.SENTIMENT,
        "name": "Market Capitulation Liquidation",
        "description": "Forced margin selling, record retail put volume, and volume spike signaling exhaustion selling.",
        "embedding": [-0.2, 0.5, 0.4, 0.6, -0.5, 0.7, 0.4, 0.3],
        "decay_half_life_hours": 24.0,
        "volatility_sensitivity": 1.30,
    },
    {
        "concept_id": "SENT_EUPHORIC_BLOWOFF",
        "category": ConceptCategory.SENTIMENT,
        "name": "Speculative Euphoria / Blowoff",
        "description": "Extreme retail call option buying, leveraged inflows, and parabolic price slope.",
        "embedding": [-0.1, 0.2, -0.2, 0.3, 0.7, -0.2, -0.6, 0.4],
        "decay_half_life_hours": 24.0,
        "volatility_sensitivity": 1.40,
    },
    {
        "concept_id": "SENT_SHORT_INTEREST_CROWDING",
        "category": ConceptCategory.SENTIMENT,
        "name": "Extreme Short Interest Crowding",
        "description": "High borrow cost and utilization exceeding 90% creating explosive short covering squeeze potential.",
        "embedding": [0.1, 0.4, 0.1, 0.5, 0.4, 0.2, -0.3, 0.5],
        "decay_half_life_hours": 72.0,
        "volatility_sensitivity": 1.35,
    },
]


CONCEPT_VOCABULARY: Dict[str, FinancialConcept] = {
    c["concept_id"]: FinancialConcept(**c) for c in _RAW_CONCEPTS
}

CONCEPT_IDS: List[str] = sorted(CONCEPT_VOCABULARY.keys())
_CONCEPT_ID_TO_IDX: Dict[str, int] = {cid: i for i, cid in enumerate(CONCEPT_IDS)}

# Precompute normalized embedding matrix (num_concepts x dim)
_EMBED_MATRIX = np.zeros((len(CONCEPT_IDS), 8), dtype=np.float32)
for idx, cid in enumerate(CONCEPT_IDS):
    vec = np.array(CONCEPT_VOCABULARY[cid].embedding, dtype=np.float32)
    norm = np.linalg.norm(vec)
    _EMBED_MATRIX[idx] = vec / (norm if norm > 1e-12 else 1.0)


def get_concept(concept_id: str) -> FinancialConcept | None:
    return CONCEPT_VOCABULARY.get(concept_id)


def list_concepts() -> List[FinancialConcept]:
    return [CONCEPT_VOCABULARY[cid] for cid in CONCEPT_IDS]


def get_embedding_matrix() -> np.ndarray:
    return _EMBED_MATRIX


def get_concept_index(concept_id: str) -> int | None:
    return _CONCEPT_ID_TO_IDX.get(concept_id)


# Deterministic empirical transition likelihood priors between concept categories
def get_transition_priors(from_concept_id: str) -> Dict[str, float]:
    """Calculate transition probability distribution P(C_{t+1} | C_t) based on category dynamics."""
    source = CONCEPT_VOCABULARY.get(from_concept_id)
    if source is None:
        return {cid: 1.0 / len(CONCEPT_IDS) for cid in CONCEPT_IDS}

    probs: Dict[str, float] = {}
    total = 0.0

    src_cat = source.category
    for target_id, target in CONCEPT_VOCABULARY.items():
        tgt_cat = target.category
        # Base self/category affinity
        weight = 0.05
        if src_cat == ConceptCategory.MACRO:
            if tgt_cat == ConceptCategory.MACRO:
                weight = 0.35
            elif tgt_cat in (ConceptCategory.VALUATION, ConceptCategory.RISK):
                weight = 0.25
        elif src_cat == ConceptCategory.MICROSTRUCTURE:
            if tgt_cat == ConceptCategory.MICROSTRUCTURE:
                weight = 0.40
            elif tgt_cat in (ConceptCategory.SENTIMENT, ConceptCategory.RISK):
                weight = 0.25
        elif src_cat == ConceptCategory.FUNDAMENTALS:
            if tgt_cat == ConceptCategory.VALUATION:
                weight = 0.40
            elif tgt_cat == ConceptCategory.FUNDAMENTALS:
                weight = 0.30
        elif src_cat == ConceptCategory.VALUATION:
            if tgt_cat in (ConceptCategory.FUNDAMENTALS, ConceptCategory.SENTIMENT):
                weight = 0.35
            elif tgt_cat == ConceptCategory.VALUATION:
                weight = 0.30
        elif src_cat == ConceptCategory.VOLATILITY:
            if tgt_cat in (ConceptCategory.RISK, ConceptCategory.MICROSTRUCTURE):
                weight = 0.40
            elif tgt_cat == ConceptCategory.VOLATILITY:
                weight = 0.30
        elif src_cat == ConceptCategory.RISK:
            if tgt_cat in (ConceptCategory.SENTIMENT, ConceptCategory.MICROSTRUCTURE):
                weight = 0.35
            elif tgt_cat == ConceptCategory.RISK:
                weight = 0.25
        elif src_cat == ConceptCategory.SENTIMENT:
            if tgt_cat in (ConceptCategory.MICROSTRUCTURE, ConceptCategory.VALUATION):
                weight = 0.35

        # Incorporate vector cosine affinity
        src_vec = np.array(source.embedding)
        tgt_vec = np.array(target.embedding)
        sim = float(np.dot(src_vec, tgt_vec) / (np.linalg.norm(src_vec) * np.linalg.norm(tgt_vec) + 1e-9))
        affinity = max(0.01, (sim + 1.0) / 2.0)
        p = weight * affinity
        probs[target_id] = p
        total += p

    return {cid: p / total for cid, p in probs.items()}
