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

import logging
import os
import sys
import warnings
from enum import Enum

logger = logging.getLogger("DELTA.Config.Mode")


class DeltaMode(str, Enum):
    LIVE = "LIVE"
    PAPER = "PAPER"
    SIMULATION = "SIMULATION"
    RESEARCH = "RESEARCH"
    DEMO = "DEMO"
    SHADOW = "SHADOW"  # Stage-5 X: true live-data/hypothetical-exec split (was PAPER alias)

    @classmethod
    def parse(cls, raw: str) -> "DeltaMode":
        key = (raw or "").strip().upper()
        aliases = {
            "PROD": cls.LIVE,
            "PRODUCTION": cls.LIVE,
            "SIM": cls.SIMULATION,
            "PAPER": cls.PAPER,
            "SHADOW": cls.SHADOW,  # true shadow mode (live data, hypothetical exec)
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
            DeltaMode.SHADOW: "shadow",
            DeltaMode.SIMULATION: "simulation",
            DeltaMode.RESEARCH: "research",
            DeltaMode.DEMO: "simulation",  # demo runs on sim rails, badged DEMO
        }[self]

    @property
    def is_paper_family(self) -> bool:
        return self in (DeltaMode.PAPER, DeltaMode.SHADOW)

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
    elif mode is DeltaMode.SHADOW:
        base += " — LIVE DATA, HYPOTHETICAL EXECUTION (NO ORDERS)"
    elif mode is DeltaMode.RESEARCH:
        base += " — RESEARCH ONLY, NO ORDERS"
    if extra:
        base += f" — {extra}"
    return base


def resolve_mode(raw: str) -> DeltaMode:
    """Parse a mode string with the LIVE fail-closed gate.

    LIVE resolves only when ``DELTA_LIVE=ARMED`` is set in the environment.
    Otherwise the request downgrades to PAPER with a loud warning (warnings
    + stderr) — never silently. Deeper live gates (vault unlock, health,
    signed authorization) live in ``brokers/live.py`` and the execution
    policy; this is the first downgrade layer, not the whole gate.
    """
    mode = DeltaMode.parse(raw)
    if mode is DeltaMode.LIVE and os.environ.get("DELTA_LIVE", "").upper() != "ARMED":
        msg = (
            "LIVE mode requested without DELTA_LIVE=ARMED: "
            "fail-closed downgrade to PAPER (no live orders)")
        warnings.warn(msg, UserWarning, stacklevel=2)
        logger.warning(msg)
        print(f"WARNING: {msg}", file=sys.stderr)
        return DeltaMode.PAPER
    return mode
