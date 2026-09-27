from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import perf_counter


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    name: str
    count: int
    total_seconds: float
    min_seconds: float | None
    max_seconds: float | None

    @property
    def average_seconds(self) -> float:
        if self.count == 0:
            return 0.0

        return self.total_seconds / self.count


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._count: dict[str, int] = {}
        self._total: dict[str, float] = {}
        self._minimum: dict[str, float] = {}
        self._maximum: dict[str, float] = {}

    def observe(
        self,
        name: str,
        elapsed_seconds: float,
    ) -> None:
        if elapsed_seconds < 0:
            raise ValueError("elapsed_seconds cannot be negative")

        with self._lock:
            self._count[name] = self._count.get(name, 0) + 1
            self._total[name] = (
                self._total.get(name, 0.0) + elapsed_seconds
            )

            self._minimum[name] = min(
                self._minimum.get(name, elapsed_seconds),
                elapsed_seconds,
            )

            self._maximum[name] = max(
                self._maximum.get(name, elapsed_seconds),
                elapsed_seconds,
            )

    def snapshot(self, name: str) -> MetricSnapshot:
        with self._lock:
            return MetricSnapshot(
                name=name,
                count=self._count.get(name, 0),
                total_seconds=self._total.get(name, 0.0),
                min_seconds=self._minimum.get(name),
                max_seconds=self._maximum.get(name),
            )


class Timer:
    def __init__(
        self,
        registry: MetricsRegistry,
        name: str,
    ) -> None:
        self.registry = registry
        self.name = name
        self._start = 0.0

    def __enter__(self) -> "Timer":
        self._start = perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.registry.observe(
            self.name,
            perf_counter() - self._start,
        )


class Histogram:
    """Latency distribution with p50/p95/p99/p99.9. Thread-safe.

    Execution hot path must not block on reporting: observe() is O(1)
    amortized; percentiles computed on snapshot only.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._samples: list[float] = []

    def observe(self, value_seconds: float) -> None:
        if value_seconds < 0:
            raise ValueError("value_seconds cannot be negative")
        with self._lock:
            self._samples.append(value_seconds)

    def percentile(self, pct: float) -> float:
        if not 0.0 <= pct <= 1.0:
            raise ValueError("pct must be in [0,1]")
        with self._lock:
            if not self._samples:
                return 0.0
            ordered = sorted(self._samples)
        k = min(len(ordered) - 1, int(pct * len(ordered)))
        return ordered[k]

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            count = len(self._samples)
        return {
            "count": float(count),
            "p50": self.percentile(0.50),
            "p95": self.percentile(0.95),
            "p99": self.percentile(0.99),
            "p999": self.percentile(0.999),
        }