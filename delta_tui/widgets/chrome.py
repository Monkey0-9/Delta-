"""Rich widgets — every widget takes a TYPED viewmodel, never raw strings."""
from __future__ import annotations


def header_text(h: dict) -> str:
    mode = str(h.get("mode", "PAPER")).upper()
    market = str(h.get("market", "CLOSED")).upper()
    data = str(h.get("data", "HEALTHY")).upper()
    risk = str(h.get("risk", "SAFE")).upper()
    clock = str(h.get("clock_utc", ""))
    # Image 1 (console-safe): DELTA | QUANT INTELLIGENCE CLI | • MARKETS | • DATA | • RISK | [MODE] | clock
    # (Uses • U+2022 which survives cp1252; avoids Δ/●/◉ which crash Windows consoles.)
    return (
        "DELTA  |  QUANT INTELLIGENCE CLI  |  "
        f"MARKETS {market}  |  DATA {data}  |  RISK {risk}  |  "
        f"[{mode}]  |  {clock}".strip()
    )


def footer_text(f: dict) -> str:
    return (
        f"Model: {f.get('model', 'delta-fm-research')}  |  "
        f"Agent: {f.get('agent', 'quant-researcher')}  |  "
        f"Session: {f.get('session', 'default')}"
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
