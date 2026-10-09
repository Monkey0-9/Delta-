"""Group 03 remainder — environment profiles (dev/paper/shadow/prod) + research/sim blocks.

Loads config/*.yaml, hashes effective config per run (Group 03: hashing/snapshots).
Fail-closed: unknown profile raises; production gated (R10 only, signed).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config.hashing import config_hash

ROOT = Path(__file__).resolve().parents[1]
PROFILE_FILES = {
    "dev": "config/base.yaml",
    "paper": "config/paper.yaml",
    "shadow": "config/shadow.yaml",
    "prod": "config/prod.yaml",
    "research": "config/research.yaml",
    "simulation": "config/simulation.yaml",
}


def load_profile(name: str, *, enforce: bool = False) -> dict[str, Any]:
    key = (name or "").lower()
    if key not in PROFILE_FILES:
        raise ValueError(f"unknown profile {name!r}; expected one of {sorted(PROFILE_FILES)}")
    p = ROOT / PROFILE_FILES[key]
    if not p.exists():
        raise FileNotFoundError(f"profile file missing: {p}")
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    cfg["_profile"] = key
    cfg["_sha"] = config_hash(cfg)
    if key == "prod" and not cfg.get("r10_certified"):
        cfg["_gated"] = "BLOCKED: production requires R10 + sign-offs (Group 30)"
    if enforce and cfg.get("_gated"):
        # Enforcing variant: the gated dict is real config data, but handing
        # it out for execution would let a caller trade on a blocked profile.
        # Refuse loudly instead. Default enforce=False preserves the old
        # advisory behavior for readers that only inspect the marker.
        raise RuntimeError(
            f"production profile refused: {cfg['_gated']}")
    return cfg


def research_block(seed: int = 7, budget: float = 1.0) -> dict[str, Any]:
    return {"seed": seed, "budget": budget, "embargo_bars": 5, "purge_bars": 5}


def simulation_block(venue: str = "SIM", latency_ms: float = 0.8) -> dict[str, Any]:
    return {"venue": venue, "modelled_latency_ms": latency_ms,
            "policies": ["RETAIN_IF_DECREASE", "LOSE_PRIORITY"]}


__all__ = ["load_profile", "research_block", "simulation_block", "PROFILE_FILES"]
