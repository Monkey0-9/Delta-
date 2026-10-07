"""Model/MCP/think/key proof: switching routes inference, settings persist, keys work.

Every failure here was reproduced live from a user report. This suite fails
the build if switching becomes a label-swap again or settings evaporate.
"""
from __future__ import annotations


def test_switch_pins_real_gateway_route():
    from delta_os.repl import Terminal
    t = Terminal()
    out, _ = t.handle("/model switch delta-fm-research")
    assert "Switched" in out and t.model_name == "delta-fm-research"
    # local brain: gateway commentary role untouched, brain path used
    assert t.models.active["commentary"] == "qwen-3.6"


def test_key_add_unlocks_switch_with_temp_vault(tmp_path, monkeypatch):
    import os
    from delta_os.repl import Terminal
    from delta_os.vault import Vault
    monkeypatch.setenv("DELTA_VAULT_PASS", "probe-pass-123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # force vault path, not env
    # point default vault path at tmp by pre-opening our own vault on Terminal
    t = Terminal()
    v = Vault(tmp_path / "vault.bin")
    v.unlock("probe-pass-123")
    t.vault = v
    t.models.vault = v
    out, _ = t.handle("/key anthropic sk-probe-key")
    assert "stored" in out
    out2, _ = t.handle("/model switch claude-3-7-sonnet")
    assert "Switched" in out2, out2
    assert t.model_name == "claude-3-7-sonnet"
    assert t.models.active["commentary"] == "claude-3-7-sonnet"
    assert t.models._key("anthropic") == "sk-probe-key"
    os.environ.pop("ANTHROPIC_API_KEY", None)


def test_switch_refuses_keyless_cloud():
    from delta_os.repl import Terminal
    t = Terminal()
    assert t.vault is None
    out, _ = t.handle("/model switch claude-opus-5-5")
    assert "refused" in out and "NEEDS_KEY" in out
    assert t.model_name == "delta-fm-research"  # unchanged


def test_switch_refuses_unwired_template_even_when_ready(monkeypatch):
    from delta_os.repl import Terminal
    from delta_os.vault import Vault
    import tempfile, pathlib
    td = tempfile.mkdtemp()
    monkeypatch.setenv("DELTA_VAULT_PASS", "p2")
    t = Terminal()
    v = Vault(pathlib.Path(td) / "v.bin")
    v.unlock("p2")
    t.vault = v
    t.models.vault = v
    t.handle("/key astro sk-a")
    t.handle("/models add astro-6-0 https://example.invalid astro-6-0")
    out, _ = t.handle("/model switch astro-6-0")
    assert "refused" in out and "no inference rail" in out


def test_effort_thinking_persist_and_apply():
    from delta_os.repl import Terminal
    t = Terminal()
    out, _ = t.handle("/effort high")
    assert "applied to gateway" in out
    assert t.effort == "HIGH" and t.models.effort == "HIGH"
    assert t.models.timeout_s == 60.0 and t.models.max_tokens == 2048
    out2, _ = t.handle("/thinking activity")
    assert "ACTIVITY" in out2 and t.thinking == "ACTIVITY"
    out3, _ = t.handle("/effort bogus")
    assert "Invalid effort" in out3


def test_tui_model_switch_does_not_corrupt_store():
    from delta_tui.app import DeltaApp
    from config.mode import DeltaMode
    app = DeltaApp(mode=DeltaMode.PAPER)
    out = app.dispatch("/model switch delta-fm-research")
    assert "Switched" in out
    assert app.store.model == "delta-fm-research", app.store.model


def test_tui_effort_thinking_key_passthrough():
    from delta_tui.app import DeltaApp
    from config.mode import DeltaMode
    app = DeltaApp(mode=DeltaMode.PAPER)
    assert "applied to gateway" in app.dispatch("/effort low")
    assert app.store.effort == "LOW"
    assert "ACTIVITY" in app.dispatch("/thinking activity") or "activity" in app.dispatch("/thinking activity").lower()
    assert app.store.thinking == "ACTIVITY"
    out = app.dispatch("/key")
    assert "API KEY VAULT" in out


def test_tui_no_stale_backend_bleed():
    from delta_tui.app import DeltaApp
    from config.mode import DeltaMode
    app = DeltaApp(mode=DeltaMode.PAPER)
    app.dispatch("/mcp")  # fills backend echo
    out = app.dispatch("/data")  # unrelated screen must not echo MCP table
    assert "MCP SERVERS" not in out


def test_default_agent_exists_and_legacy_alias():
    from agent.orchestrator import AGENTS
    from delta_tui.state.store import TerminalStore
    assert TerminalStore().agent in AGENTS
    from delta_tui.app import DeltaApp
    from config.mode import DeltaMode
    app = DeltaApp(mode=DeltaMode.PAPER)
    out = app.dispatch("/agent quant-researcher")
    assert "unknown agent" not in out and app.store.agent == "research-agent"
