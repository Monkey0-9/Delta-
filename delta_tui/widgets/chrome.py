"""Rich widgets — every widget takes a TYPED viewmodel, never raw strings."""
from __future__ import annotations


def _safe_glyph(text: str) -> str:
    """Safe console glyph degradation for terminals lacking unicode support."""
    try:
        enc = getattr(__import__("sys").stdout, "encoding", "utf-8") or "utf-8"
        text.encode(enc)
        return text
    except Exception:
        return (text.replace("Δ", "D").replace("●", "*").replace("○", "o")
                .replace("×", "x").replace("→", "->").replace("✓", "v"))


def header_text(h: dict, state: str = "A") -> str:
    """Institutional micro-header for State A and State B."""
    mode = str(h.get("mode", "PAPER")).upper()
    market_dot = "●"
    data_dot = "●" if "HEALTHY" in str(h.get("data", "HEALTHY")).upper() or str(h.get("data")) == "●" else "○"
    risk = str(h.get("risk", "SAFE")).upper()
    clock = str(h.get("clock_utc", "14:32:18"))
    if " " in clock:
        clock = clock.split()[0]  # strip UTC for clean display
    symbol = str(h.get("symbol", "")).upper()

    # Visual distinction for live vs paper/research
    mode_chip = f"{mode} ●" if mode != "LIVE" else "LIVE [!] ●"

    if state.upper() == "B" or (state == "auto" and symbol):
        # State B — Active conversation header
        short_clock = ":".join(clock.split(":")[:2]) if ":" in clock else clock
        ctx_part = f"{symbol} · {short_clock}" if symbol else short_clock
        raw = f"Δ DELTA       MARKET {market_dot} DATA {data_dot} RISK {risk} {mode_chip}       {ctx_part}"
        return _safe_glyph(raw)

    # State A — New session splash header
    raw = f"Δ DELTA          MARKET {market_dot}   DATA {data_dot}   RISK {risk}   {mode_chip}       {clock}"
    return _safe_glyph(raw)


def footer_text(f: dict, state: str = "A") -> str:
    """Institutional micro-footer for State A and State B."""
    mode = str(f.get("mode", "PAPER")).upper()
    risk = str(f.get("risk", "SAFE")).upper()
    model = str(f.get("model", "delta-fm-research"))
    agent = str(f.get("agent", "quant-researcher"))
    context = str(f.get("context", "none"))

    if state.upper() == "A":
        # State A footer
        raw = f"~/delta/trader                                      {mode} · RISK {risk}"
        return _safe_glyph(raw)
    elif state.upper() == "B":
        # State B conversation footer
        raw = f"Model {model} · Agent {agent}"
        return _safe_glyph(raw)

    # Contextual screen footer
    raw = f"Model: {model} · Agent: {agent} · Session: {f.get('session', 'default')} · Context: {context}"
    return _safe_glyph(raw)


def hero_nav() -> str:
    return "RESEARCH  |  SIMULATE  |  ANALYZE  |  EXECUTE  |  LEARN"


def input_box() -> str:
    return "> Ask DELTA anything, research a strategy, analyze a market...  [/ commands · Ctrl+K kill]"


def status_text(s: dict) -> str:
    return (
        f"MARKET {s.get('market')} | DATA {s.get('data')} | RISK {s.get('risk')} | "
        f"MODE {s.get('mode')} | MODEL {s.get('model')} | "
        f"BROKER {s.get('broker')} | KILL SWITCH {s.get('kill')}"
    )


def format_quant_num(val: float | int | str, kind: str = "auto", explicit_sign: bool = False) -> str:
    """Instant readable institutional quant formatting.

    Bad:  12431221.239182
    Good: $12.43M
    Pct:  +2.41%
    Mult: 1.28×
    Bps:  18.2 bps
    """
    try:
        v = float(val)
    except (ValueError, TypeError):
        return str(val)

    if kind == "currency":
        sign = "+" if explicit_sign and v > 0 else ("-" if v < 0 else "")
        abs_v = abs(v)
        if abs_v >= 1_000_000_000:
            return f"{sign}${abs_v / 1_000_000_000:.2f}B"
        if abs_v >= 1_000_000:
            return f"{sign}${abs_v / 1_000_000:.2f}M"
        if abs_v >= 1_000:
            return f"{sign}${abs_v / 1_000:.2f}K"
        return f"{sign}${abs_v:.2f}"

    if kind == "percent":
        sign = "+" if v > 0 or explicit_sign else ""
        return f"{sign}{v:.2f}%"

    if kind == "ratio":
        return f"{v:.2f}×"

    if kind == "bps":
        sign = "+" if explicit_sign and v > 0 else ""
        return f"{sign}{v:.1f} bps"

    # auto
    abs_v = abs(v)
    if abs_v >= 1_000:
        return format_quant_num(v, kind="currency", explicit_sign=explicit_sign)
    return f"{v:.2f}"
