"""Screen base: every workspace is a real screen built FROM a typed viewmodel."""
from __future__ import annotations

from typing import Any

from ..state.store import TerminalStore

SCREEN_IDS = (
    "home", "market", "security", "research", "alpha", "portfolio",
    "risk", "execution", "orders", "scenarios", "models", "system", "session",
)


class BaseScreen:
    name = "base"

    def build_viewmodel(self, store: TerminalStore) -> Any:
        raise NotImplementedError

    def render_text(self, vm: Any) -> str:
        return str(vm)

    # Textual hook: real app calls compose() when textual is installed.
    def textual_widget(self):  # pragma: no cover
        return None
