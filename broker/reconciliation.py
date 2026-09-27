"""OMS-vs-broker reconciliation runner (P3).

Thin wrapper over the daemon reconciler (single implementation).
Compares OMS open client-order ids vs broker open ids.
"""
from __future__ import annotations

from apps.daemon.reconciler import ReconcileReport, reconcile_orders


def reconcile_oms_vs_broker(
    oms_open: tuple[str, ...],
    broker_open: tuple[str, ...],
) -> ReconcileReport:
    return reconcile_orders(oms_open, broker_open)
