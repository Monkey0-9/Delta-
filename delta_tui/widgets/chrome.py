"""Rich widgets — every widget takes a TYPED viewmodel, never raw strings."""
from __future__ import annotations
from typing import Any


def _safe_glyph(text: str) -> str:
    """Safe console glyph degradation for terminals lacking unicode support."""
    try:
        enc = getattr(__import__("sys").stdout, "encoding", "utf-8") or "utf-8"
        text.encode(enc)
        return text
    except Exception:
        return (text.replace("Δ", "D").replace("▲", "^").replace("●", "*").replace("○", "o")
                .replace("⬡", "[o]").replace("✧", "*").replace("❖", "[+]")
                .replace("👤", "@").replace("≡", "=").replace("∨", "v")
                .replace("╭", "+").replace("╮", "+").replace("╰", "+").replace("╯", "+")
                .replace("─", "-").replace("│", "|")
                .replace("×", "x").replace("→", "->").replace("✓", "v"))


def header_text(h: dict, state: str = "A", width: int = 100) -> str:
    """Institutional micro-header matching exact user layout."""
    mode = str(h.get("mode", "PAPER")).upper()
    market_dot = "●"
    mkt_status = "LIVE" if h.get("market_live", True) else "CLOSED"
    data_status = str(h.get("data", "HEALTHY")).upper()
    data_dot = "●" if "HEALTHY" in data_status or str(h.get("data")) == "●" else "○"
    risk_status = str(h.get("risk", "SAFE")).upper()
    risk_dot = "●" if "SAFE" in risk_status or str(h.get("risk")) == "●" else "○"
    
    clock = str(h.get("clock_utc", "14:32:18"))
    if "UTC" not in clock:
        clock = f"{clock.strip()} UTC"
    symbol = str(h.get("symbol", "")).upper()

    left = "▲ DELTA  |  QUANT INTELLIGENCE CLI"
    mode_chip = f"⬡ {mode}"

    if state.upper() == "B" or (state == "auto" and symbol):
        # State B — Active conversation header
        short_clock = clock.split()[0]
        if ":" in short_clock:
            short_clock = ":".join(short_clock.split(":")[:2])
        ctx_part = f"{symbol} · {short_clock}" if symbol else short_clock
        if width >= 100:
            right = f"{market_dot} MARKETS  {mkt_status}  |  {data_dot} DATA  {data_status}  |  {risk_dot} RISK  {risk_status}  |  {mode_chip}  |  {ctx_part}"
        else:
            right = f"{market_dot} {mkt_status} | {data_dot} {data_status} | {risk_dot} {risk_status} | {mode_chip} | {ctx_part}"
    else:
        # State A — Frontpart landing header
        if width >= 100:
            right = f"{market_dot} MARKETS  {mkt_status}  |  {data_dot} DATA  {data_status}  |  {risk_dot} RISK  {risk_status}  |  {mode_chip}  |  {clock}"
        else:
            right = f"{market_dot} {mkt_status} | {data_dot} {data_status} | {risk_dot} {risk_status} | {mode_chip} | {clock}"

    pad = max(2, width - len(left) - len(right))
    raw = left + (" " * pad) + right
    return _safe_glyph(raw)


