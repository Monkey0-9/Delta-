"""Group 05 — Modal manager (confirm kill, inspect alpha lineage)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Modal:
    kind: str  # confirm_kill | alpha_lineage | generic
    title: str
    body: str
    require_text: str = ""  # e.g. CONFIRM for kill


class ModalManager:
    def __init__(self) -> None:
        self._stack: list[Modal] = []

    def open(self, modal: Modal) -> None:
        self._stack.append(modal)

    def confirm_kill(self) -> Modal:
        m = Modal("confirm_kill", "EMERGENCY KILL",
                  "Type CONFIRM to halt execution. Bypasses LLM.", "CONFIRM")
        self.open(m)
        return m

    def inspect_alpha(self, alpha_id: str, lineage: str) -> Modal:
        m = Modal("alpha_lineage", f"Alpha {alpha_id}", lineage)
        self.open(m)
        return m

    def resolve(self, text: str) -> bool:
        if not self._stack:
            return False
        top = self._stack[-1]
        if top.require_text and text.strip() != top.require_text:
            return False
        self._stack.pop()
        return True

    def current(self) -> Modal | None:
        return self._stack[-1] if self._stack else None
