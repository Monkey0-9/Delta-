"""Phase-2 doc closures: zoo, fleet, report, memory, alerts, logging, deploy, budget, codec, FFI, config."""
import ctypes
import os
import pathlib
import shutil
import subprocess

import numpy as np


def _xy():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 3))
    y = 2 * X[:, 0] - X[:, 1] + rng.normal(scale=0.1, size=60)
    return X, y


def test_forecast_zoo_fits_and_compares():
    from quant.forecasting.models import (
        ARModel,
        EnsembleModel,
        GradientBoostingModel,
        LassoModel,
        MultiHorizonForecaster,
        OLSModel,
        QuantileModel,
        RandomForestModel,
        RidgeModel,
        compare_models,
        walk_forward_mse,
    )

    X, y = _xy()
    for cls in (OLSModel, RidgeModel, LassoModel, RandomForestModel, GradientBoostingModel):
        pred = cls().fit(X, y).predict(X)
        assert pred.shape == (60,) and np.isfinite(pred).all()
    ar = ARModel(lags=5).fit(y)
    assert np.isfinite(ar.predict_next(y[-5:]))
    q = QuantileModel().fit(X, y).predict(X[:5])
    assert set(q) == {0.1, 0.5, 0.9} and (q[0.1] <= q[0.9]).all()
    ens = EnsembleModel([OLSModel(), RidgeModel()]).fit(X, y)
    assert ens.predict(X).shape == (60,)
    mse = walk_forward_mse(OLSModel, X, y, train=30, test=10, step=10)
    assert mse < 1.0
    ranking = compare_models([("ols", OLSModel), ("ridge", RidgeModel)], X, y)
    assert [r.name for r in ranking] == ["ols", "ridge"]
    mh = MultiHorizonForecaster(OLSModel, ("1D", "1W")).fit({"1D": X, "1W": X}, {"1D": y, "1W": y})
    assert set(mh.predict({"1D": X[:2], "1W": X[:2]})) == {"1D", "1W"}


def test_agent_fleet_contracts_and_grounding():
    from agents.fleet import (
        fundamental_agent,
        macro_agent,
        market_agent,
        news_agent,
        quant_agent,
        risk_agent,
    )
    from finance_model.grounding import verify_grounding

    findings = [
        market_agent("AAA", volatility=0.2, spread_bps=10.0, volume_ratio=1.0),
        macro_agent("AAA", rate_change_bp=10.0, inflation_yoy=0.02, growth_yoy=0.03),
        fundamental_agent("AAA", pe=15.0, pb=2.0, roe=0.15, dividend_yield=0.02),
        news_agent("AAA", events=({"title": "deal", "severity": 0.9, "source": "wire"},)),
        quant_agent("AAA", momentum=0.05, zscore=1.2, forecast_return=0.01, regime="trending", confidence=0.7),
        risk_agent("AAA", gross_exposure=80000.0, leverage=0.8, stress_breaches=()),
    ]
    assert {f.role.value for f in findings} == {"MARKET", "MACRO", "FUNDAMENTAL", "NEWS", "QUANT", "RISK"}
    for f in findings:
        checks = verify_grounding(tuple(e.claim for e in f.evidence), tuple(e.evidence_id for e in f.evidence))
        assert checks and all(c.supported for c in checks)
    assert risk_agent("AAA", gross_exposure=1.0, leverage=5.0, stress_breaches=("X",)).thesis.startswith("risk BLOCKED")


def test_research_report_renders():
    from research.report import render_research_report

    md = render_research_report(
        title="T", hypothesis="H", experiment_id="e1", manifest_hash="ab",
        metrics={"sharpe": 1.6}, stress={"CRASH-40": "flagged"},
        gates={"oos": True, "stress": False}, limitations=("research-only",),
    )
    assert "# T" in md and "`e1`" in md and "- oos: PASS" in md and "- stress: FAIL" in md


def test_memory_store_versioning_and_chain():
    from memory.store import MemoryStore

    store = MemoryStore()
    e1 = store.append("d1", "decision", {"action": "BUY"})
    e2 = store.append("d1", "decision", {"action": "HOLD"})
    assert (e1.version, e2.version) == (1, 2)
    assert store.verify_chain("d1") is True
    assert store.latest("d1").payload == {"action": "HOLD"}
    store.append("f1", "failure", {"type": "MODEL_ERROR"})
    assert len(store.search("decision")) == 1 and len(store.search("failure")) == 1
    try:
        store.append("x", "nope", {})
    except ValueError:
        pass
    else:
        raise AssertionError("expected kind reject")


def test_alerts_and_logging():
    from observability.alerts import AlertEngine, AlertRule
    from observability.logging import JsonLogger

    eng = AlertEngine((AlertRule("high-dd", "drawdown", "gt", 0.2, "critical"),
                       AlertRule("low-lev", "leverage", "lt", 0.1),))
    fired = eng.evaluate({"drawdown": 0.25, "leverage": 1.0})
    assert [a.rule for a in fired] == ["high-dd"] and eng.active == ("high-dd",)
    assert eng.evaluate({"drawdown": 0.1, "leverage": 1.0}) == []

    logger = JsonLogger("test")
    rec = logger.log("info", "order note api_key=SECRET123", trace_id="t1")
    assert "[REDACTED]" in rec["msg"] and "SECRET123" not in rec["msg"]
    assert rec["trace_id"] == "t1"


