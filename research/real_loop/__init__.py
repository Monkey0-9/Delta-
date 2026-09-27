"""DELTA real loop (W94-W104): data → PIT → features → alpha → regime →
forecast → uncertainty → portfolio → risk → costs → execution →
LLM synthesis (evidence-backed) → paper broker → memory → governance.

Offline-capable: tries Yahoo Finance, falls back to seeded synthetic bars
explicitly labeled source="synthetic_offline" (PIT-safe, deterministic).
The hash-seeded demo path is NEVER used here.
"""
from __future__ import annotations

from research.real_loop.cycle import run_full_cycle, run_opportunity_scan

__all__ = ["run_full_cycle", "run_opportunity_scan"]
