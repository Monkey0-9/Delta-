from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats


def historical_var(
    returns,
    confidence: float = 0.95,
) -> float:
    """Historical Value at Risk (VaR).
    
    VaR is reported as a positive loss quantity (e.g. 0.02 means 2% loss).
    """
    values = np.asarray(
        returns,
        dtype=float,
    )

    if values.size < 20:
        raise ValueError(
            "minimum 20 observations required"
        )

    if not 0 < confidence < 1:
        raise ValueError(
            "confidence must be between 0 and 1"
        )

    return float(
        -np.quantile(
            values,
            1.0 - confidence,
        )
    )


def historical_cvar(
    returns,
    confidence: float = 0.95,
) -> float:
    """Historical Conditional Value at Risk (CVaR) / Expected Shortfall."""
    values = np.asarray(
        returns,
        dtype=float,
    )

    threshold = np.quantile(
        values,
        1.0 - confidence,
    )

    tail = values[
        values <= threshold
    ]

    if len(tail) == 0:
        return historical_var(
            values,
            confidence,
        )

    return float(-tail.mean())


def parametric_var(
    returns,
    confidence: float = 0.95,
) -> float:
    """Gaussian Parametric Value at Risk."""
    values = np.asarray(returns, dtype=float)
    if values.size < 20:
        raise ValueError("minimum 20 observations required")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    mu = float(np.mean(values))
    sigma = float(np.std(values, ddof=1))
    if sigma <= 1e-12:
        return 0.0

    z = float(stats.norm.ppf(confidence))
    return float(z * sigma - mu)


def parametric_cvar(
    returns,
    confidence: float = 0.95,
) -> float:
    """Gaussian Parametric Conditional Value at Risk / Expected Shortfall."""
    values = np.asarray(returns, dtype=float)
    if values.size < 20:
        raise ValueError("minimum 20 observations required")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    mu = float(np.mean(values))
    sigma = float(np.std(values, ddof=1))
    if sigma <= 1e-12:
        return 0.0

    z = float(stats.norm.ppf(confidence))
    phi_z = float(stats.norm.pdf(z))
    return float(sigma * (phi_z / (1.0 - confidence)) - mu)


def cornish_fisher_var(
    returns,
    confidence: float = 0.95,
) -> float:
    """Cornish-Fisher expansion Value at Risk adjusting for skewness and kurtosis.
    
    Formula for loss quantile (-w_cf):
        z_loss = z - (S/6)*(z^2 - 1) + (K/24)*(z^3 - 3z) - (S^2/36)*(2z^3 - 5z)
    where:
        z = Phi^{-1}(confidence)
        S = Fisher sample skewness (negative S increases loss quantile)
        K = Fisher excess kurtosis (positive K increases loss quantile)
    """
    values = np.asarray(returns, dtype=float)
    if values.size < 20:
        raise ValueError("minimum 20 observations required")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    mu = float(np.mean(values))
    sigma = float(np.std(values, ddof=1))
    if sigma <= 1e-12:
        return 0.0

    s = float(stats.skew(values))
    k = float(stats.kurtosis(values, fisher=True))

    z = float(stats.norm.ppf(confidence))
    z_loss = (
        z
        - (s / 6.0) * (z**2 - 1.0)
        + (k / 24.0) * (z**3 - 3.0 * z)
        - ((s**2) / 36.0) * (2.0 * z**3 - 5.0 * z)
    )

    # Monotonicity sanity check: prevent inversion under pathological sample moments
    z_loss = max(z_loss, z * 0.5)

    return float(z_loss * sigma - mu)


def cornish_fisher_cvar(
    returns,
    confidence: float = 0.95,
) -> float:
    """Cornish-Fisher Conditional Value at Risk (Expected Shortfall).
    
    Approximated via numerical integration over the tail quantile function.
    """
    values = np.asarray(returns, dtype=float)
    if values.size < 20:
        raise ValueError("minimum 20 observations required")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    # Integrate tail quantiles from confidence to 0.9999
    alphas = np.linspace(confidence, 0.999, 100)
    tail_vars = [cornish_fisher_var(values, float(a)) for a in alphas]
    return float(np.mean(tail_vars))


