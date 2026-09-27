"""Doc-checkbox closures: alpha factory, compiler, regime, signals, exposure, histo, gpu."""
from decimal import Decimal

from observability.metrics import Histogram
from portfolio.factor_exposure import factor_exposure, net_factor_exposure
from quant.regime.detector import classify_regime, regime_conditioned_weight, transition_matrix
from quant.regime.regime import Regime
from quant.signals.extensions import (
    bollinger_pct_b,
    carry_signal,
    donchian_breakout,
    vol_breakout_signal,
)
from research.alpha_factory import AlphaFactory, Hypothesis
from research.compiler import StrategySpec, compile_strategy


def test_alpha_factory_end_to_end():
    factory = AlphaFactory()
    res = factory.run(
        Hypothesis("mom-vol", "momentum conditioned on vol regime", "momentum", "mom20", ("AAA", "BBB")),
        n=100, train=50, test=10, step=10, purge=2, embargo=2,
        backtest_fn=lambda ts, te, ss, se: 0.05,
        oos_fn=lambda: 0.03,
        min_mean_score=0.0, min_oos_score=0.0,
        dataset_hash="d" * 64, code_version="test", seed=1,
    )
    assert res.passed is True and res.n_windows == 4
    assert len(res.manifest_hash) == 64
    assert factory._registry.get(res.experiment_id).conclusion == "PASS"


def test_alpha_factory_rejects_weak():
    res = AlphaFactory().run(
        Hypothesis("weak", "weak idea", "f", "s", ("AAA",)),
        n=100, train=50, test=10, step=10,
        backtest_fn=lambda ts, te, ss, se: -0.5,
        min_mean_score=0.0, dataset_hash="d" * 64,
    )
    assert res.passed is False


def test_compiler_single_artifact():
    spec = StrategySpec("s1", ("AAA",), ("mom20", "vol60"), "mom_regime",
                        "1W", "vol_target", "firewall_v1", "twap")
    compiled = compile_strategy(spec, dataset_hash="d" * 64)
    assert len(compiled.validation_plan) == 6
    assert len(compiled.plan_hash) == 64
    assert compiled.backtest_config["signal"] == "mom_regime"
    assert len(compiled.manifest.manifest_hash) == 64


def test_regime_detector_priority():
    assert classify_regime(realized_vol=Decimal("0.5"), vol_high_threshold=Decimal("0.3"),
                           trend_strength=Decimal("0"), avg_correlation=Decimal("0.9")) is Regime.CRISIS
    assert classify_regime(realized_vol=Decimal("0.1"), vol_high_threshold=Decimal("0.3"),
                           trend_strength=Decimal("0"), spread_bps=Decimal("150")) is Regime.ILLIQUID
    assert classify_regime(realized_vol=Decimal("0.5"), vol_high_threshold=Decimal("0.3"),
                           trend_strength=Decimal("0")) is Regime.HIGH_VOLATILITY
    assert classify_regime(realized_vol=Decimal("0.1"), vol_high_threshold=Decimal("0.3"),
                           trend_strength=Decimal("0.8")) is Regime.TRENDING
    assert classify_regime(realized_vol=Decimal("0.1"), vol_high_threshold=Decimal("0.3"),
                           trend_strength=Decimal("0")) is Regime.NORMAL


def test_transition_matrix_and_conditioning():
    m = transition_matrix((Regime.NORMAL, Regime.NORMAL, Regime.TRENDING))
    assert m[("normal", "normal")] == Decimal("1") / Decimal("2")
    assert m[("normal", "trending")] == Decimal("1") / Decimal("2")
    assert transition_matrix((Regime.NORMAL,)) == {}
    assert regime_conditioned_weight(Regime.CRISIS, Decimal("1")) == Decimal("0")
    assert regime_conditioned_weight(Regime.HIGH_VOLATILITY, Decimal("1")) == Decimal("0.5")


def test_signal_extensions():
    assert carry_signal(Decimal("0.01"), Decimal("0.03")) == 1
    assert carry_signal(Decimal("0.03"), Decimal("0.01")) == -1
    assert donchian_breakout((10, 11, 12, 13, 20), 4) == 1
    assert donchian_breakout((20, 11, 12, 13, 5), 4) == -1
    assert donchian_breakout((10, 11, 12, 13, 12), 4) == 0
    mid = bollinger_pct_b(tuple([100.0] * 20))
    assert mid == Decimal("0.5")
    assert vol_breakout_signal(tuple(float(100 + i) for i in range(61))) == 0


def test_factor_exposure_math():
    exp = factor_exposure({"A": Decimal("0.6"), "B": Decimal("0.4")},
                          {"A": {"value": Decimal("1"), "size": Decimal("-0.5")},
                           "B": {"value": Decimal("0.5"), "size": Decimal("0.5")}})
    assert exp["value"] == Decimal("0.8") and exp["size"] == Decimal("-0.1")
    assert net_factor_exposure(exp) == Decimal("0.9")


def test_histogram_percentiles():
    h = Histogram()
    for i in range(1, 101):
        h.observe(float(i) / 1000.0)
    snap = h.snapshot()
    assert snap["count"] == 100.0
    assert snap["p50"] <= snap["p95"] <= snap["p99"] <= snap["p999"]
    assert abs(snap["p50"] - 0.051) < 1e-9


def test_gpu_select_backend_safe():
    from benchmark.gpu_contract import ComputeBackend, select_backend

    back = select_backend()
    assert back.available is True
    assert back.backend in (ComputeBackend.CPU, ComputeBackend.CUDA)
