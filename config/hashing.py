"""Group 03 — Configuration hashing + runtime snapshots + compatibility tests helper.

Effective config sha stored per run / experiment manifest.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, default=str).encode()


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(canonical(cfg)).hexdigest()


def snapshot(cfg: dict, dest: str | Path) -> Path:
    p = Path(dest)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sha": config_hash(cfg),
        "at": datetime.now(timezone.utc).isoformat(),
        "config": cfg,
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def compatible(snapshot_sha: str, current_cfg: dict) -> bool:
    return snapshot_sha == config_hash(current_cfg)
