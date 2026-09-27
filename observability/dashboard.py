"""Metrics dashboard: point-in-time JSON snapshot of health + metrics + alerts."""
from __future__ import annotations


def render_dashboard(
    *,
    health: dict,
    metrics: dict,
    alerts: tuple[str, ...] = (),
    certification: dict | None = None,
) -> dict:
    if not isinstance(health, dict) or not isinstance(metrics, dict):
        raise ValueError("health and metrics must be dicts.")
    degraded = [k for k, v in health.items() if v != "healthy"]
    return {
        "status": "degraded" if degraded or alerts else "healthy",
        "unhealthy_components": sorted(degraded),
        "active_alerts": list(alerts),
        "metrics": dict(metrics),
        "certification": dict(certification or {}),
    }
