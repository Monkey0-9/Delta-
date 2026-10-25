"""DELTA OS — Next-Concept Modeling (NCM) Engine.

Institutional reasoning engine operating over discrete financial concept spaces.
Unlike auto-regressive token models which drift into ungrounded narrative hallucinations,
NCM predicts transitions between discrete economic, microstructure, and risk states
using native Rust tensor kernels and empirical category priors.

NON-NEGOTIABLE SAFETY INVARIANT:
NCM is strictly an analytical and regime-forecasting capability. It has ZERO
order-entry, risk-loosening, or kill-switch override authority. Any attempt to
channel order instructions through NCM triggers immediate fail-closed AuthorityRefused.
"""
from __future__ import annotations

import datetime
import math
import re
import uuid
from typing import Dict, List, Optional, Tuple
import numpy as np

from finance_model.authority import AuthorityRefused, refuse_llm_order
from finance_model.ncm.contracts import (
    ConceptCategory,
    ConceptTrajectory,
    FinancialConcept,
    NCMGenerationRequest,
    NCMGenerationResult,
    NCMConditioningContext,
)
from finance_model.ncm.vocabulary import (
    CONCEPT_IDS,
    CONCEPT_VOCABULARY,
    get_concept,
    get_embedding_matrix,
    get_transition_priors,
)
from native.accel import backend, fast_ncm_entropy, fast_ncm_similarity


