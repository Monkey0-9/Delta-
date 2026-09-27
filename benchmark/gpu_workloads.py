"""GPU workloads: matmul, batch Monte Carlo, transfer timing — device-agnostic.

Runs on CPU everywhere; uses CUDA only when torch exposes a real device
(see benchmark/gpu_contract.py). CPU-only paths (order book, single-event
risk, network I/O) must never be routed here.
"""
from __future__ import annotations

import time

import torch

from benchmark.gpu_contract import select_backend


def active_device() -> torch.device:
    back = select_backend()
    if back.backend.value == "cuda":
        return torch.device("cuda")
    return torch.device("cpu")


def matmul_benchmark(n: int = 1024, iters: int = 10, seed: int = 0) -> dict:
    """Large matrix multiply timing on the active device."""
    torch.manual_seed(seed)
    device = active_device()
    a = torch.randn(n, n, device=device)
    b = torch.randn(n, n, device=device)
    if device.type == "cuda":
        torch.cuda.synchronize()
    start = time.perf_counter()
    for _ in range(iters):
        c = a @ b
    if device.type == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    return {"device": device.type, "n": n, "iters": iters,
            "elapsed_s": elapsed, "gflops": (2 * n**3 * iters / elapsed) / 1e9,
            "checksum": float(c.sum().item())}


def batch_monte_carlo(
    n_paths: int = 100000, n_steps: int = 252, mu: float = 0.05,
    sigma: float = 0.2, seed: int = 0,
) -> dict:
    """Vectorized GBM terminal distribution on the active device."""
    if n_paths < 1 or n_steps < 1 or sigma <= 0:
        raise ValueError("invalid MC parameters.")
    gen = torch.Generator(device="cpu").manual_seed(seed)
    device = active_device()
    if device.type == "cuda":
        gen = torch.Generator(device="cuda").manual_seed(seed)
    dt = 1.0 / 252.0
    shocks = torch.randn(n_paths, n_steps, generator=gen, device=device)
    terminal = torch.exp((mu - 0.5 * sigma**2) * n_steps * dt
                         + sigma * (dt**0.5) * shocks.sum(dim=1))
    return {"device": device.type, "n_paths": n_paths, "n_steps": n_steps,
            "mean": float(terminal.mean().item()),
            "p5": float(terminal.quantile(0.05).item()),
            "p95": float(terminal.quantile(0.95).item())}


def transfer_benchmark(n: int = 10_000_000, seed: int = 0) -> dict:
    """CPU<->device copy timing. Documents why small paths stay on CPU."""
    torch.manual_seed(seed)
    host = torch.randn(n)
    device = active_device()
    start = time.perf_counter()
    dev = host.to(device)
    back = dev.to("cpu")
    elapsed = time.perf_counter() - start
    mb = host.numel() * 4 / 1e6
    return {"device": device.type, "mb_each_way": mb,
            "roundtrip_s": elapsed, "identical": bool(torch.equal(host, back))}