def test_deployment_registry_lifecycle_and_rollback():
    from deployment.registry import DeploymentRegistry

    reg = DeploymentRegistry()
    reg.register("strat-a", "v1", "h" * 64, "alice")
    reg.register("strat-a", "v2", "i" * 64, "alice")
    reg.promote("strat-a", "v1", "candidate", "alice")
    reg.promote("strat-a", "v1", "shadow", "alice")
    reg.promote("strat-a", "v1", "production", "alice")
    reg.promote("strat-a", "v2", "candidate", "alice")
    reg.promote("strat-a", "v2", "shadow", "alice")
    reg.promote("strat-a", "v2", "production", "alice")
    assert reg.production("strat-a").version == "v2"
    back = reg.rollback("strat-a", "alice")
    assert back.version == "v1"
    assert reg.verify_log() is True
    try:
        reg.promote("strat-a", "v1", "production", "alice")
    except ValueError:
        pass
    else:
        raise AssertionError("expected illegal-transition reject")


def test_portfolio_budget_math():
    from decimal import Decimal

    from portfolio.budget import check_group_caps, risk_contribution, risk_parity_weights

    w = risk_parity_weights({"A": Decimal("0.2"), "B": Decimal("0.4")})
    assert abs(w["A"] - Decimal("2") / Decimal("3")) < Decimal("1e-12")
    rc = risk_contribution(w, {"A": Decimal("0.2"), "B": Decimal("0.4")})
    assert abs(sum(rc.values(), Decimal("0")) - Decimal("1")) < Decimal("1e-12")
    breached = check_group_caps({"A": Decimal("0.5"), "B": Decimal("0.1")},
                                {"A": "tech", "B": "tech"}, {"tech": Decimal("0.5")})
    assert breached == ("tech",)


def test_msgpack_codec_roundtrip_and_tamper():
    from schemas.serialization import pack, unpack

    blob = pack({"order_id": "o-1", "qty": 10})
    assert unpack(blob) == {"order_id": "o-1", "qty": 10}
    tampered = bytearray(blob)
    tampered[-1] ^= 0xFF
    try:
        unpack(bytes(tampered))
    except Exception:
        pass
    else:
        raise AssertionError("expected tamper reject")


def test_new_signal_math():
    from decimal import Decimal

    from quant.signals.extensions import (
        cross_asset_momentum_rank,
        garch11_volatility,
        pair_spread_zscore,
        regime_conditioned_signal,
    )

    assert garch11_volatility((0.01, -0.02, 0.015, -0.005, 0.02)) > Decimal("0")
    z = pair_spread_zscore(tuple(range(70)), tuple(range(70)), window=60)
    assert z == Decimal("0")
    ranks = cross_asset_momentum_rank({"A": Decimal("0.1"), "B": Decimal("-0.1")})
    assert ranks[0][0] == "A" and ranks[0][1] == Decimal("1")
    assert regime_conditioned_signal(Decimal("1"), "crisis") == Decimal("0")
    assert regime_conditioned_signal(Decimal("2"), "normal") == Decimal("2")


def test_ctypes_cabi_boundary():
    gcc = shutil.which("g++")
    if gcc is None:
        raise AssertionError("g++ required for FFI gate.")
    if os.name == "nt":
        # MinGW runtime DLLs (libwinpthread etc.) live beside g++.
        os.add_dll_directory(os.path.dirname(gcc))
    tmp = pathlib.Path("cabi_gate")
    tmp.mkdir(exist_ok=True)
    ext = ".dll" if os.name == "nt" else ".so"
    lib = tmp / f"delta_cabi{ext}"
    subprocess.run(
        ["g++", "-std=c++17", "-shared", "-fPIC", "-static-libgcc",
         "-static-libstdc++", "-I.", "native/cpp/cabi.cpp",
         "-o", str(lib)], check=True, timeout=300,
    )
    so = ctypes.CDLL(str(lib.resolve()))
    so.delta_match_buy.restype = ctypes.c_double
    so.delta_match_buy.argtypes = [ctypes.c_double, ctypes.POINTER(ctypes.c_double),
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_double)]
    asks = (ctypes.c_double * 3)(4.0, 4.0, 4.0)
    rem = ctypes.c_double()
    assert so.delta_match_buy(10.0, asks, 3, ctypes.byref(rem)) == 10.0
    assert rem.value == 0.0
    so.delta_rolling_mean.restype = ctypes.c_double
    so.delta_rolling_mean.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t]
    vals = (ctypes.c_double * 4)(1.0, 2.0, 3.0, 4.0)
    assert abs(so.delta_rolling_mean(vals, 4) - 2.5) < 1e-12
    so.delta_tick_imbalance.restype = ctypes.c_double
    so.delta_tick_imbalance.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t]
    ticks = (ctypes.c_double * 3)(100.0, 101.0, 102.0)
    assert abs(so.delta_tick_imbalance(ticks, 3) - 1.0) < 1e-12


def test_config_loader_most_restrictive():
    from config.loader import load_config

    research = load_config("research")
    assert research["execution"]["mode"] == "research"
    assert research["risk"]["max_order_qty"] == 100
    copilot = load_config("copilot")
    assert copilot["risk"]["max_leverage"] == 1
    assert copilot["risk"]["max_order_qty"] == 10
    try:
        load_config("live")
    except ValueError:
        pass
    else:
        raise AssertionError("expected unknown-env reject")
