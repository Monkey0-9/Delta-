"""DELTA TUI — finance-native workstation (Textual + Rich).

Single interactive frontend. Bare `delta` boots this app.
Typed viewmodels in viewmodels/; screens render FROM viewmodels only —
never by sniffing strings for '|' or '==='.
"""
from __future__ import annotations

from .app import DeltaApp, main

__all__ = ["DeltaApp", "main"]