def evt_peaks_over_threshold_var(
    returns,
    confidence: float = 0.99,
    threshold_quantile: float = 0.90,
) -> Tuple[float, float, float, float]:
    """Extreme Value Theory (EVT) Peaks-Over-Threshold (POT) VaR and CVaR.
    
    Fits a Generalized Pareto Distribution (GPD) to losses exceeding a high threshold.
    
    Returns:
        (evt_var, evt_cvar, xi_shape, beta_scale)
    """
    values = np.asarray(returns, dtype=float)
    if values.size < 50:
        raise ValueError("minimum 50 observations required for EVT fitting")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    if not 0.5 < threshold_quantile < confidence:
        raise ValueError("threshold_quantile must be between 0.5 and confidence")

    losses = -values
    u = float(np.quantile(losses, threshold_quantile))
    exceedances = losses[losses > u] - u
    n_u = len(exceedances)
    n = len(losses)

    if n_u < 5:
        # Fallback to empirical historical metrics if tail sample is too small
        h_var = historical_var(values, confidence)
        h_cvar = historical_cvar(values, confidence)
        return h_var, h_cvar, 0.0, float(np.std(losses))

    # Fit Generalized Pareto Distribution via scipy.stats
    shape_xi, _, scale_beta = stats.genpareto.fit(exceedances, floc=0.0)

    # Analytical POT VaR & CVaR formulas
    ratio = (n / n_u) * (1.0 - confidence)
    if abs(shape_xi) < 1e-4:
        # Gumbel exponential limit as xi -> 0
        var_pot = u - scale_beta * math.log(ratio)
        cvar_pot = var_pot + scale_beta
    elif shape_xi < 1.0:
        var_pot = u + (scale_beta / shape_xi) * ((ratio ** (-shape_xi)) - 1.0)
        cvar_pot = (var_pot / (1.0 - shape_xi)) + ((scale_beta - shape_xi * u) / (1.0 - shape_xi))
    else:
        # Infinite mean / extreme heavy tail fallback
        var_pot = float(np.quantile(losses, confidence))
        cvar_pot = float(np.mean(losses[losses >= var_pot]))

    return float(var_pot), float(cvar_pot), float(shape_xi), float(scale_beta)


def multi_horizon_var(
    daily_var: float,
    horizon_days: int,
    autocorrelation: float = 0.0,
) -> float:
    """Scale Value at Risk to multi-day horizon with optional autocorrelation correction.
    
    If returns exhibit serial correlation rho, the variance multiplier is:
        M(h) = h + 2 * sum_{k=1}^{h-1} (h - k) * rho^k
    """
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    if horizon_days == 1:
        return float(daily_var)
    if not -0.99 <= autocorrelation <= 0.99:
        raise ValueError("autocorrelation must be in [-0.99, 0.99]")

    if abs(autocorrelation) < 1e-6:
        multiplier = math.sqrt(float(horizon_days))
    else:
        rho = autocorrelation
        h = float(horizon_days)
        # Closed form: h + 2 * [ rho*(h*(1-rho) - (1-rho^h)) / (1-rho)^2 ]
        sum_terms = sum((horizon_days - k) * (rho**k) for k in range(1, horizon_days))
        var_scale = h + 2.0 * sum_terms
        multiplier = math.sqrt(max(0.1, var_scale))

    return float(daily_var * multiplier)


def risk_report(
    returns,
) -> dict:
    """Comprehensive institutional risk report.
    
    Preserves legacy keys (VaR95, CVaR95, VaR99, CVaR99) while providing
    full parametric, Cornish-Fisher, and EVT extreme tail analytics.
    """
    values = np.asarray(returns, dtype=float)
    h_var95 = historical_var(values, 0.95)
    h_cvar95 = historical_cvar(values, 0.95)
    h_var99 = historical_var(values, 0.99)
    h_cvar99 = historical_cvar(values, 0.99)

    p_var95 = parametric_var(values, 0.95)
    p_cvar95 = parametric_cvar(values, 0.95)
    p_var99 = parametric_var(values, 0.99)
    p_cvar99 = parametric_cvar(values, 0.99)

    cf_var95 = cornish_fisher_var(values, 0.95)
    cf_cvar95 = cornish_fisher_cvar(values, 0.95)
    cf_var99 = cornish_fisher_var(values, 0.99)
    cf_cvar99 = cornish_fisher_cvar(values, 0.99)

    report = {
        "VaR95": h_var95,
        "CVaR95": h_cvar95,
        "VaR99": h_var99,
        "CVaR99": h_cvar99,
        "Parametric_VaR95": p_var95,
        "Parametric_CVaR95": p_cvar95,
        "Parametric_VaR99": p_var99,
        "Parametric_CVaR99": p_cvar99,
        "CornishFisher_VaR95": cf_var95,
        "CornishFisher_CVaR95": cf_cvar95,
        "CornishFisher_VaR99": cf_var99,
        "CornishFisher_CVaR99": cf_cvar99,
        "Skewness": float(stats.skew(values)),
        "Excess_Kurtosis": float(stats.kurtosis(values, fisher=True)),
    }

    if values.size >= 50:
        evt_var, evt_cvar, xi, beta = evt_peaks_over_threshold_var(values, 0.99)
        report["EVT_VaR99"] = evt_var
        report["EVT_CVaR99"] = evt_cvar
        report["EVT_Xi"] = xi
        report["EVT_Beta"] = beta

    return report
