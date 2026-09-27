from __future__ import annotations

import time

import numpy as np


def cpu_gbm(
    paths: int,
    steps: int,
    seed: int = 42,
) -> float:

    rng = np.random.default_rng(seed)

    start = time.perf_counter()

    z = rng.standard_normal(
        (paths, steps)
    )

    terminal = np.exp(
        np.cumsum(
            z,
            axis=1,
        )[:, -1]
    )

    _ = terminal.mean()

    return (
        time.perf_counter()
        - start
    )


def torch_gbm(
    paths: int,
    steps: int,
    device: str,
    seed: int = 42,
) -> float:

    import torch

    torch.manual_seed(seed)

    start = time.perf_counter()

    z = torch.randn(
        paths,
        steps,
        device=device,
    )

    terminal = torch.exp(
        torch.cumsum(
            z,
            dim=1,
        )[:, -1]
    )

    _ = terminal.mean()

    if device.startswith("cuda"):
        torch.cuda.synchronize()

    return (
        time.perf_counter()
        - start
    )


def crossover_table(
    path_sizes: tuple[int, ...] = (
        1_000,
        10_000,
        100_000,
    ),
    steps: int = 252,
) -> list[dict]:

    output = []

    for paths in path_sizes:

        cpu = cpu_gbm(
            paths,
            steps,
        )

        row = {
            "paths": paths,
            "steps": steps,
            "cpu_seconds": cpu,
        }

        try:

            gpu = torch_gbm(
                paths,
                steps,
                "cuda",
            )

            row["gpu_seconds"] = gpu
            row["gpu_speedup"] = (
                cpu / gpu
                if gpu > 0
                else None
            )

        except Exception as exc:

            row["gpu_seconds"] = None
            row["gpu_speedup"] = None
            row["gpu_error"] = str(exc)

        output.append(row)

    return output
