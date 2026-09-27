"""Lock-Free Discrete-Event Simulation Backtester.

W99: Implements deterministic discrete-event simulator with
simulated queue priority, latencies, and cancel-replace dynamics.
"""

from .engine import DiscreteEventEngine, Event, EventType, EventPriority
from .simulator import MarketSimulator, OrderBook, LimitOrder
from .latency import LatencyModel, LatencyDistribution

__all__ = [
    "DiscreteEventEngine",
    "Event",
    "EventType",
    "EventPriority",
    "MarketSimulator",
    "OrderBook",
    "LimitOrder",
    "LatencyModel",
    "LatencyDistribution",
]