def header_rich(h: dict, state: str = "A", width: int = 100) -> str:
    """Rich color markup for micro-header matching exact user visual specification."""
    mode = str(h.get("mode", "PAPER")).upper()
    mkt_status = "LIVE" if h.get("market_live", True) else "CLOSED"
    data_status = str(h.get("data", "HEALTHY")).upper()
    risk_status = str(h.get("risk", "SAFE")).upper()
    
    clock = str(h.get("clock_utc", "14:32:18"))
    if "UTC" not in clock:
        clock = f"{clock.strip()} UTC"
    symbol = str(h.get("symbol", "")).upper()

    left = "[bold #20C9A6]▲ DELTA[/] [dim #475569]|[/] [dim #94A3B8]QUANT INTELLIGENCE CLI[/]"
    left_len = 34

    if state.upper() == "B" or (state == "auto" and symbol):
        short_clock = clock.split()[0]
        if ":" in short_clock:
            short_clock = ":".join(short_clock.split(":")[:2])
        ctx_part = f"{symbol} · {short_clock}" if symbol else short_clock
        if width >= 100:
            right = (f"[bold #20C9A6]●[/] [dim #94A3B8]MARKETS[/] [bold #10B981]{mkt_status}[/] [dim #475569]|[/] "
                     f"[bold #20C9A6]●[/] [dim #94A3B8]DATA[/] [bold #10B981]{data_status}[/] [dim #475569]|[/] "
                     f"[bold #20C9A6]●[/] [dim #94A3B8]RISK[/] [bold #10B981]{risk_status}[/] [dim #475569]|[/] "
                     f"[bold #F59E0B]⬡ {mode}[/] [dim #475569]|[/] "
                     f"[dim #94A3B8]{ctx_part}[/]")
            right_len = 66
        else:
            right = (f"[bold #20C9A6]●[/] [bold #10B981]{mkt_status}[/] [dim #475569]|[/] "
                     f"[bold #20C9A6]●[/] [bold #10B981]{data_status}[/] [dim #475569]|[/] "
                     f"[bold #20C9A6]●[/] [bold #10B981]{risk_status}[/] [dim #475569]|[/] "
                     f"[bold #F59E0B]⬡ {mode}[/] [dim #475569]|[/] "
                     f"[dim #94A3B8]{ctx_part}[/]")
            right_len = 48
    else:
        if width >= 100:
            right = (f"[bold #20C9A6]●[/] [dim #94A3B8]MARKETS[/] [bold #10B981]{mkt_status}[/] [dim #475569]|[/] "
                     f"[bold #20C9A6]●[/] [dim #94A3B8]DATA[/] [bold #10B981]{data_status}[/] [dim #475569]|[/] "
                     f"[bold #20C9A6]●[/] [dim #94A3B8]RISK[/] [bold #10B981]{risk_status}[/] [dim #475569]|[/] "
                     f"[bold #F59E0B]⬡ {mode}[/] [dim #475569]|[/] "
                     f"[dim #94A3B8]{clock}[/]")
            right_len = 66
        else:
            right = (f"[bold #20C9A6]●[/] [bold #10B981]{mkt_status}[/] [dim #475569]|[/] "
                     f"[bold #20C9A6]●[/] [bold #10B981]{data_status}[/] [dim #475569]|[/] "
                     f"[bold #20C9A6]●[/] [bold #10B981]{risk_status}[/] [dim #475569]|[/] "
                     f"[bold #F59E0B]⬡ {mode}[/] [dim #475569]|[/] "
                     f"[dim #94A3B8]{clock}[/]")
            right_len = 48

    pad = max(2, width - left_len - right_len)
    return left + (" " * pad) + right


def hero_nav() -> str:
    return "RESEARCH  |  SIMULATE  |  ANALYZE  |  EXECUTE  |  LEARN"


def input_box() -> str:
    return "> │ Ask DELTA anything, run a strategy, analyze a market, or type / for commands...       Ctrl + K  ✧"


