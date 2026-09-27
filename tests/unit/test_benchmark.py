from benchmark.workloads import (
    benchmark,
    deterministic_workload,
)


def test_workload_is_deterministic() -> None:
    first = deterministic_workload(1000)
    second = deterministic_workload(1000)

    assert first == second


def test_benchmark_returns_positive_metrics() -> None:
    result = benchmark(
        name="test",
        function=lambda: 42,
        iterations=10,
    )

    assert result.name == "test"
    assert result.iterations == 10
    assert result.elapsed_seconds >= 0
    assert result.operations_per_second > 0
    assert result.result_digest == "42"