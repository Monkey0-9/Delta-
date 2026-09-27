"""
OpenCode-style interactive TUI.

NOTE: cli.app is the legacy blueprint TUI whose internal `delta.*` imports
predate the top-level package layout (see delta_compat). The supported
interactive frontends are `delta` (trader/opencode_terminal over the live
delta_os core) and `python -m delta_os`. DeltaCLI is lazy-loaded so that
`import cli` never crashes; importing it directly raises a clear error.
"""

__all__ = ["DeltaCLI"]


def __getattr__(name: str):
    if name == "DeltaCLI":
        try:
            import delta_compat  # noqa: F401  (blueprint delta.* alias)
            from cli.app import DeltaCLI as _CLI
            return _CLI
        except Exception as exc:
            raise ImportError(
                "cli.app (legacy blueprint TUI) is unavailable: its "
                f"delta.* imports are unported ({exc}). Use `delta` or "
                "`python -m delta_os` instead.") from exc
    raise AttributeError(f"module 'cli' has no attribute {name!r}.")