# Canonical keywords mapping directly to concept activations across 42 regimes
_KEYWORD_CONCEPT_MAP: List[Tuple[re.Pattern, str, float]] = [
    # Macro
    (re.compile(r"\b(inflation|cpi|ppi|pce|price surge|rising prices)\b", re.I), "MACRO_INFLATION_SURGE", 0.9),
    (re.compile(r"\b(rate hike|hike rates|hawkish|tightening|fed hikes)\b", re.I), "MACRO_RATE_HIKE_CYCLE", 0.95),
    (re.compile(r"\b(rate cut|dovish|easing|fed cuts|rate relief)\b", re.I), "MACRO_RATE_CUT_EXPECTED", 0.95),
    (re.compile(r"\b(recession|contraction|slowdown|gdp decline|pmi drop)\b", re.I), "MACRO_RECESSIONARY_DRAG", 0.9),
    (re.compile(r"\b(liquidity expansion|qe|quantitative easing|balance sheet)\b", re.I), "MACRO_LIQUIDITY_EXPANSION", 0.85),
    (re.compile(r"\b(inverted|inversion|yield curve 10y-2y|curve invert)\b", re.I), "MACRO_YIELD_CURVE_INVERSION", 0.95),
    (re.compile(r"\b(quantitative tightening|qt|balance sheet runoff|draining reserves)\b", re.I), "MACRO_QUANTITATIVE_TIGHTENING", 0.9),
    (re.compile(r"\b(curve steepening|steepener|term premium expansion|long yields rising)\b", re.I), "MACRO_YIELD_CURVE_STEEPENING", 0.85),
    (re.compile(r"\b(sovereign spread|widening spread|peripheral debt|debt risk premium)\b", re.I), "MACRO_SOVEREIGN_SPREAD_WIDENING", 0.9),
    (re.compile(r"\b(dollar shortage|usd squeeze|basis swap|global dollar liquidity)\b", re.I), "MACRO_DOLLAR_LIQUIDITY_SQUEEZE", 0.9),
    # Microstructure
    (re.compile(r"\b(bid depth|order book bid|buying wall|institutional bid)\b", re.I), "MICRO_ORDER_BOOK_IMBALANCE_BID", 0.8),
    (re.compile(r"\b(ask depth|order book ask|selling wall|supply overhang)\b", re.I), "MICRO_ORDER_BOOK_IMBALANCE_ASK", 0.8),
    (re.compile(r"\b(spread tight|compressed spread|high liquidity)\b", re.I), "MICRO_SPREAD_COMPRESSION", 0.75),
    (re.compile(r"\b(liquidity vacuum|flash crash|gap down|illiquid|spread blowout)\b", re.I), "MICRO_LIQUIDITY_VACUUM", 0.9),
    (re.compile(r"\b(vpin|toxic flow|order flow toxicity|informed trading)\b", re.I), "MICRO_ORDER_FLOW_TOXICITY_VPIN", 0.9),
    (re.compile(r"\b(iceberg|hidden size|stealth liquidity|native replenishment)\b", re.I), "MICRO_ICEBERG_ACCUMULATION", 0.85),
    (re.compile(r"\b(adverse selection|maker toxicity|toxic fills|unfavorable execution)\b", re.I), "MICRO_ADVERSE_SELECTION_SPIKE", 0.85),
    (re.compile(r"\b(cancel replace|quote flicker|cancel to fill|hft flicker)\b", re.I), "MICRO_CANCEL_REPLACE_CASCADE", 0.8),
    # Fundamentals
    (re.compile(r"\b(earnings beat|eps acceleration|revenue beat|strong guidance)\b", re.I), "FUND_EARNINGS_ACCELERATION", 0.85),
    (re.compile(r"\b(earnings miss|margin compression|downgrade|weak revenue)\b", re.I), "FUND_EARNINGS_CONTRACTION", 0.85),
    (re.compile(r"\b(free cash flow|fcf inflection|cash generative|buyback power)\b", re.I), "FUND_CASH_FLOW_SURPLUS", 0.8),
    (re.compile(r"\b(debt maturity|debt cliff|refinancing risk|rollover risk)\b", re.I), "FUND_DEBT_ROLLOVER_CLIFF", 0.9),
    (re.compile(r"\b(working capital strain|cash burn|inventory bloat|dso spike)\b", re.I), "FUND_WORKING_CAPITAL_STRAIN", 0.85),
    (re.compile(r"\b(solvency distress|altman z|distressed debt|reorganization risk)\b", re.I), "FUND_SOLVENCY_DETERIORATION", 0.95),
    (re.compile(r"\b(capex supercycle|capital expenditure boom|capacity expansion)\b", re.I), "FUND_CAPEX_SUPERCYCLE", 0.85),
    # Valuation
    (re.compile(r"\b(undervalued|deep value|discount to nav|cheap pe)\b", re.I), "VAL_DISCOUNT_TO_INTRINSIC", 0.85),
    (re.compile(r"\b(overvalued|multiple expansion|bubble|expensive pe|stretched)\b", re.I), "VAL_EXTREME_PREMIUM", 0.85),
    (re.compile(r"\b(terminal growth cut|growth compression|multiple de-rating)\b", re.I), "VAL_TERMINAL_GROWTH_COMPRESSION", 0.85),
    (re.compile(r"\b(historical quintile low|bottom decile|10-year low multiple)\b", re.I), "VAL_HISTORICAL_QUINTILE_LOW", 0.85),
    (re.compile(r"\b(bubble exhaustion|speculative mania collapse|extreme detachment)\b", re.I), "VAL_BUBBLE_EXHAUSTION", 0.95),
    # Volatility & Derivatives
    (re.compile(r"\b(variance risk premium|vrp|iv over rv|volatility premium)\b", re.I), "VOL_VARIANCE_PREMIUM_SPIKE", 0.9),
    (re.compile(r"\b(skew steepening|put skew|downside skew|out of the money puts)\b", re.I), "VOL_SKEW_STEEPENING", 0.9),
    (re.compile(r"\b(call gamma squeeze|gamma squeeze|dealer short calls|forced delta buying)\b", re.I), "VOL_GAMMA_SQUEEZE_CALL", 0.95),
    (re.compile(r"\b(put gamma cascade|dealer short puts|forced delta selling)\b", re.I), "VOL_GAMMA_SQUEEZE_PUT", 0.95),
    (re.compile(r"\b(volatility clustering|vol expansion|garch spike|sustained vol)\b", re.I), "VOL_CLUSTERING_EXPANSION", 0.85),
    (re.compile(r"\b(iv rv divergence|implied realized dislocation|volatility decoupling)\b", re.I), "VOL_IMPLIED_REALIZED_DIVERGENCE", 0.85),
    # Risk & Sentiment
    (re.compile(r"\b(tail risk|black swan|skew spike|downside protection|vix surge)\b", re.I), "RISK_TAIL_EVENT_ELEVATED", 0.95),
    (re.compile(r"\b(correlation 1|all assets down|contagion|systemic shock)\b", re.I), "RISK_CORRELATION_BREAKDOWN", 0.9),
    (re.compile(r"\b(liquidity black hole|market freeze|zero bids|liquidity evaporation)\b", re.I), "RISK_LIQUIDITY_BLACK_HOLE", 0.95),
    (re.compile(r"\b(capitulation|panic selling|margin call|exhaustion bottom)\b", re.I), "SENT_CAPITULATION_BOTTOM", 0.9),
    (re.compile(r"\b(euphoria|fomo|parabolic|retail frenzy|blowoff top)\b", re.I), "SENT_EUPHORIC_BLOWOFF", 0.9),
    (re.compile(r"\b(short interest|short squeeze|borrow fee|utilization 90%|crowded short)\b", re.I), "SENT_SHORT_INTEREST_CROWDING", 0.9),
]


