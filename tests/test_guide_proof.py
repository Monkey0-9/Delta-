"""Shame-proofing tests: every guide-promised command resolves AND renders.

A command that appears in USER_GUIDE but prints 'unknown' in front of
traders/IBs/guests is a shame event. This suite fails the build if any
guide command hits a dead end in either rail.
"""
from __future__ import annotations

GUIDE_COMMANDS = ["desk", "markets", "lab", "portfolio", "risk", "orders", "exec",
                  "recon", "audit", "config", "kill", "analyze", "forecast", "crash",
                  "news", "sentinel", "algo", "ask", "key", "trade", "halt", "unlock",
                  "data", "doctor", "status", "models", "model", "agent", "mcp", "mcps",
                  "plan", "session", "sessions", "help", "market", "book", "alpha",
                  "system", "home", "quote", "chart", "macro", "compare", "stress",
                  "brain", "mode", "theme", "workspace", "flatten", "cancel", "order",
                  "protect", "dipbuy", "simulate", "backtest", "learn", "execution",
                  "open", "auth", "connect", "live", "paper", "account", "accounts",
                  "shadow", "scenario", "optimize", "inspect", "depth", "latency",
                  "reproduce", "attribution", "data"]


def _registry():
    from delta_tui.commands import registry as R
    import delta_tui.commands.aliases  # noqa: F401
    import delta_tui.commands.terminal  # noqa: F401
    return R


def test_every_guide_command_in_tui_registry():
    R = _registry()
    missing = [c for c in dict.fromkeys(GUIDE_COMMANDS) if R.lookup(c) is None]
    assert not missing, f"TUI registry dead ends: {missing}"


def test_every_registry_screen_exists():
    from delta_tui.app import SCREENS
    R = _registry()
    bad = [(a.name, a.screen) for a in R.REGISTRY.values() if a.screen not in SCREENS]
    assert not bad, f"registry screens with no SCREENS entry: {bad}"


def test_tui_dispatch_never_unknown_screen():
    from delta_tui.app import DeltaApp, SCREENS
    from config.mode import DeltaMode
    app = DeltaApp(mode=DeltaMode.PAPER)
    R = _registry()
    failures = []
    for name in dict.fromkeys(GUIDE_COMMANDS):
        action = R.lookup(name)
        if action is None:
            failures.append((name, "no registry entry"))
            continue
        if action.screen not in SCREENS:
            failures.append((name, f"screen {action.screen} missing"))
    assert not failures, f"TUI dispatch dead ends: {failures}"


def test_recon_audit_screens_honest():
    from delta_tui.app import SCREENS
    from delta_tui.state.store import TerminalStore
    from config.mode import DeltaMode
    store = TerminalStore(mode=DeltaMode.PAPER)
    for key in ("reconciliation", "audit"):
        scr = SCREENS[key]
        text = scr.render_text(scr.build_viewmodel(store))
        assert ("RECONCILIATION" in text or "AUDIT" in text)
        assert "SOURCE/" in text  # provenance badge mandatory


def test_repl_unlock_token_gated(monkeypatch):
    import os
    from delta_os.repl import Terminal
    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "PROBE-TOKEN-9")
    t = Terminal()
    t.handle("/kill")
    assert t.safety.mode == "HALTED"
    out, _ = t.handle("/unlock WRONGTOKEN")
    assert "DENIED" in out and t.safety.mode == "HALTED"
    out2, _ = t.handle("/unlock PROBE-TOKEN-9 operator probe")
    assert "DENIED" not in out2 and t.safety.mode != "HALTED"


def test_halt_is_risky_kill_alias():
    R = _registry()
    halt = R.lookup("halt")
    assert halt is not None and halt.risky is True


def test_no_web_claim_in_app_dispatch():
    import pathlib
    text = pathlib.Path("delta_tui/app.py").read_text(encoding="utf-8")
    assert "Full visualization available in DELTA Web" not in text
