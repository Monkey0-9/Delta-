"""W231-W250 (O) — Full telemetry: data/feature/model/risk/decision/execution/
broker latency, queue depth, rejections, fill ratio, slippage, PnL, drawdown.
Prometheus exposition stub + OpenTelemetry-style span records. No external deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

COUNTERS: tuple[str, ...] = ("orders", "rejects", "fills", "timeouts", "gaps")
GAUGES: tuple[str, ...] = ("queue_depth", "pnl", "drawdown", "gross_exposure")
HISTOGRAMS: tuple[str, ...] = ("data_latency_ns", "feature_latency_ns", "model_latency_ns",
                               "risk_latency_ns", "decision_latency_ns", "execution_latency_ns",
                               "broker_latency_ns", "slippage_bps")


@dataclass
class Telemetry:
    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    histograms: dict[str, list[int]] = field(default_factory=dict)
    spans: list[dict] = field(default_factory=list)

    def inc(self, name: str, n: int = 1) -> None:
        if name not in COUNTERS:
            raise ValueError(f"unknown counter {name}")
        self.counters[name] = self.counters.get(name, 0) + n

    def set_gauge(self, name: str, v: float) -> None:
        if name not in GAUGES:
            raise ValueError(f"unknown gauge {name}")
        self.gauges[name] = float(v)

    def observe(self, name: str, v: int) -> None:
        if name not in HISTOGRAMS:
            raise ValueError(f"unknown histogram {name}")
        self.histograms.setdefault(name, []).append(int(v))

    def span(self, name: str, duration_ns: int, **attrs) -> None:
        self.spans.append({"name": name, "duration_ns": duration_ns, **attrs})

    def fill_ratio(self) -> float:
        o = self.counters.get("orders", 0)
        return self.counters.get("fills", 0) / o if o else 0.0

    def rejection_rate(self) -> float:
        o = self.counters.get("orders", 0)
        return self.counters.get("rejects", 0) / o if o else 0.0

    def to_prometheus(self) -> str:
        lines = []
        for k, v in self.counters.items():
            lines.append(f"delta_{k}_total {v}")
        for k, v in self.gauges.items():
            lines.append(f"delta_{k} {v}")
        for k, vals in self.histograms.items():
            if vals:
                s = sorted(vals)
                lines.append(f"delta_{k}_p50 {s[len(s)//2]}")
                lines.append(f"delta_{k}_p99 {s[min(len(s)-1, int(len(s)*0.99))]}")
                lines.append(f"delta_{k}_count {len(s)}")
        return "\n".join(lines)
