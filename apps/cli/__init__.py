"""DELTA CLI package (lazy export to avoid runpy RuntimeWarning)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .main import main

__all__ = ["main"]


def __getattr__(name: str):  # PEP 562 lazy export
    if name == "main":
        from .main import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")