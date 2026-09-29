"""Rich widgets — every widget takes a TYPED viewmodel, never raw strings."""
from __future__ import annotations


def header_text(h: dict) -> str:
    mode = str(h.get("mode", "PAPER")).upper()
    market = str(h.get("market", "LIVE")).upper()
    data = str(h.get("data", "HEALTHY")).upper()
    risk = str(h.get("risk", "SAFE")).upper()
    clock = str(h.get("clock_utc", ""))
    context_symbol = h.get("symbol", "")

    # Mode visual formatting
    if mode == "LIVE":
        mode_str = "MODE: LIVE [!] "
    elif mode == "RESEARCH":
        mode_str = "MODE: RESEARCH"
    else:
        mode_str = f"MODE: {mode}"

    # Symbol context tag if active
    sym_tag = f"  |  {context_symbol}" if context_symbol else ""

    return (
        f"DELTA  |  MARKET {market}  |  DATA {data}  |  RISK {risk}  |  "
        f"{mode_str}{sym_tag}  |  {clock}".strip()
    )


def footer_text(f: dict) -> str:
    ctx = f.get("context", "none")
    return (
        f"Model: {f.get('model', 'delta-fm-research')}  |  "
        f"Agent: {f.get('agent', 'quant-researcher')}  |  "
        f"Session: {f.get('session', 'default')}  |  "
        f"Context: {ctx}"
    )


def hero_nav() -> str:
    return "RESEARCH  |  SIMULATE  |  ANALYZE  |  EXECUTE  |  LEARN"


def input_box() -> str:
    return ">  Ask DELTA anything, run a strategy, analyze a market, or type / for commands...   [Ctrl+K]"


def status_text(s: dict) -> str:
    return (
        f"MARKET {s.get('market')} | DATA {s.get('data')} | RISK {s.get('risk')} | "
        f"MODE {s.get('mode')} | MODEL {s.get('model')} | "
        f"BROKER {s.get('broker')} | KILL SWITCH {s.get('kill')}"
    )
