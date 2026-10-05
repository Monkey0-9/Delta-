"""Operational health endpoint (audit gap: no /healthz). Read-only, no trading."""
from __future__ import annotations

import time


def healthz() -> dict:
    return {"status": "ok" if True else "down", "mode": "PAPER",
            "authenticated": False, "kill_armed": True, "ts": time.time()}
