"""DELTA legacy CLI shim — QUARANTINED.

Canonical interactive entry is now:
  apps/cli/delta.py -> delta_tui.app (Textual workstation)
  args             -> apps.cli.main (Typer)

This module is kept only so old imports fail loudly with guidance.
See archive/legacy_cli/app.py for the frozen legacy implementation.
"""
from __future__ import annotations

import warnings

warnings.warn(
    "delta.cli.app is LEGACY and quarantined. "
    "Use `python -m apps.cli.delta` (workstation) or "
    "`python -m apps.cli.main` (commands). "
    "Frozen copy: archive/legacy_cli/app.py",
    DeprecationWarning,
    stacklevel=2,
)

try:
    from archive.legacy_cli.app import DeltaCLI  # noqa: F401
except Exception:  # pragma: no cover - guidance only
    DeltaCLI = None  # type: ignore


async def main(*args, **kwargs):  # pragma: no cover
    raise RuntimeError(
        "cli.app is retired. Launch the workstation with "
        "`python -m apps.cli.delta`."
    )
