"""P0-remainder Groups 01-09: permissions, sessions, events, modal/toast, a11y,
config hashing, arch rules, command UX, responsive. Truthful, no fake metrics.
"""
from config.hashing import compatible, config_hash, snapshot
from core.architecture import check_import
from delta_tui.a11y import plain_text, strip_style, to_ascii_safe
from delta_tui.commands.ux import dispatch, fuzzy_rank, nl_to_action, unknown_guidance
from delta_tui.responsive_probe import layout_for_width
from delta_tui.security.permissions import check
from delta_tui.state.events import EventStream, FillEvent, RiskBreach
from delta_tui.state.session import SessionManager
from delta_tui.widgets.modal import ModalManager
from delta_tui.widgets.toast import ToastManager


def test_kill_needs_confirm_bypass_llm():
    d = check("kill", confirmed=False)
    assert not d.allowed and d.bypass_llm and d.needs_confirm
    d2 = check("kill", confirmed=True)
    assert d2.allowed and d2.bypass_llm


def test_risk_bypasses_llm():
    assert check("risk").bypass_llm


def test_session_new_fork_export_search(tmp_path):
    m = SessionManager(db_path=str(tmp_path / "s.sqlite"))
    s = m.new(mode="PAPER", universe="NVDA")
    f = m.fork(s.session_id)
    assert f.session_id != s.session_id
    ex = m.export(s.session_id)
    assert ex["mode"] == "PAPER"
    assert s.session_id in m.search("sess")
    assert SessionManager.mandate_hash({"a": 1}) == SessionManager.mandate_hash({"a": 1})


def test_events_typed_only():
    es = EventStream()
    got = []
    es.subscribe(got.append)
    es.publish(RiskBreach("gross", 1.0, 2.0))
    es.publish(FillEvent("o1", "paper", 10, 100.0))
    assert len(got) == 2
    try:
        es.publish("SCREEN:home")  # type: ignore
        assert False, "untyped must reject"
    except TypeError:
        pass


def test_modal_kill_confirm():
    mm = ModalManager()
    mm.confirm_kill()
    assert not mm.resolve("nope")
    assert mm.resolve("CONFIRM")
    assert mm.current() is None


def test_toast_breach_fill():
    tm = ToastManager()
    tm.breach("gross breach")
    tm.fill("fill o1")
    assert len(tm.items()) == 2


def test_a11y_ascii_nocolor_plaintext():
    assert to_ascii_safe("hi ⭐") != ""
    assert "[" not in strip_style("[red]hi[/red]", no_color=True)
    assert "risk" in plain_text("risk", "gross 1.0").lower()


def test_config_hash_snapshot_compat(tmp_path):
    cfg = {"mode": "PAPER", "universe": ["NVDA"]}
    h = config_hash(cfg)
    p = snapshot(cfg, tmp_path / "cfg.json")
    assert p.exists()
    assert compatible(h, cfg)
    assert not compatible("dead", cfg)


def test_arch_reverse_rejected():
    assert not check_import("risk/emergency/breaker.py", "delta_tui/app.py")
    assert check_import("delta_tui/app.py", "config/mode.py")


def test_ux_fuzzy_unknown_nl_dispatch():
    assert "book" in fuzzy_rank("bok")
    assert "Did you mean" in unknown_guidance("bok")
    assert nl_to_action("please kill everything") == "kill"
    assert "CONFIRM" in dispatch("/kill", confirmed=False)
    assert dispatch("/nope-cmd") != ""


def test_responsive_layouts():
    assert layout_for_width(160) == "full"
    assert layout_for_width(80) == "collapsed"
    assert layout_for_width(50, ssh=True) == "compact-ssh"


def test_width_snapshots_resize_deeplink():
    from delta_tui.navigation.deeplink import alpha_lineage
    from delta_tui.responsive_probe import display_probe, on_resize
    for w, exp in [(160, "full"), (140, "wide"), (120, "standard"), (100, "narrow"), (80, "collapsed")]:
        assert layout_for_width(w) == exp
    assert on_resize(100, 30)["layout"] == "narrow"
    assert "width" in display_probe()
    assert "momentum-v4" in alpha_lineage("momentum-v4", None)


def test_doctor_display_probe():
    from delta_tui.responsive_probe import display_probe
    p = display_probe()
    assert p["width"] > 0 and p["layout"]


def test_dependency_graph_no_crash():
    from scripts.dependency_graph import reverse_edges
    assert isinstance(reverse_edges("delta_tui"), list)