def render_frontpart(store_or_dict: Any, width: int = 100, use_rich: bool = False) -> str:
    """Renders the exact frontpart layout from the user specification."""
    if hasattr(store_or_dict, "model"):
        model = getattr(store_or_dict, "model", "delta-fm-research")
        agent = getattr(store_or_dict, "agent", "quant-researcher")
        session = getattr(store_or_dict, "session_id", "default")
    else:
        model = store_or_dict.get("model", "delta-fm-research")
        agent = store_or_dict.get("agent", "quant-researcher")
        session = store_or_dict.get("session", "default")

    logo_lines = [
        "                     ▲",
        "                    / \\",
        "                   /   \\",
        "                  /  ▲  \\",
        "                 /  / \\  \\",
        "                /__/   \\__\\",
    ]

    if width >= 100:
        box_w = max(98, min(108, width - 4))
    else:
        box_w = max(60, width - 4)
    top_b = "╭" + "─" * (box_w - 2) + "╮"
    bot_b = "╰" + "─" * (box_w - 2) + "╯"
    side_pad = max(0, (width - box_w) // 2)

    prompt_txt = "Ask DELTA anything, run a strategy, analyze a market, or type / for commands..."
    shortcut = "Ctrl + K  ✧"
    
    # Calculate spacing inside box
    inner_w = box_w - 4
    if len(prompt_txt) + len(shortcut) + 4 <= inner_w:
        spaces = inner_w - len(prompt_txt) - len(shortcut) - 4
        clean_inner = f"> │ {prompt_txt}" + (" " * max(1, spaces)) + shortcut
    else:
        avail = max(10, inner_w - len(shortcut) - 8)
        clean_inner = f"> │ {prompt_txt[:avail]}... " + shortcut

    selectors = f"❖ Model: {model} ∨    |    👤 Agent: {agent} ∨    |    ≡ Session: {session} ∨"
    sel_pad = max(0, (width - len(selectors)) // 2)

    if use_rich:
        # Rich markup with hex colors
        inner_spaces = box_w - 4 - 5 - len(prompt_txt) - len(shortcut)
        rich_inner = (
            f"[bold #20C9A6]>[/] [dim #475569]│[/]  "
            f"[#94A3B8]{prompt_txt}[/]"
            + (" " * max(1, inner_spaces))
            + f"[bold #20C9A6]{shortcut}[/]"
        )
        rich_nav = "[dim #94A3B8]RESEARCH[/]  [dim #475569]|[/]  [dim #94A3B8]SIMULATE[/]  [dim #475569]|[/]  [dim #94A3B8]ANALYZE[/]  [dim #475569]|[/]  [dim #94A3B8]EXECUTE[/]  [dim #475569]|[/]  [dim #94A3B8]LEARN[/]"
        nav_pad = max(0, (width - 49) // 2)

        rich_sel = (
            f"[bold #20C9A6]❖[/] [dim #94A3B8]Model:[/] [bold #20C9A6]{model} ∨[/]    "
            f"[dim #475569]|[/]    "
            f"[bold #20C9A6]👤[/] [dim #94A3B8]Agent:[/] [bold #20C9A6]{agent} ∨[/]    "
            f"[dim #475569]|[/]    "
            f"[bold #20C9A6]≡[/] [dim #94A3B8]Session:[/] [bold #20C9A6]{session} ∨[/]"
        )

        lines = ["", ""]
        for l in logo_lines:
            lines.append(f"[bold #20C9A6]{l.center(width)}[/]")
        lines.extend([
            "",
            f"[bold white]{'DELTA'.center(width)}[/]",
            f"[bold #94A3B8]{'QUANT INTELLIGENCE CLI'.center(width)}[/]",
            "",
            " " * nav_pad + rich_nav,
            "",
            " " * side_pad + f"[#20C9A6]{top_b}[/]",
            " " * side_pad + f"[#20C9A6]│[/]  {rich_inner}  [#20C9A6]│[/]",
            " " * side_pad + f"[#20C9A6]{bot_b}[/]",
            "",
            " " * sel_pad + rich_sel,
            "",
        ])
        return "\n".join(lines)

    # Plain text version with safe glyphs
    lines = ["", ""]
    for l in logo_lines:
        lines.append(l.center(width))
    lines.extend([
        "",
        "DELTA".center(width),
        "QUANT INTELLIGENCE CLI".center(width),
        "",
        hero_nav().center(width),
        "",
        " " * side_pad + top_b,
        " " * side_pad + f"│ {clean_inner} │",
        " " * side_pad + bot_b,
        "",
        " " * sel_pad + selectors,
        "",
    ])
    return _safe_glyph("\n".join(lines))


def footer_text(f: dict, state: str = "A") -> str:
    """Institutional micro-footer for State A and State B."""
    mode = str(f.get("mode", "PAPER")).upper()
    risk = str(f.get("risk", "SAFE")).upper()
    model = str(f.get("model", "delta-fm-research"))
    agent = str(f.get("agent", "quant-researcher"))
    context = str(f.get("context", "none"))

    if state.upper() == "A":
        # In State A, the selectors pill bar is already the bottom of the frontpart!
        return ""
    elif state.upper() == "B":
        # State B conversation footer
        raw = f"Model {model} · Agent {agent}"
        return _safe_glyph(raw)

    # Contextual screen footer
    raw = f"Model: {model} · Agent: {agent} · Session: {f.get('session', 'default')} · Context: {context}"
    return _safe_glyph(raw)


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
