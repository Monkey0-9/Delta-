"""Terminal themes: ANSI token coloring (tickers cyan, BUY green, SELL red,
commands magenta). No dependencies. Unknown theme -> ValueError listing names."""
from __future__ import annotations

import re

THEMES = {
    "bloomberg-amber": {"base": "\x1b[33m", "ticker": "\x1b[93m", "buy": "\x1b[33;1m",
                        "sell": "\x1b[31m", "cmd": "\x1b[35m", "reset": "\x1b[0m"},
    "tokyo-night": {"base": "\x1b[36m", "ticker": "\x1b[96m", "buy": "\x1b[92m",
                    "sell": "\x1b[91m", "cmd": "\x1b[95m", "reset": "\x1b[0m"},
    "matrix": {"base": "\x1b[32m", "ticker": "\x1b[92m", "buy": "\x1b[92;1m",
               "sell": "\x1b[31m", "cmd": "\x1b[35m", "reset": "\x1b[0m"},
    "monokai": {"base": "\x1b[37m", "ticker": "\x1b[96m", "buy": "\x1b[92m",
                "sell": "\x1b[91m", "cmd": "\x1b[95m", "reset": "\x1b[0m"},
    "plain": {"base": "", "ticker": "", "buy": "", "sell": "",
              "cmd": "", "reset": ""},
}

_TICKER = re.compile(r"\b([A-Z]{2,5})\b(?=\s|$)|\$([A-Z]{1,5})\b")


def paint(text: str, theme: str = "monokai") -> str:
    t = THEMES.get(theme)
    if t is None:
        raise ValueError(f"unknown theme {theme}; choose {sorted(THEMES)}.")
    if theme == "plain":
        return text
    out = re.sub(r"(?m)^(/\w+)", t["cmd"] + r"\1" + t["reset"], text)
    out = re.sub(r"\bBUY\b", t["buy"] + "BUY" + t["reset"], out)
    out = re.sub(r"\bSELL\b", t["sell"] + "SELL" + t["reset"], out)
    return out


__all__ = ["THEMES", "paint"]
