"""W241-W250 parallel experiment scheduler: deterministic research fabric.

Seeds split deterministically (base_seed + index) so parallel runs replay
identically to serial runs. Fail-closed: worker exceptions are collected,
never swallowed — the batch reports FAIL with the offending experiment IDs.
"""
from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScheduledResult:
    experiment_id: str
    seed: int
    status: str  # PASS | FAIL
    detail: str = ""


def run_parallel(experiment_ids: tuple[str, ...], base_seed: int,
                 worker, max_workers: int = 4) -> list[ScheduledResult]:
    """Run worker(exp_id, seed) across the fabric; deterministic seed split."""
    if not experiment_ids:
        return []
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1.")
    seeds = {exp_id: base_seed + i for i, exp_id in enumerate(experiment_ids)}
    results: dict[str, ScheduledResult] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(worker, exp_id, seeds[exp_id]): exp_id for exp_id in experiment_ids}
        for fut in concurrent.futures.as_completed(futs):
            exp_id = futs[fut]
            try:
                detail = fut.result()
                results[exp_id] = ScheduledResult(exp_id, seeds[exp_id], "PASS", str(detail))
            except Exception as exc:
                results[exp_id] = ScheduledResult(exp_id, seeds[exp_id], "FAIL",
                                                  f"{type(exc).__name__}: {exc}")
    ordered = [results[e] for e in experiment_ids]
    failed = [r.experiment_id for r in ordered if r.status == "FAIL"]
    if failed:
        raise RuntimeError(f"fabric batch failed: {failed}.")
    return ordered
