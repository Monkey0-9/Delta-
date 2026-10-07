"""Audit-gap closure tests: DATA screen, bridge handle_command, /data registry, commands.toml."""
from __future__ import annotations

from pathlib import Path


def test_data_screen_registered_and_honest():
    from delta_tui.app import SCREENS
    from delta_tui.screens.base import SCREEN_IDS
    assert "data" in SCREENS and "data" in SCREEN_IDS
    from delta_tui.state.store import TerminalStore
    from config.mode import DeltaMode
    store = TerminalStore(mode=DeltaMode.PAPER)
    scr = SCREENS["data"]
    vm = scr.build_viewmodel(store)
    text = scr.render_text(vm)
    assert text.startswith("DATA [PAPER]")
    assert "UNAVAILABLE" in text  # no snapshot → honest
    assert "quality" in text and "freshness" in text


def test_bridge_handle_command_ready():
    from delta_os.bridge import handle_command
    import inspect
    assert callable(handle_command)
    sig = inspect.signature(handle_command)
    assert "text" in sig.parameters


def test_data_command_in_registry_and_toml():
    from delta_tui.commands.registry import lookup
    assert lookup("data") is not None
    assert lookup("/data").screen == "data"
    toml_path = Path(__file__).resolve().parents[1] / "config" / "commands.toml"
    assert toml_path.exists()
    text = toml_path.read_text()
    assert "[commands.data]" in text and "[commands.doctor]" in text
    assert 'screen = "data"' in text
