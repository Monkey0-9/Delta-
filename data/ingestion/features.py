from __future__ import annotations
from decimal import Decimal
from hashlib import sha256


def feature_version(code_commit: str, dataset_hash: str, spec: str) -> str:
    return sha256(f"{code_commit}|{dataset_hash}|{spec}".encode()).hexdigest()[:16]


def returns(prices: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    out = []
    for p, c in zip(prices, prices[1:]):
        out.append(Decimal("0") if p == 0 else (c - p) / abs(p))
    return tuple(out)


def ewma_vol(rets: tuple[Decimal, ...], lam: float = 0.94) -> Decimal:
    v = 0.0
    for r in rets:
        f = float(r)
        v = lam * v + (1 - lam) * f * f
    return Decimal(str(v ** 0.5 * (252 ** 0.5)))
