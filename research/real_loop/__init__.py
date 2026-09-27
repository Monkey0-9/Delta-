"""DELTA real loop (W94-W104): data → PIT → features → alpha → regime →
forecast → uncertainty → portfolio → risk → costs → execution →
LLM synthesis (evidence-backed) → paper broker → memory → governance.

Production truth policy (fail-closed): DATA_MODE=LIVE (default) uses Yahoo
only and raises MarketDataUnavailable on failure — synthetic bars are NEVER
returned. DATA_MODE=SIMULATION explicitly opts into seeded synthetic bars
labeled source="synthetic_offline" (PIT-safe, deterministic) for tests/dev.
The hash-seeded demo path is NEVER used here.
"""
from __future__ import annotations

from research.real_loop.cycle import run_full_cycle, run_opportunity_scan

__all__ = ["run_full_cycle", "run_opportunity_scan"]
