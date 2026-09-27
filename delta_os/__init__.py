"""DELTA OS: OpenCode-grade terminal over the institutional substrate.

LAZY package (PEP 562): `import delta_os` imports NOTHING — submodules load
on first attribute access. Rationale (lightweight mandate): the terminal
imports pandas/brokers/research stack only when actually used; `--help`-style
flows and test collection stay instant. Python is thin glue here; hot loops
live in C/C++/Rust (native/).
"""
from __future__ import annotations

_SUBMODULES = ("brokers", "data_router", "llm_gateway", "quantkit", "repl",
               "safety", "themes", "vault")

__all__ = list(_SUBMODULES)


def __getattr__(name: str):
    if name in _SUBMODULES:
        import importlib

        mod = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = mod
        return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
