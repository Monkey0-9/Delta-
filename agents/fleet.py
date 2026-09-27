"""Deterministic finance agent fleet: 6 specialists -> AgentEvidence findings.

Rule-based reference implementations. Every claim cites [evidence_id] so the
grounding gate can verify it. LLM-backed variants must produce the same
contract shapes and pass through risk/authorization downstream.
"""
from __future__ import annotations

from datetime import datetime, timezone

from agents.contracts import AgentEvidence, AgentFinding, AgentRole


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ev(evidence_id: str, source: str, claim: str, reliability: float) -> AgentEvidence:
    return AgentEvidence(evidence_id, source, f"{claim} [{evidence_id}]", _utc(), reliability)


def market_agent(asset: str, *, volatility: float, spread_bps: float, volume_ratio: float) -> AgentFinding:
    if volatility < 0 or spread_bps < 0 or volume_ratio < 0:
        raise ValueError("market stats must be non-negative.")
    stressed = volatility > 0.4 or spread_bps > 100
    thesis = "liquidity stressed; reduce size" if stressed else "market microstructure normal"
    return AgentFinding(
        "market-01", AgentRole.MARKET, asset, thesis, 0.0 if stressed else 0.01,
        0.4 if stressed else 0.7,
        "invalidation: spread normalizes and volume recovers",
        (
            _ev("mkt-vol", "market", f"realized vol {volatility:.3f}", 0.8),
            _ev("mkt-liq", "market", f"spread {spread_bps:.1f}bps volume_ratio {volume_ratio:.2f}", 0.75),
        ),
        _utc(),
    )


def macro_agent(asset: str, *, rate_change_bp: float, inflation_yoy: float, growth_yoy: float) -> AgentFinding:
    headwind = rate_change_bp > 50 or inflation_yoy > 0.05
    thesis = "macro headwind from rates/inflation" if headwind else "macro backdrop neutral"
    return AgentFinding(
        "macro-01", AgentRole.MACRO, asset, thesis, -0.01 if headwind else 0.005,
        0.6, "invalidation: rate path reverses",
        (
            _ev("mac-rates", "macro", f"rate change {rate_change_bp:.0f}bp", 0.7),
            _ev("mac-growth", "macro", f"inflation {inflation_yoy:.3f} growth {growth_yoy:.3f}", 0.65),
        ),
        _utc(),
    )


def fundamental_agent(asset: str, *, pe: float, pb: float, roe: float, dividend_yield: float) -> AgentFinding:
    if pe <= 0 or pb <= 0:
        raise ValueError("pe/pb must be positive.")
    cheap = pe < 20 and pb < 3
    quality = roe > 0.12
    thesis = f"value={'cheap' if cheap else 'rich'} quality={'high' if quality else 'low'}"
    return AgentFinding(
        "fund-01", AgentRole.FUNDAMENTAL, asset, thesis, 0.02 if cheap and quality else 0.0,
        0.65 if cheap and quality else 0.45, "invalidation: earnings restatement",
        (
            _ev("fun-val", "filings", f"P/E {pe:.1f} P/B {pb:.1f}", 0.8),
            _ev("fun-qual", "filings", f"ROE {roe:.3f} yield {dividend_yield:.3f}", 0.75),
        ),
        _utc(),
    )


def news_agent(asset: str, *, events: tuple[dict, ...]) -> AgentFinding:
    material = [e for e in events if float(e.get("severity", 0.0)) >= 0.7]
    thesis = f"{len(material)} material events" if material else "no material news"
    return AgentFinding(
        "news-01", AgentRole.NEWS, asset, thesis, -0.02 if material else 0.0,
        0.55 if material else 0.5, "invalidation: event retracted",
        tuple(
            _ev(f"news-{i}", str(e.get("source", "wire")), f"{e.get('title', 'event')} sev={e.get('severity', 0)}", 0.6)
            for i, e in enumerate(material)
        ) or (_ev("news-none", "wire", "no material events in window", 0.5),),
        _utc(),
    )


def quant_agent(
    asset: str, *, momentum: float, zscore: float, forecast_return: float, regime: str, confidence: float
) -> AgentFinding:
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1].")
    aligned = (momentum > 0 and forecast_return > 0) or (momentum < 0 and forecast_return < 0)
    thesis = f"quant aligned ({regime})" if aligned else f"quant mixed ({regime})"
    return AgentFinding(
        "quant-01", AgentRole.QUANT, asset, thesis, forecast_return if aligned else 0.0,
        confidence if aligned else confidence * 0.5, "invalidation: regime flips",
        (
            _ev("qnt-mom", "quant", f"momentum {momentum:.3f} z {zscore:.2f}", 0.7),
            _ev("qnt-fc", "quant", f"forecast {forecast_return:.4f} regime {regime}", 0.7),
        ),
        _utc(),
    )


def risk_agent(asset: str, *, gross_exposure: float, leverage: float, stress_breaches: tuple[str, ...]) -> AgentFinding:
    if gross_exposure < 0 or leverage < 0:
        raise ValueError("exposures must be non-negative.")
    blocked = bool(stress_breaches) or leverage > 3.0
    thesis = "risk BLOCKED: breaches present" if blocked else "risk within limits"
    return AgentFinding(
        "risk-01", AgentRole.RISK, asset, thesis, 0.0, 0.9,
        "invalidation: exposures reduced and breaches cleared",
        (
            _ev("rsk-exp", "risk", f"gross {gross_exposure:.0f} lev {leverage:.2f}", 0.9),
            _ev("rsk-stress", "risk", f"breaches {list(stress_breaches) or 'none'}", 0.9),
        ),
        _utc(),
    )
