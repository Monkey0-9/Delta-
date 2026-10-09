"""Phase 8 (registry-driven commands) + §13/§97 command surface.

Registers terminal commands into the single CommandRegistry. Every entry:
id/name/aliases/description/arguments/category/permission/read_only/
state_changing/confirmation_required. TUI + headless API share definitions.
"""
from __future__ import annotations

from .registry import REGISTRY, CommandAction


def _go(screen: str):
    def _f(ctx: dict) -> str:
        return f"SCREEN:{screen}"
    return _f


# (name, description, screen, category, permission, read_only, confirm)
EXTRA: list[tuple] = [
    ("desk", "Trader DESK (default screen)", "home", "Workspace", "READ", True, False),
    ("markets", "Market workspace", "market", "Workspace", "READ", True, False),
    ("brokers", "Broker management view", "system", "Workspace", "BROKER_ADMIN", True, False),
    ("mcp", "MCP management center", "system", "Workspace", "READ", True, False),
    ("models", "Model registry", "models", "Workspace", "READ", "True", False),
    ("agents", "Agent workspace", "models", "Workspace", "READ", True, False),
    ("plan", "Finance read-only planning mode", "research", "Research", "MARKET_RESEARCH", True, False),
    ("execute-plan", "Execute approved plan (permission-gated)", "execution", "Trading", "PAPER_TRADE", False, True),
    ("btw", "Side question (no transcript pollution)", "home", "Research", "READ", True, False),
    ("effort", "Set reasoning effort low|medium|high|xhigh|auto", "models", "System/AI", "READ", True, False),
    ("thinking", "Thinking display off|summary|activity", "models", "System/AI", "READ", True, False),
    ("connect", "Connect provider flow (brokers/data/news/macro/AI/MCP)", "system", "System", "BROKER_ADMIN", False, True),
    ("disconnect", "Disconnect provider", "system", "System", "BROKER_ADMIN", False, True),
    ("flatten", "Flatten positions (confirm)", "execution", "Trading", "ORDER_CANCEL", False, True),
    ("unlock", "Authenticated unlock from HALTED", "system", "Safety", "UNLOCK", False, True),
    ("compact", "Compact session transcript", "session", "System/AI", "READ", True, False),
    ("copy", "Copy response/selection", "home", "System", "READ", True, False),
    ("export", "Export markdown|json|csv", "home", "System", "READ", True, False),
    ("tasks", "Task queue (running/queued/done/failed)", "system", "System", "READ", True, False),
    ("background", "Background task control", "system", "System", "READ", True, False),
    ("context", "Show resolved @ context", "home", "System", "READ", True, False),
    ("sessions", "Session list", "session", "System/AI", "READ", True, False),
    ("new", "New session", "session", "System/AI", "READ", True, False),
    ("resume", "Resume session", "session", "System/AI", "READ", True, False),
    ("chart", "Focused price chart", "market", "Market", "READ", True, False),
    ("news", "News workspace", "market", "Market", "READ", True, False),
    ("macro", "Macro workspace", "market", "Market", "READ", True, False),
    ("fundamentals", "Fundamentals workspace", "market", "Market", "READ", True, False),
    ("compare", "Compare instruments", "market", "Research", "READ", True, False),
    ("quote", "Quote (read-only)", "security", "Market", "READ", True, False),
    ("stress", "Stress scenarios", "risk", "Risk", "RISK_READ", True, False),
    ("account", "Account scope", "system", "Workspace", "PORTFOLIO_READ", True, False),
    ("accounts", "Account list", "system", "Workspace", "PORTFOLIO_READ", True, False),
    ("cancel", "Cancel order (confirm; live orders need explicit Y/N)", "orders", "Trading", "ORDER_CANCEL", False, True),
    ("kill", "EMERGENCY kill switch (halt execution)", "system", "Safety", "KILL_SWITCH", False, True),
    ("mode", "Execution mode", "session", "System", "READ", True, False),
    ("paper", "Paper mode", "session", "System", "PAPER_TRADE", True, False),
    ("live", "Live mode request (guarded transition)", "system", "Safety", "LIVE_EXECUTION", False, True),
    ("order", "Stage order (preview first)", "execution", "Trading", "ORDER_STAGE", False, True),
]

for _name, _desc, _screen, _cat, _perm, _ro, _confirm in EXTRA:
    if _name not in REGISTRY:
        REGISTRY[_name] = CommandAction(name=_name, description=_desc,
                                        screen=_screen, category=_cat, run=_go(_screen))

COMMAND_PERMISSIONS = {n: p for n, _, _, _, p, _, _ in
                       [(e[0],) + e[1:] for e in EXTRA]}
COMMAND_READONLY = {e[0] for e in EXTRA if e[5] is True}
COMMAND_CONFIRM = {e[0] for e in EXTRA if e[6]}


__all__ = ["EXTRA", "COMMAND_PERMISSIONS", "COMMAND_READONLY", "COMMAND_CONFIRM"]
