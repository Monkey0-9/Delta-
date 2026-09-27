"""Live broker factory (P3).

Paper default, fail-closed: live adapters are NEVER constructed implicitly.
Requires ALL of: DELTA_LIVE_BROKER=1, DELTA_BROKER_URL, DELTA_BROKER_API_KEY.
Otherwise raises. Keeps README 'paper/sim-only unless explicitly enabled'.
"""
from __future__ import annotations

import os


def live_enabled() -> bool:
    return os.environ.get("DELTA_LIVE_BROKER", "0") == "1"


def create_live_broker(endpoints: dict[str, str] | None = None):
    """Build GenericRESTBroker from env. Raises unless explicitly enabled."""
    from broker.generic_rest import GenericRESTBroker

    if not live_enabled():
        raise RuntimeError(
            "Live broker disabled: set DELTA_LIVE_BROKER=1 to enable explicitly."
        )
    base_url = os.environ.get("DELTA_BROKER_URL", "")
    api_key = os.environ.get("DELTA_BROKER_API_KEY", "")
    if not base_url or not api_key:
        raise RuntimeError("Live broker misconfigured: DELTA_BROKER_URL/KEY required.")
    return GenericRESTBroker(
        base_url=base_url,
        api_key=api_key,
        endpoints=endpoints
        or {
            "health": "health",
            "account": "account",
            "positions": "positions",
            "submit": "orders",
            "cancel": "orders/{0}/cancel",
            "status": "orders/{0}",
            "open_orders": "orders/open",
        },
    )
