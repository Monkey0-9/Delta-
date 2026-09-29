"""Paper trading package (DELTA OS).

Lightweight broker-free API: engine / orchestrator / analytics.
Legacy heavyweight paper_engine (PaperTradingEngine, ...) is re-exported
best-effort only and never breaks the lightweight imports.
"""
from __future__ import annotations

from .engine import PaperEngine, PaperFill, PaperOrder
from .orchestrator import PaperOrchestrator
from .analytics import max_drawdown, sharpe, turnover

__all__ = [
    "PaperEngine",
    "PaperOrder",
    "PaperFill",
    "PaperOrchestrator",
    "sharpe",
    "max_drawdown",
    "turnover",
]

try:  # Optional legacy heavyweight engine (may need broker deps).
    from .paper_engine import (  # type: ignore[import-not-found]
        LongDurationValidator,
        PaperTrade,
        PaperTradingEngine,
        PortfolioState,
        ShadowTradingEngine,
        TradingMode,
    )

    __all__ += [
        "TradingMode",
        "PaperTrade",
        "PortfolioState",
        "PaperTradingEngine",
        "ShadowTradingEngine",
        "LongDurationValidator",
    ]
except Exception:  # pragma: no cover - legacy is optional
    pass
