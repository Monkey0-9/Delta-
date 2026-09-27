"""Digital-twin Monte Carlo: seeded terminal-value distribution per action."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class TerminalDistribution:
    action: str
    mean: float
    p5: float
    p50: float
    p95: float
    prob_profit: float
    n_paths: int


def terminal_distribution(
    *,
    action: str,
    start_value: float,
    drift: float,
    vol: float,
    horizon_days: int,
    n_paths: int = 10000,
    seed: int = 0,
) -> TerminalDistribution:
    """GBM terminal values, vectorized and seeded. Same inputs -> same outputs."""
    if start_value <= 0 or vol < 0 or horizon_days < 1 or n_paths < 1:
        raise ValueError("invalid distribution parameters.")
    rng = np.random.default_rng(seed)
    dt = 1.0 / 252.0
    shocks = rng.normal(size=(n_paths, horizon_days))
    terminal = start_value * np.exp(
        (drift - 0.5 * vol**2) * horizon_days * dt + vol * (dt**0.5) * shocks.sum(axis=1)
    )
    return TerminalDistribution(
        action=action,
        mean=float(terminal.mean()),
        p5=float(np.quantile(terminal, 0.05)),
        p50=float(np.quantile(terminal, 0.50)),
        p95=float(np.quantile(terminal, 0.95)),
        prob_profit=float((terminal > start_value).mean()),
        n_paths=n_paths,
    )
