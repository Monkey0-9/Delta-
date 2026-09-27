from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ComponentHealth:

    component: str
    status: HealthStatus
    latency_ms: float
    message: str


class HealthRegistry:

    def __init__(self):

        self._components = {}

    def update(
        self,
        health: ComponentHealth,
    ) -> None:

        self._components[
            health.component
        ] = health

    def overall(
        self,
    ) -> HealthStatus:

        if any(
            item.status == HealthStatus.FAILED
            for item
            in self._components.values()
        ):
            return HealthStatus.FAILED

        if any(
            item.status == HealthStatus.DEGRADED
            for item
            in self._components.values()
        ):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY