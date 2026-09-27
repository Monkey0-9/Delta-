from __future__ import annotations
from decimal import Decimal


def twap_slices(total: Decimal, n: int) -> tuple[Decimal, ...]:
    if n <= 0 or total <= 0:
        raise ValueError("total/n must be positive.")
    base = total / n
    out = [base] * n
    out[-1] += total - sum(out)  # fix rounding dust
    return tuple(out)


def vwap_slices(total: Decimal, volumes: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    if total <= 0 or not volumes or any(v < 0 for v in volumes):
        raise ValueError("bad inputs.")
    tot = sum(volumes) or Decimal("1")
    return tuple(total * v / tot for v in volumes)


def pov_slices(total: Decimal, volumes: tuple[Decimal, ...], pov: Decimal) -> tuple[Decimal, ...]:
    if not (Decimal("0") < pov <= 1):
        raise ValueError("pov in (0,1].")
    return tuple(min(v * pov, total) for v in volumes)
