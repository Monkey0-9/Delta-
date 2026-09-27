from __future__ import annotations

from dataclasses import dataclass

from broker.contracts import BrokerAdapter


@dataclass(frozen=True)
class BrokerHealth:
    healthy: bool
    reason: str


def check(
    adapter: BrokerAdapter,
) -> BrokerHealth:

    try:
        healthy = adapter.health()

    except Exception as exc:
        return BrokerHealth(
            healthy=False,
            reason=str(exc),
        )

    if not healthy:
        return BrokerHealth(
            healthy=False,
            reason="broker health check failed",
        )

    return BrokerHealth(
        healthy=True,
        reason="OK",
    )