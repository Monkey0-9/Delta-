"""P6: TUI command convergence + /brain lifecycle (no textual import needed)."""
from delta_os.repl import Terminal
from delta_tui.commands.registry import lookup


def test_registry_covers_brain_verbs():
    for name in ("brain", "alerts", "protect", "dipbuy"):
        assert lookup(name) is not None, name


def test_brain_alias_and_lifecycle():
    t = Terminal()
    out, _ = t.handle("/brain status")
    assert "SENTINEL" in out
    out, _ = t.handle("/brain start")
    assert "STARTED" in out
    try:
        out, _ = t.handle("/brain stop")
        assert "STOPPED" in out
    finally:
        if t.sentinel is not None:
            t.sentinel.stop()


def test_models_and_alerts_commands():
    t = Terminal()
    out, _ = t.handle("/models list")
    assert "delta-fm-research" in out and "READY" in out
    out, _ = t.handle("/alerts")
    assert "terminal log" in out and "telegram" in out
    out, _ = t.handle("/mcp")
    assert "UNPROBED" in out and "CONNECTED" not in out
