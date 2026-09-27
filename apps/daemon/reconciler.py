"""Daemon safe-restart reconciler (P2).

Compares OMS open orders vs broker open orders on restart:
resume only when sets match; otherwise halt for operator review.
Pure function, deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReconcileReport:
    matched: tuple[str, ...]
    oms_only: tuple[str, ...]
    broker_only: tuple[str, ...]
    decision: str  # RESUME | HALT
    reason: str


def reconcile_orders(
    oms_open: tuple[str, ...],
    broker_open: tuple[str, ...],
) -> ReconcileReport:
    oms = set(oms_open)
    bro = set(broker_open)
    matched = tuple(sorted(oms & bro))
    oms_only = tuple(sorted(oms - bro))
    broker_only = tuple(sorted(bro - oms))
    if not oms_only and not broker_only:
        return ReconcileReport(matched, (), (), "RESUME", "OMS and broker agree; safe to resume.")
    return ReconcileReport(
        matched,
        oms_only,
        broker_only,
        "HALT",
        f"Divergence: OMS-only={list(oms_only)} broker-only={list(broker_only)}. Halt for review.",
    )
