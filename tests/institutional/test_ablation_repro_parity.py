"""Ablation contribution + reproducibility manifest + native parity gates."""
import shutil
import subprocess
from decimal import Decimal
from uuid import uuid4

from market_data.order_book import BookLevel, OrderBook
from research.ablation.runner import Ablation, AblationRunner
from research.reproducibility.manifest import ReproducibilityManifest


def test_ablation_contribution_full_vs_removed():
    runner = AblationRunner()
    full = Ablation("full", lambda: 1.50)
    ablated = [
        Ablation("no-regime", lambda: 1.20),
        Ablation("no-uncertainty", lambda: 1.35),
        Ablation("no-memory", lambda: 1.40),
        Ablation("no-twin", lambda: 1.45),
    ]
    report = runner.compare(full, ablated)
    assert report.passed is True
    assert report.full_score == 1.50
    assert len(report.contributions) == 4
    assert all("contribution=" in d for d in report.details)


def test_ablation_regression_detected():
    runner = AblationRunner()
    report = runner.compare(Ablation("full", lambda: 1.0), [Ablation("bad", lambda: 1.5)])
    assert report.passed is False


def test_manifest_roundtrip_and_tamper():
    m = ReproducibilityManifest.from_parts(
        git_commit="abc123",
        dataset_hash="d" * 64,
        model_hash="m" * 64,
        strategy_hash="s" * 64,
        config_hash="c" * 64,
        seed=42,
    )
    fp = m.fingerprint
    assert len(fp) == 64 and m.verify(fp) is True
    assert m.verify("0" * 64) is False


def test_manifest_rejects_empty_hashes():
    try:
        ReproducibilityManifest.from_parts(
            git_commit="x", dataset_hash="", model_hash="m",
            strategy_hash="s", config_hash="c", seed=0,
        )
    except ValueError:
        return
    raise AssertionError("expected empty dataset_hash reject")


def test_python_mirrors_cpp_parity_vectors():
    """Python-side of the vectors proven in native/cpp/parity_check.cpp."""
    from execution.matching.engine import PriceTimeMatcher

    m = PriceTimeMatcher()
    assert m.add("s1", "sell", Decimal("4"), Decimal("4")) == []
    fills = m.add("b1", "buy", Decimal("4"), Decimal("10"))
    assert sum(f.quantity for f in fills) == Decimal("4")

    book = OrderBook(
        instrument_id=uuid4(),
        bids=(BookLevel(Decimal("99"), Decimal("10")), BookLevel(Decimal("98"), Decimal("5"))),
        asks=(BookLevel(Decimal("101"), Decimal("10")),),
    )
    assert abs(book.imbalance() - Decimal("5") / Decimal("25")) < Decimal("1e-12")
    try:
        OrderBook(
            instrument_id=uuid4(),
            bids=(BookLevel(Decimal("102"), Decimal("1")),),
            asks=(BookLevel(Decimal("101"), Decimal("1")),),
        )
    except ValueError:
        return
    raise AssertionError("expected crossed-book reject")


def test_cpp_parity_binary_passes():
    exe = shutil.which("g++")
    if exe is None:
        raise AssertionError("g++ required for parity gate.")
    subprocess.run(
        ["g++", "-std=c++17", "-Wall", "-Wextra", "-I.",
         "native/cpp/parity_check.cpp", "-o", "parity_check_gate"],
        check=True, timeout=180, cwd=".",
    )
    import os

    binary = os.path.join(".", "parity_check_gate.exe" if os.name == "nt" else "parity_check_gate")
    proc = subprocess.run([binary], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0 and "DELTA-CPP-PARITY: PASS" in proc.stdout


def test_native_bench_runner_smoke():
    from benchmarks.native_bench import BenchmarkRunner, BenchmarkWorkload

    runner = BenchmarkRunner()
    wl = BenchmarkWorkload(
        name="smoke",
        description="smoke",
        workload_sizes=[1000],
        warmup_iterations=1,
        benchmark_iterations=3,
        workload_func=lambda n: sum(range(n)),
        data_generator=None,
        validation_func=lambda r: r is not None,
    )
    res = runner.run_workload(wl, "python", 1000)
    assert res.p50 > 0 and res.p99 >= res.p50 and res.throughput > 0