class NextConceptModel:
    """Institutional Next-Concept Model (NCM) Engine.
    
    Generates high-dimensional concept trajectories across economic, microstructure,
    and risk regimes with strict deterministic fail-closed execution boundaries.
    """

    def __init__(self, model_version: str = "ncm-fin-v1.0-institutional") -> None:
        self.model_version = model_version
        self._embed_matrix = get_embedding_matrix()
        self._concepts = CONCEPT_VOCABULARY
        self._backend = backend()

    def detect_concepts_from_text(self, text: str) -> List[str]:
        """Detect matched concepts from input text based on regex patterns."""
        matched: List[str] = []
        for pattern, concept_id, _ in _KEYWORD_CONCEPT_MAP:
            if pattern.search(text) and concept_id not in matched:
                matched.append(concept_id)
        return matched

    def _infer_initial_embedding(
        self,
        macro_text: str,
        headlines: List[str],
        metrics: Dict[str, float],
    ) -> np.ndarray:
        """Derive 8D query state vector from text context and quantitative metrics."""
        combined_text = f"{macro_text} {' '.join(headlines)}"
        activations: Dict[str, float] = {}

        # 1. Text keyword activations
        for pattern, concept_id, weight in _KEYWORD_CONCEPT_MAP:
            if pattern.search(combined_text):
                activations[concept_id] = max(activations.get(concept_id, 0.0), weight)

        # 2. Quantitative metrics activations
        if metrics:
            # Volatility & tail metrics
            vix = metrics.get("vix", metrics.get("implied_vol", 0.0))
            if vix > 30.0:
                activations["RISK_TAIL_EVENT_ELEVATED"] = 0.95
            elif vix > 22.0:
                activations["RISK_TAIL_EVENT_ELEVATED"] = 0.65

            # Valuation metrics
            pe = metrics.get("pe_ratio", 0.0)
            if pe > 35.0:
                activations["VAL_EXTREME_PREMIUM"] = 0.85
            elif 0.0 < pe < 12.0:
                activations["VAL_DISCOUNT_TO_INTRINSIC"] = 0.85

            # Fundamentals metrics
            eps_growth = metrics.get("eps_growth_yoy", 0.0)
            if eps_growth > 0.20:
                activations["FUND_EARNINGS_ACCELERATION"] = 0.9
            elif eps_growth < -0.10:
                activations["FUND_EARNINGS_CONTRACTION"] = 0.9

            # Microstructure metrics
            spread_bps = metrics.get("spread_bps", 0.0)
            if spread_bps > 15.0:
                activations["MICRO_LIQUIDITY_VACUUM"] = 0.85
            elif 0.0 < spread_bps < 3.0:
                activations["MICRO_SPREAD_COMPRESSION"] = 0.8

            obi = metrics.get("order_book_imbalance", 0.0)
            if obi > 0.25:
                activations["MICRO_ORDER_BOOK_IMBALANCE_BID"] = 0.85
            elif obi < -0.25:
                activations["MICRO_ORDER_BOOK_IMBALANCE_ASK"] = 0.85

        # 3. Blend activated concept vectors into query representation
        if activations:
            query = np.zeros(8, dtype=np.float32)
            for cid, act in activations.items():
                concept = self._concepts.get(cid)
                if concept:
                    query += act * np.array(concept.embedding, dtype=np.float32)
            norm = float(np.linalg.norm(query))
            return query / (norm if norm > 1e-12 else 1.0)

        # Default neutral baseline: modest macro growth
        neutral = np.array([0.1, 0.1, 0.1, 0.1, 0.0, 0.1, 0.0, 0.1], dtype=np.float32)
        return neutral / np.linalg.norm(neutral)

    def generate_trajectory(self, request: NCMGenerationRequest) -> NCMGenerationResult:
        """Generate a sequenced concept trajectory for the given asset and context.
        
        NON-NEGOTIABLE INVARIANT:
        Throws AuthorityRefused if order keywords are present in text inputs.
        """
        # 1. Enforce fail-closed authority gate against trading intents
        audit_payload = f"{request.symbol} {request.macro_context} {' '.join(request.news_headlines)}"
        refuse_llm_order(audit_payload)

        # 2. Infer starting state vector
        query_vec = self._infer_initial_embedding(
            request.macro_context,
            request.news_headlines,
            request.quant_metrics,
        )

        # 3. Compute cosine similarities across vocabulary via accelerated kernel
        concept_sims = fast_ncm_similarity(query_vec, self._embed_matrix)

        # Softmax initial activation distribution
        temp = max(request.temperature, 0.1)
        scaled_logits = concept_sims / temp
        exp_logits = np.exp(scaled_logits - np.max(scaled_logits))
        init_probs = exp_logits / (np.sum(exp_logits) + 1e-12)

        # Select observed root concept
        root_idx = int(np.argmax(init_probs))
        current_cid = CONCEPT_IDS[root_idx]
        observed = [current_cid]

        # 4. Stepwise trajectory projection over horizon
        predicted_steps: List[Tuple[str, float]] = []
        step_entropies: List[float] = []

        active_cid = current_cid
        for _ in range(request.horizon):
            priors = get_transition_priors(active_cid)
            prior_arr = np.array([priors[cid] for cid in CONCEPT_IDS], dtype=np.float64)

            # Modulate transition priors with current context similarities
            blended = 0.6 * prior_arr + 0.4 * init_probs.astype(np.float64)
            blended /= np.sum(blended) + 1e-12

            # Compute entropy of transition distribution
            entropy = fast_ncm_entropy(blended)
            step_entropies.append(entropy)

            # Determine best next concept (excluding immediate self-loop to capture regime evolution)
            candidate_indices = np.argsort(blended)[::-1]
            chosen_idx = int(candidate_indices[0])
            if CONCEPT_IDS[chosen_idx] == active_cid and len(candidate_indices) > 1:
                chosen_idx = int(candidate_indices[1])

            next_cid = CONCEPT_IDS[chosen_idx]
            next_prob = float(blended[chosen_idx])

            predicted_steps.append((next_cid, round(next_prob, 4)))
            active_cid = next_cid

        # Calculate overall trajectory metrics
        mean_entropy = float(np.mean(step_entropies)) if step_entropies else 0.0
        max_entropy = math.log(len(CONCEPT_IDS))
        confidence = float(max(0.0, min(1.0, 1.0 - (mean_entropy / max_entropy))))

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        trajectory = ConceptTrajectory(
            trajectory_id=f"traj-{uuid.uuid4().hex[:8]}",
            symbol=request.symbol,
            observed_concepts=observed,
            predicted_concepts=predicted_steps,
            horizon_steps=request.horizon,
            entropy=round(mean_entropy, 4),
            confidence=round(confidence, 4),
            created_at_utc=now_utc,
        )

        # 5. Synthesize disciplined, non-hallucinatory thesis
        root_concept = self._concepts[current_cid]
        path_str = " -> ".join([c[0] for c in predicted_steps])
        thesis = (
            f"Asset {request.symbol} exhibits an anchor regime in '{root_concept.name}' "
            f"({root_concept.category.value}). Projected transition path [{path_str}] reflects "
            f"structural propagation with an average Shannon entropy of {mean_entropy:.3f} "
            f"and overall confidence of {confidence:.1%}."
        )

        # 6. Synthesize structural invalidating conditions
        invalidating_conditions = [
            f"Abrupt reversal in {root_concept.category.value} baseline dynamics",
            "Dislocation in market depth exceeding 2.5 sigma historical threshold",
            "Unscheduled macro announcement or central bank emergency liquidity intervention",
        ]

        return NCMGenerationResult(
            symbol=request.symbol,
            model_version=self.model_version,
            provenance_badge="NCM_EXPERIMENTAL",
            trajectory=trajectory,
            synthesized_thesis=thesis,
            invalidating_conditions=invalidating_conditions,
            execution_eligibility=False,
            hardware_acceleration=self._backend,
        )

    def generate_llm_conditioning(
        self,
        request: NCMGenerationRequest,
    ) -> NCMConditioningContext:
        """Export NCM discrete trajectory as semantic priors and guardrails for LLM reasoning.
        
        Binds open-ended text generation into mathematically sound, regime-consistent channels.
        """
        res = self.generate_trajectory(request)
        traj = res.trajectory

        vol_sens_avg = float(np.mean([
            self._concepts[c[0]].volatility_sensitivity
            for c in traj.predicted_concepts
            if c[0] in self._concepts
        ])) if traj.predicted_concepts else 1.0

        if vol_sens_avg > 1.4:
            vol_regime = "HIGH_VOLATILITY_EXPANSION"
        elif vol_sens_avg < 0.6:
            vol_regime = "LOW_VOLATILITY_COMPRESSION"
        else:
            vol_regime = "NORMAL_BALANCED"

        guardrails = [
            f"Adhere strictly to projected regime path: {' -> '.join([c[0] for c in traj.predicted_concepts])}",
            f"Reject any claims assuming {vol_regime} reversal without explicit catalyst",
            "Maintain Truth Over Polish: cite explicit [tool:id] or [evidence:id] for any metric",
            "Zero direct order authority: candidate actions require downstream RiskFirewall approval",
        ]

        active = traj.observed_concepts if traj.observed_concepts else ([traj.predicted_concepts[0][0]] if traj.predicted_concepts else [])

        return NCMConditioningContext(
            symbol=request.symbol,
            active_regimes=active,
            forecast_trajectory=traj.predicted_concepts,
            systemic_entropy=traj.entropy,
            volatility_regime=vol_regime,
            invalidating_conditions=res.invalidating_conditions,
            semantic_guardrails=guardrails,
        )
