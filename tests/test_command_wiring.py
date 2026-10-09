"""A4: command dispatch + palette + leader-key wiring (doctor/status/data).

Scope: dispatch + palette + key handling ONLY. No safety/kill/render claims.
TDD proof that:
  - TUI /doctor runs the REAL probe layer (mocked) and renders exactly those
    rows (no hardcoded 6/11 counts);
  - REPL /doctor + /status + /data are known commands (not `unknown`);
  - palette ranking follows ux.fuzzy_rank (not substring-only);
  - leader mapping resolves per keymap; Ctrl+K stays palette (never instant kill).
"""
from __future__ import annotations


def _fake_checks():
    from delta_os.doctor_connections import ConnCheck

    # Deliberately NOT 11 rows: proves no hardcoded 11-probe table.
    return [
        ConnCheck("probe/alpha", "READY", True, "alpha ok", 1.0, "runtime-probe", ""),
        ConnCheck("probe/beta", "NEEDS_KEY", False, "beta needs key", 1.0,
                  "runtime-probe", "fix: set key"),
        ConnCheck("probe/gamma", "DOWN", False, "gamma unreachable", 1.0,
                  "runtime-probe", "fix: retry later"),
    ]


def test_tui_doctor_runs_real_probes_no_hardcoded_counts(monkeypatch):
    import delta_os.doctor_connections as D
    from config.mode import DeltaMode
    from delta_tui.app import DeltaApp

    fake = _fake_checks()
    monkeypatch.setattr(D, "run_all", lambda vault=None: fake)
    app = DeltaApp(mode=DeltaMode.PAPER)
    out = app.dispatch("/doctor")
    # Every probe row rendered exactly as the probe layer reported.
    for c in fake:
        assert c.name in out, f"probe row missing: {c.name}"
        assert c.status in out, f"probe status missing: {c.status}"
    # Verdict reflects the mocked layer (1 ready of 3 -> CHECK-NEEDED),
    # sized to the mocked layer, never a hardcoded 11.
    assert "1/3 ready" in out
    assert "11" not in out.replace("probe/", ""), "hardcoded 11-probe count?"
    assert "CHECK-NEEDED" in out


def test_repl_doctor_status_data_known(monkeypatch):
    import delta_os.doctor_connections as D
    from delta_os.repl import Terminal

    monkeypatch.setattr(D, "run_all", lambda vault=None: _fake_checks())
    t = Terminal()
    for cmd in ("/doctor", "/status", "/data"):
        out, _ = t.handle(cmd)
        assert not out.startswith("unknown"), f"{cmd} still unknown: {out[:80]}"
    out, _ = t.handle("/doctor")
    assert "probe/alpha" in out and "READY" in out
    # Unknown-command guidance preserved for the rest of the surface.
    out, _ = t.handle("/recon")
    assert out.startswith("unknown")


def test_repl_data_honest_when_probe_fails(monkeypatch):
    from delta_os.repl import Terminal

    t = Terminal()
    monkeypatch.setattr(t.data, "quote", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("offline")))
    out, _ = t.handle("/data")
    assert "UNAVAILABLE" in out


def test_palette_ranking_uses_fuzzy():
    from delta_tui.commands.palette import entries
    from delta_tui.commands.ux import fuzzy_rank

    ranked = entries("re")
    names = [e["name"].strip("/") for e in ranked]
    # Order follows the real fuzzy ranker (top-5 exact match proves wiring).
    assert names[:5] == fuzzy_rank("re", 5)
    # Substring-only filtering would drop /risk for query "re"; fuzzy keeps it.
    assert "risk" in names, "palette still substring-only (risk missing for /re)"
    assert "research" in names


def test_palette_empty_query_keeps_priority_order():
    from delta_tui.commands.palette import format_palette_box

    box = format_palette_box("")
    for token in ("/research", "/market", "/risk", "System/AI:"):
        assert token in box


def test_leader_mapping_resolves_per_keymap():
    from delta_tui import keymap as K

    expected = {
        "ctrl+x h": "home", "ctrl+x m": "market", "ctrl+x b": "book",
        "ctrl+x r": "research", "ctrl+x a": "alpha", "ctrl+x p": "portfolio",
        "ctrl+x k": "risk", "ctrl+x e": "execution", "ctrl+x o": "orders",
        "ctrl+x s": "system", "ctrl+x n": "research_new",
        "ctrl+x t": "session_new",
    }
    for seq, target in expected.items():
        assert K.resolve(seq) == target, f"{seq} -> {K.resolve(seq)!r}"
    # Ctrl+K conflict resolved: palette per keymap, never instant kill.
    assert K.BINDINGS["ctrl+k"] == "palette"
    assert K.KILL_SEQUENCE == ("ctrl+x", "k", "kill-confirm")


def test_completer_built_from_registry():
    from delta_tui.app import build_completer_words
    from delta_tui.commands import registry as R
    import delta_tui.commands.aliases  # noqa: F401 loads aliases
    import delta_tui.commands.terminal  # noqa: F401 loads terminal surface

    words = build_completer_words()
    assert "/doctor" in words and "/status" in words and "/data" in words
    assert len(words) >= len(R.REGISTRY), "completer smaller than registry?"
    assert len(words) > 19, "completer still the hardcoded 19 words?"


def test_tui_status_honest_fields():
    from config.mode import DeltaMode
    from delta_tui.app import DeltaApp

    out = DeltaApp(mode=DeltaMode.PAPER).dispatch("/status")
    for token in ("workspace", "model", "broker", "risk", "mcp", "gpu"):
        assert token in out.lower(), f"status missing honest field: {token}"


def test_tui_data_attempts_probe_and_stays_honest(monkeypatch):
    from config.mode import DeltaMode
    from delta_os.data_router import Provenance, QuoteFrame
    from delta_tui.app import DeltaApp
    import pandas as pd

    app = DeltaApp(mode=DeltaMode.PAPER)
    seen = {}

    def _fake_quote(symbol, days=30):
        seen["called"] = True
        frame = pd.DataFrame(
            {"open": [100.0], "high": [101.0], "low": [99.0],
             "close": [100.0], "volume": [1000]})
        return QuoteFrame(frame, Provenance("TIER3-SYNTH",
                                            "[SYNTHETIC SIMULATION ONLY]",
                                            symbol, "now"))

    be = app.backend()
    assert be is not None and be.data is not None
    monkeypatch.setattr(be.data, "quote", _fake_quote)
    out = app.dispatch("/data")
    assert seen.get("called") is True, "dispatching /data never probed a feed"
    assert "DATA" in out
    assert "UNAVAILABLE" in out, "synthetic-only feed must stay UNAVAILABLE"
