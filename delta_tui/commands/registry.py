"""One command/action model: slash commands AND natural language converge here."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class CommandAction:
    name: str
    description: str
    screen: str = "home"
    needs_symbol: bool = False
    risky: bool = False
    run: Callable[[dict], str] | None = None


def _go(screen: str):
    def _f(ctx: dict) -> str:
        return f"SCREEN:{screen}"
    return _f


REGISTRY: dict[str, CommandAction] = {}


def _reg(a: CommandAction) -> None:
    REGISTRY[a.name] = a


for _name, _desc, _screen, _sym in [
    ("market", "Market overview", "market", False),
    ("book", "Order book for symbol", "book", True),
    ("analyze", "Security analysis", "security", True),
    ("research", "Research workspace / new experiment", "research", False),
    ("alpha", "Alpha lab", "alpha", False),
    ("portfolio", "Portfolio (actual state for mode)", "portfolio", False),
    ("risk", "Risk cockpit", "risk", False),
    ("execution", "Execution monitor", "execution", False),
    ("orders", "Orders & fills", "orders", False),
    ("scenario", "Historical scenario replay", "scenarios", False),
    ("model", "Model status", "models", False),
    ("system", "System health", "system", False),
    ("home", "Command cockpit", "home", False),
    ("kill", "EMERGENCY kill switch (two-step confirm, bypasses LLM)", "system", False),
]:
    _reg(CommandAction(name=_name, description=_desc, screen=_screen,
                       needs_symbol=_sym, risky=(_name == "kill"), run=_go(_screen)))


def lookup(name: str) -> CommandAction | None:
    return REGISTRY.get((name or "").lower().strip("/ "))
