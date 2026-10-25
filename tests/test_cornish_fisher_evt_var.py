"""Test suite for institutional risk analytics: Cornish-Fisher, EVT, and Multi-Horizon VaR."""
import numpy as np
import pytest
from risk.analytics.var import (
    cornish_fisher_cvar,
    cornish_fisher_var,
    evt_peaks_over_threshold_var,
    historical_cvar,
    historical_var,
    multi_horizon_var,
    parametric_cvar,
    parametric_var,
    risk_report,
)


def test_parametric_and_historical_consistency():
    # Symmetric normal distribution: parametric and historical should roughly align
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 5000)

    h_var = historical_var(returns, 0.95)
    p_var = parametric_var(returns, 0.95)
    cf_var = cornish_fisher_var(returns, 0.95)

    assert abs(h_var - p_var) < 0.005
    assert abs(p_var - cf_var) < 0.005


def test_cornish_fisher_skewness_sensitivity():
    # Negative skew (fat left tail): Cornish-Fisher VaR must exceed Gaussian VaR
    np.random.seed(42)
    left_skewed = np.concatenate([
        np.random.normal(0.005, 0.015, 1000),
        np.random.uniform(-0.15, -0.05, 50),  # Severe crash events
    ])

    p_var = parametric_var(left_skewed, 0.99)
    cf_var = cornish_fisher_var(left_skewed, 0.99)

    assert cf_var > p_var, f"Cornish-Fisher ({cf_var:.4f}) should be larger than Gaussian ({p_var:.4f}) under left skew"


def test_evt_peaks_over_threshold():
    np.random.seed(42)
    # Student-t with df=3 has heavy tails
    t_returns = np.random.standard_t(df=3, size=2000) * 0.02

    var_evt, cvar_evt, xi, beta = evt_peaks_over_threshold_var(t_returns, confidence=0.99)

    assert var_evt > 0.0
    assert cvar_evt >= var_evt
    assert beta > 0.0
    # Heavy tails should yield positive shape parameter xi
    assert xi >= -0.2


def test_multi_horizon_scaling():
    daily_var = 0.02
    # 1-day
    assert multi_horizon_var(daily_var, 1) == 0.02

    # 10-day i.i.d.
    h10_iid = multi_horizon_var(daily_var, 10, autocorrelation=0.0)
    assert abs(h10_iid - (0.02 * np.sqrt(10))) < 1e-6

    # 10-day positively autocorrelated (momentum: volatility grows faster than sqrt(t))
    h10_mom = multi_horizon_var(daily_var, 10, autocorrelation=0.2)
    assert h10_mom > h10_iid

    # 10-day negatively autocorrelated (mean-reversion: volatility grows slower than sqrt(t))
    h10_mr = multi_horizon_var(daily_var, 10, autocorrelation=-0.2)
    assert h10_mr < h10_iid


def test_comprehensive_risk_report():
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.018, 100)
    rep = risk_report(returns)

    expected_keys = [
        "VaR95", "CVaR95", "VaR99", "CVaR99",
        "Parametric_VaR95", "Parametric_CVaR95",
        "CornishFisher_VaR95", "CornishFisher_CVaR95",
        "EVT_VaR99", "EVT_CVaR99",
        "Skewness", "Excess_Kurtosis",
    ]
    for k in expected_keys:
        assert k in rep, f"Missing key {k} in risk_report"
        assert isinstance(rep[k], (float, int))


def test_error_handling_and_validation():
    with pytest.raises(ValueError, match="minimum 20 observations required"):
        historical_var([0.01, -0.02])

    with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
        cornish_fisher_var([0.01] * 25, confidence=1.5)

    with pytest.raises(ValueError, match="horizon_days must be positive"):
        multi_horizon_var(0.02, 0)
