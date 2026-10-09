"""Leader-key map: Ctrl+X then key. Ctrl+K opens the palette (never instant kill).

Scope truth (A4):
  - Wired in the prompt_toolkit fallback loop (delta_tui/app.py run()):
    every 'ctrl+x <key>' chord stages its slash text; Tab there is
    completion, NOT next_pane.
  - The minimal Textual shell (run_textual) passes raw text only: slash
    commands work, key chords don't (no popup nav there either — palette is
    a fuzzy-ranked list + Tab completion; see commands/palette.py).
  - 'tab' -> next_pane applies to a multi-pane Textual shell only.
Kill path unchanged: Ctrl+X K opens the risk cockpit; halting still needs
typed /kill CONFIRM (see DeltaApp._kill_step).
"""
from __future__ import annotations

LEADER = "ctrl+x"

BINDINGS: dict[str, str] = {
    "ctrl+x h": "home",
    "ctrl+x m": "market",
    "ctrl+x b": "book",
    "ctrl+x r": "research",
    "ctrl+x a": "alpha",
    "ctrl+x p": "portfolio",
    "ctrl+x k": "risk",       # risk cockpit; kill needs confirm below
    "ctrl+x e": "execution",
    "ctrl+x o": "orders",
    "ctrl+x s": "system",
    "ctrl+x n": "research_new",
    "ctrl+x t": "session_new",
    "ctrl+p": "palette",
    "ctrl+k": "palette",      # Image 1 hint: opens / palette + kill shortcut hint
    "ctrl+o": "open",         # browser handoff
    "/": "palette",
    "escape": "back",
    # Fallback REPL loop scope: Tab is prompt_toolkit completion there.
    # next_pane only exists in the Textual multi-pane shell.
    "tab": "next_pane",  # textual-only; fallback loop keeps Tab==completion
}

# Emergency sequence: leader, then K, then typed confirmation. Bypasses LLM.
KILL_SEQUENCE = ("ctrl+x", "k", "kill-confirm")

# A4: slash text each leader target opens in the fallback-loop input loop
# (buffer text only — nothing dispatches without Enter; kill still needs
# typed /kill CONFIRM, never a keypress).
LEADER_SLASH: dict[str, str] = {
    "home": "/home",
    "market": "/market",
    "book": "/book",
    "research": "/research",
    "alpha": "/alpha",
    "portfolio": "/portfolio",
    "risk": "/risk",
    "execution": "/execution",
    "orders": "/orders",
    "system": "/system",
    "research_new": "/research ",
    "session_new": "/session ",
    "palette": "/",
    "open": "/open",
    "back": "",
    "next_pane": "",
}


def _norm(seq: str) -> str:
    """Normalize 'Ctrl+X H' / 'c-x h' / 'ctrl+x,h' to 'ctrl+x h'."""
    s = (seq or "").lower().replace(",", " ")
    s = " ".join(s.split())
    parts = [("ctrl+x" if tok in ("c-x", "cx", "ctrlx") else tok)
             for tok in s.split(" ")]
    return " ".join(parts)


def resolve(seq: str) -> str | None:
    """Resolve a key sequence to its action name per BINDINGS.

    Accepts 'ctrl+x h', 'c-x h', 'Ctrl+X H'. Returns None when unbound.
    Single keys ('ctrl+k', 'ctrl+p', '/', 'tab', 'escape') resolve too.
    """
    key = _norm(seq)
    if key in BINDINGS:
        return BINDINGS[key]
    # single-letter leader shorthand: 'ctrl+x' + 'h' passed separately?
    return None


def leader_slash(action: str) -> str:
    """Slash text the fallback loop stages for a leader action ('' = no-op)."""
    return LEADER_SLASH.get(action or "", "")
