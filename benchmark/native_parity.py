from __future__ import annotations

from decimal import Decimal


def py_checksum(values: tuple[int, ...]) -> int:
    acc = 0
    for v in values:
        acc = (acc + v) % 2**64
    return acc


def py_normalize_dedup(values: tuple[int, ...]) -> tuple[int, ...]:
    out: list[int] = []
    prev: int | None = None
    for v in values:
        if v != prev:
            out.append(v)
        prev = v
    return tuple(out)


def py_feature_returns(prices: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    out: list[Decimal] = []
    for i in range(len(prices) - 1):
        base = abs(prices[i])
        out.append(Decimal("0") if base == 0 else (prices[i + 1] - prices[i]) / base)
    return tuple(out)


def py_replay_inversions(timestamps: tuple[int, ...]) -> int:
    return sum(
        1 for i in range(len(timestamps)) for j in range(i + 1, len(timestamps))
        if timestamps[i] > timestamps[j]
    )


def py_risk_gross_exposure(
    quantities: tuple[int, ...], prices: tuple[int, ...]
) -> int:
    return sum(q * p for q, p in zip(quantities, prices))


def py_match_orders(buy_qty: int, asks: tuple[int, ...]) -> tuple[int, int]:
    remaining, filled = buy_qty, 0
    for ask in asks:
        if remaining == 0:
            break
        take = min(remaining, ask)
        filled += take
        remaining -= take
    return filled, remaining


def assert_parity(rel: float = 1e-9, abs_tol: float = 1e-12) -> None:
    """Python-side parity vectors mirroring the Rust unit tests.

    Run in CI alongside ``cargo test``; the Rust kernels assert the same
    vectors so any divergence fails one side. Tolerances per parity policy.
    """
    assert py_checksum((1, 2, 3, 4, 5)) == 15
    assert py_normalize_dedup((1, 1, 2, 3, 3, 3, 4)) == (1, 2, 3, 4)
    rets = py_feature_returns(
        (Decimal("100"), Decimal("110"), Decimal("110"), Decimal("55"))
    )
    assert abs(float(rets[0]) - 0.1) < rel
    assert abs(float(rets[1])) < abs_tol
    assert abs(float(rets[2]) + 0.5) < rel
    assert py_replay_inversions((1, 2, 3)) == 0
    assert py_replay_inversions((3, 2, 1)) == 3
    assert py_risk_gross_exposure((10, 5), (100, 200)) == 2000
    assert py_match_orders(10, (4, 4, 4)) == (10, 0)
    assert py_match_orders(20, (4, 4)) == (8, 12)
