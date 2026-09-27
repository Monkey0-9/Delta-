"""FINAGENT mandate builder (Week 1).

Builds a validated TradingMandate from wizard answers. Deterministic,
most-restrictive-wins. Never enables leverage/short/autonomous implicitly.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .mandate import AutonomyMode, TradingMandate

_UNIVERSE_PRESETS: dict[str, tuple[str, ...]] = {
    "us equities": ("AAPL", "MSFT", "NVDA", "SPY", "QQQ"),
    "indian equities": ("RELIANCE", "TCS", "INFY", "HDFCBANK", "NIFTYBEES"),
    "nifty 500": ("NIFTY500",),
    "etfs": ("SPY", "QQQ", "AGG", "GLD", "NIFTYBEES"),
    "bonds": ("AGG", "LQD", "HYG"),
    "treasuries": ("SHY", "IEF", "TLT"),
    "fx": ("EURUSD", "USDINR", "GBPUSD"),
    "commodities": ("GLD", "USO", "SLV"),
    "crypto": ("BTC", "ETH"),
    "multi-asset": ("SPY", "AGG", "GLD", "NIFTYBEES", "USDINR"),
}

_HORIZON_PRESETS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "intraday": ("1d", "1w", ("1d",)),
    "today": ("1d", "1w", ("1d",)),
    "1-5 days": ("1w", "1m", ("1d", "1w")),
    "week": ("1w", "1m", ("1d", "1w")),
    "1-4 weeks": ("1m", "1y", ("1w", "1m")),
    "month": ("1m", "1y", ("1w", "1m")),
    "1-6 months": ("1m", "1y", ("1w", "1m")),
    "1-3 years": ("1y", "3y", ("1m", "1y")),
    "3-10 years": ("3y", "10y", ("1y", "3y")),
    "year": ("1y", "3y", ("1m", "1y")),
    "mixed": ("1w", "1y", ("1d", "1w", "1m", "1y")),
}

_RISK_PRESETS: dict[str, tuple[float, float, float]] = {
    # min_confidence, max_position_pct, max_drawdown_pct
    "conservative": (0.70, 0.05, 0.08),
    "moderate": (0.60, 0.10, 0.15),
    "aggressive": (0.50, 0.15, 0.25),
}


def parse_capital(text: str) -> Decimal:
    t = (text or "").lower().replace(",", "").replace("rs", "").replace("inr", "").strip()
    if not t or "connect" in t or "existing" in t or "account" in t:
        return Decimal("1000000")
    num = "".join(ch for ch in t if ch.isdigit() or ch in ".-")
    try:
        return Decimal(num or "1000000")
    except InvalidOperation:
        return Decimal("1000000")


def build_mandate(
    *,
    account_id: str = "TRADER-1",
    capital_text: str = "1000000",
    horizon_text: str = "1-4 weeks",
    risk_text: str = "moderate",
    universe_text: str = "multi-asset",
    execution_mode: str = "SUPERVISED",
    preferred_algo: str = "VWAP",
) -> TradingMandate:
    capital = parse_capital(capital_text)
    h = (horizon_text or "mixed").strip().lower()
    primary, secondary, horizons = _HORIZON_PRESETS.get(h, _HORIZON_PRESETS["mixed"])
    r = (risk_text or "moderate").strip().lower()
    conf, pos_pct, dd = _RISK_PRESETS.get("conservative" if "conserv" in r else "aggressive" if "aggress" in r else "moderate")
    # Explicit drawdown override like "max drawdown 10%" wins.
    import re

    m = re.search(r"(\d+(?:\.\d+)?)\s*%", r)
    if m:
        try:
            dd = max(0.01, min(0.60, float(m.group(1)) / 100.0))
        except ValueError:
            pass
    u = (universe_text or "multi-asset").strip().lower()
    universe = _UNIVERSE_PRESETS.get(u, _UNIVERSE_PRESETS["multi-asset"])
    for key, preset in _UNIVERSE_PRESETS.items():
        if key in u and key != u:
            universe = preset
            break
    if "nifty" in u and "etf" in u:
        universe = ("NIFTY500", "NIFTYBEES", "JUNIORBEES")
    mode = (execution_mode or "SUPERVISED").strip().upper()
    if mode not in {m.value for m in AutonomyMode}:
        mode = AutonomyMode.SUPERVISED.value
    autonomy = mode == AutonomyMode.AUTONOMOUS.value
    if autonomy:
        # Bounded autonomy: never silently enabled; caller must pass it explicitly.
        pass
    max_pos_notional = capital * Decimal(str(pos_pct))
    max_ord_notional = capital * Decimal(str(min(pos_pct / 3.0, 0.03)))
    return TradingMandate(
        account_id=account_id,
        universe=tuple(universe),
        allowed_modes=frozenset({AutonomyMode.PAPER, AutonomyMode(mode)}),
        max_position_notional=max_pos_notional,
        max_order_notional=max_ord_notional,
        max_daily_turnover=capital * Decimal("0.25"),
        allowed_short=False,
        max_orders_per_day=100,
        required_confidence=conf,
        allowed_horizons=horizons,
        capital=capital,
        primary_horizon=primary,
        secondary_horizon=secondary,
        max_position_pct=pos_pct,
        max_order_pct=min(pos_pct / 3.0, 0.03),
        max_drawdown_pct=dd,
        allow_leverage=False,
        execution_mode=mode,
        preferred_algo=preferred_algo.upper(),
        autonomy_enabled=autonomy,
    )


def describe(mandate: TradingMandate) -> str:
    lines = [
        "TRADING MANDATE",
        f"Capital: {mandate.capital}",
        f"Universe: {' + '.join(mandate.universe)}",
        f"Primary horizon: {mandate.primary_horizon}",
        f"Secondary horizon: {mandate.secondary_horizon}",
        f"Maximum position: {mandate.max_position_pct:.0%}",
        f"Maximum single order: {mandate.max_order_pct:.0%}",
        f"Maximum drawdown threshold: {mandate.max_drawdown_pct:.0%}",
        f"Short selling: {'Enabled' if mandate.allowed_short else 'Disabled'}",
        f"Leverage: {'Enabled' if mandate.allow_leverage else 'Disabled'}",
        f"Execution: {mandate.execution_mode}",
        f"Preferred execution: {mandate.preferred_algo}",
        f"Minimum confidence: {mandate.required_confidence:.2f}",
        f"Autonomous execution: {'Enabled' if mandate.autonomy_enabled else 'Disabled'}",
    ]
    return "\n".join(lines)
