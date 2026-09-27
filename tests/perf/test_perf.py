from __future__ import annotations

from benchmark.regression import PerfBudget, check_budget
from benchmark.runner import numerical_workload


def test_numerical_workload_within_budget() -> None:
    budget = PerfBudget("decimal_numerical_1000", max_seconds=30.0)
    result = check_budget(budget, lambda: numerical_workload(1000))
    assert result.passed
    assert result.elapsed_seconds >= 0
