"""Derivatives pricing: Black-Scholes-Merton + Greeks + margin + expiry/roll.

Reference Python implementation. Hot kernels may be ported to C++ only
after DELTA-NATIVE-BENCH proves a bottleneck, with parity tests.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


def _n(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _n_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass(frozen=True, slots=True)
class OptionSpec:
    spot: float
    strike: float
    rate: float  # risk-free, continuously compounded
    vol: float  # implied vol, annualized
    t_years: float  # time to expiry in years
    is_call: bool = True
    dividend_yield: float = 0.0


@dataclass(frozen=True, slots=True)
class Greeks:
    delta: float
    gamma: float
    theta_per_day: float
    vega_per_point: float
    rho_per_point: float


def bsm_price(spec: OptionSpec) -> float:
    if spec.t_years <= 0:
        intrinsic = max(spec.spot - spec.strike, 0.0) if spec.is_call else max(spec.strike - spec.spot, 0.0)
        return intrinsic
    if spec.vol <= 0 or spec.spot <= 0 or spec.strike <= 0:
        raise ValueError("spot/strike/vol must be positive.")
    fwd = spec.spot * math.exp((spec.rate - spec.dividend_yield) * spec.t_years)
    d1 = (math.log(fwd / spec.strike) + 0.5 * spec.vol**2 * spec.t_years) / (spec.vol * math.sqrt(spec.t_years))
    d2 = d1 - spec.vol * math.sqrt(spec.t_years)
    disc = math.exp(-spec.rate * spec.t_years)
    if spec.is_call:
        return disc * (fwd * _n(d1) - spec.strike * _n(d2))
    return disc * (spec.strike * _n(-d2) - fwd * _n(-d1))


def greeks(spec: OptionSpec) -> Greeks:
    if spec.t_years <= 0 or spec.vol <= 0:
        raise ValueError("t_years and vol must be positive for Greeks.")
    d1 = (math.log(spec.spot / spec.strike) + (spec.rate - spec.dividend_yield + 0.5 * spec.vol**2) * spec.t_years) / (
        spec.vol * math.sqrt(spec.t_years)
    )
    d2 = d1 - spec.vol * math.sqrt(spec.t_years)
    df = math.exp(-spec.rate * spec.t_years)
    dq = math.exp(-spec.dividend_yield * spec.t_years)
    delta = dq * _n(d1) if spec.is_call else dq * (_n(d1) - 1.0)
    gamma = dq * _n_pdf(d1) / (spec.spot * spec.vol * math.sqrt(spec.t_years))
    theta = (
        -(spec.spot * dq * _n_pdf(d1) * spec.vol) / (2 * math.sqrt(spec.t_years))
        - (spec.rate * spec.strike * df * _n(d2) if spec.is_call else -spec.rate * spec.strike * df * _n(-d2))
        + (spec.dividend_yield * spec.spot * dq * (_n(d1) if spec.is_call else _n(d1) - 1.0))
    ) / 365.0
    vega = spec.spot * dq * _n_pdf(d1) * math.sqrt(spec.t_years) / 100.0
    rho = (spec.strike * spec.t_years * df * (_n(d2) if spec.is_call else -_n(-d2))) / 100.0
    return Greeks(delta, gamma, theta, vega, rho)


def futures_margin(notional: Decimal, margin_rate: Decimal = Decimal("0.10")) -> Decimal:
    if notional < 0 or not (Decimal("0") < margin_rate <= Decimal("1")):
        raise ValueError("invalid notional/margin_rate.")
    return notional * margin_rate


def roll_decision(*, days_to_expiry: int, open_interest_drop: float, roll_before_days: int = 7) -> bool:
    """True when the front contract should be rolled."""
    return days_to_expiry <= roll_before_days or open_interest_drop >= 0.5


def years_to_expiry(today: date, expiry: date, day_count: float = 365.0) -> float:
    return max((expiry - today).days, 0) / day_count
