"""Group 09 remainder — scenario/attribution/optimize/stress/inspect/compare aliases.

Converges NL + slash on the single action model (registry.lookup).
All aliases bypass string-sniffing: typed CommandAction entries.
"""
from __future__ import annotations

from .registry import REGISTRY, CommandAction, lookup


def _go(screen: str):
    def _f(ctx: dict) -> str:
        arg = (ctx or {}).get("arg", "")
        suffix = f" {arg}".rstrip() if arg else ""
        return f"SCREEN:{screen}{suffix}"
    return _f


_ALIASES: list[tuple[str, str, str, str]] = [
    ("scenario", "Historical scenario replay (/scenario NAME)", "scenarios", "Primary"),
    ("stress", "Risk stress / reverse-stress solver", "risk", "Primary"),
    ("attribution", "Portfolio attribution (factor/sector/alpha)", "portfolio", "Primary"),
    ("optimize", "Constrained portfolio optimize with reason codes", "portfolio", "Primary"),
    ("inspect", "Alpha lineage inspect (deep-link)", "alpha", "Primary"),
    ("compare", "Alpha compare A B same-period same-costs", "alpha", "Primary"),
    ("depth", "Order-book depth alias for /book", "book", "Primary"),
    ("latency", "System latency (modelled vs compute)", "system", "System/AI"),
    ("reproduce", "Experiment reproduce by EXP-ID", "research", "Primary"),
    ("shadow", "Shadow trading status", "system", "Primary"),
    # Shame-proofing: guide-promised commands that had no TUI entry.
    ("lab", "Quant Lab: alphas, IC, regime, walk-forward", "alpha", "Primary"),
    ("exec", "Execution monitor alias", "execution", "Primary"),
    ("recon", "Three-way reconciliation (OMS vs broker vs ledger)", "reconciliation", "Primary"),
    ("audit", "SHA-256 audit chain tail", "audit", "Primary"),
    ("halt", "Emergency halt alias for /kill (confirm)", "system", "Safety"),
    ("mcps", "MCP servers alias", "system", "System/AI"),
    ("forecast", "Probabilistic return forecast", "security", "Primary"),
    ("crash", "Crash/dip radar", "risk", "Primary"),
    ("sentinel", "24/7 sentinel status", "system", "Primary"),
    ("algo", "Algo-trading code generator", "research", "Primary"),
    ("ask", "Quant finance Q&A", "home", "Primary"),
    ("key", "API key vault", "system", "System/AI"),
]

for _name, _desc, _screen, _cat in _ALIASES:
    if _name not in REGISTRY:
        REGISTRY[_name] = CommandAction(name=_name, description=_desc,
                                        screen=_screen, category=_cat,
                                        run=_go(_screen))

# /halt is a kill alias: must carry the risky flag like /kill.
_halt = REGISTRY.get("halt")
if _halt is not None and not _halt.risky:
    REGISTRY["halt"] = CommandAction(name=_halt.name, description=_halt.description,
                                       screen=_halt.screen, category=_halt.category,
                                       risky=True, run=_halt.run)


def parse_book_args(raw: str) -> dict:
    """Parse '/book SYM --depth N' without string-sniffed viewmodels."""
    parts = (raw or "").strip().split()
    out: dict = {"symbol": "NVDA", "depth": 10}
    for p in parts[1:]:
        if p.startswith("--"):
            continue
        if p.isdigit():
            out["depth"] = int(p)
        elif len(p) <= 12:
            out["symbol"] = p.upper()
    for i, p in enumerate(parts):
        if p == "--depth" and i + 1 < len(parts):
            try:
                out["depth"] = int(parts[i + 1])
            except ValueError:
                pass
    return out


def nl_parity(nl: str, slash: str) -> bool:
    """NL and slash converge on the same action name."""
    from .ux import nl_to_action
    a = nl_to_action(nl)
    b = (slash or "").strip().split()[0].strip("/ ").lower() if slash.startswith("/") else slash
    # alias convergence map
    conv = {"simulate": "scenario", "depth": "book"}
    return conv.get(a, a) == conv.get(b, b) or a == b


__all__ = ["parse_book_args", "nl_parity", "lookup"]
