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
    category: str = "Primary"
    run: Callable[[dict], str] | None = None


def _go(screen: str):
    def _f(ctx: dict) -> str:
        return f"SCREEN:{screen}"
    return _f


REGISTRY: dict[str, CommandAction] = {}


def _reg(a: CommandAction) -> None:
    REGISTRY[a.name] = a


for _name, _desc, _screen, _sym, _cat in [
    ("research", "Research a hypothesis / new experiment", "research", False, "Primary"),
    ("market", "Analyze a market / overview", "market", False, "Primary"),
    ("portfolio", "Portfolio context & exposure", "portfolio", False, "Primary"),
    ("risk", "Risk state & limits cockpit", "risk", False, "Primary"),
    ("simulate", "Run scenario simulation", "scenarios", False, "Primary"),
    ("backtest", "Walk-forward strategy backtest", "scenarios", True, "Primary"),
    ("trade", "Create trade proposal & execution ticket", "execution", True, "Primary"),
    ("automation", "Manage automated routines & monitors", "execution", False, "Primary"),
    ("finance-chat", "Conversational financial & market Q&A", "home", False, "Primary"),
    ("finance-agent", "Autonomous financial research & evidence agent", "research", False, "Primary"),
    ("kill-switch", "Emergency execution control (halt & cancel)", "system", False, "Primary"),
    ("book", "Order book L2/L3 replay", "book", True, "Primary"),
    ("analyze", "Security regime analysis", "security", True, "Primary"),
    ("alpha", "Alpha factor lab", "alpha", False, "Primary"),
    ("learn", "Closed-loop feedback & lessons", "alpha", False, "Primary"),
    ("execution", "Order execution monitor", "execution", False, "Primary"),
    ("orders", "Fills and active order blotter", "orders", False, "Primary"),
    ("model", "Switch AI model engine", "models", False, "System/AI"),
    ("agent", "Select active agent persona", "models", False, "System/AI"),
    ("mcp", "Manage MCP tool integrations", "system", False, "System/AI"),
    ("auth", "AES-256 credential vault", "system", False, "System/AI"),
    ("session", "Switch or fork active session", "session", False, "System/AI"),
    ("config", "System configuration settings", "system", False, "System/AI"),
    ("open", "Open browser workspace for context", "home", False, "System/AI"),
    ("system", "System operational health", "system", False, "System/AI"),
    ("home", "Return to home view", "home", False, "System/AI"),
    ("kill", "EMERGENCY kill switch (halt execution)", "system", False, "Primary"),
]:
    _reg(CommandAction(name=_name, description=_desc, screen=_screen,
                       needs_symbol=_sym, category=_cat, risky=("kill" in _name), run=_go(_screen)))


def lookup(name: str) -> CommandAction | None:
    return REGISTRY.get((name or "").lower().strip("/ "))
