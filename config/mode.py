"""Canonical DELTA run-mode model.

Every surface (TUI header, Typer commands, logs, manifests) must render
one of these modes so the operator can NEVER mistake staged/demo state
for real portfolio state.

Mapping to existing config envs:
  LIVE       -> prod
  PAPER      -> paper
  SIMULATION -> simulation
  RESEARCH   -> research
  DEMO       -> explicit synthetic showcase (never default)
  SHADOW     -> shadow (accepted as PAPER-family alias for compat)
"""
from __future__ import annotations

from enum import Enum


class DeltaMode(str, Enum):
    LIVE = "LIVE"
    PAPER = "PAPER"
    SIMULATION = "SIMULATION"
    RESEARCH = "RESEARCH"
    DEMO = "DEMO"

    @classmethod
    def parse(cls, raw: str) -> "DeltaMode":
        key = (raw or "").strip().upper()
        aliases = {
            "PROD": cls.LIVE,
            "PRODUCTION": cls.LIVE,
            "SIM": cls.SIMULATION,
            "PAPER": cls.PAPER,
            "SHADOW": cls.PAPER,  # shadow executes paper-family path
            "RESEARCH": cls.RESEARCH,
            "DEMO": cls.DEMO,
            "LIVE": cls.LIVE,
            "SIMULATION": cls.SIMULATION,
        }
        if key not in aliases:
            raise ValueError(
                f"unknown mode {raw!r}. Choose from LIVE|PAPER|SIMULATION|RESEARCH|DEMO."
            )
        return aliases[key]

    @property
    def config_env(self) -> str:
        return {
            DeltaMode.LIVE: "prod",
            DeltaMode.PAPER: "paper",
            DeltaMode.SIMULATION: "simulation",
            DeltaMode.RESEARCH: "research",
            DeltaMode.DEMO: "simulation",  # demo runs on sim rails, badged DEMO
        }[self]

    @property
    def is_real_money(self) -> bool:
        return self is DeltaMode.LIVE

    @property
    def badge(self) -> str:
        return f"[{self.value}]"


def mode_banner(mode: DeltaMode, *, extra: str = "") -> str:
    base = f"MODE {mode.badge}"
    if mode is DeltaMode.DEMO:
        base += " — SYNTHETIC SHOWCASE, NOT PORTFOLIO STATE"
    elif mode is DeltaMode.SIMULATION:
        base += " — SIMULATED EXECUTION"
    elif mode is DeltaMode.RESEARCH:
        base += " — RESEARCH ONLY, NO ORDERS"
    if extra:
        base += f" — {extra}"
    return base
