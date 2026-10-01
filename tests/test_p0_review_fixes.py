"""P0 review regression tests — kill truthfulness, no-fake bridge, exact CONFIRM."""
from __future__ import annotations


def test_kill_step_requires_exact_confirm_and_backend():
    from delta_tui.app import DeltaApp

    class DeadBE:
        def handle(self, t):
            raise RuntimeError("engine down")
    app = DeltaApp()
    out = app._kill_step("/kill unconfirmed")
    assert "HALTED" not in out  # substring must not trigger
    app._backend = DeadBE()
    # force backend() to return our dead double
    app.backend = lambda: app._backend
    out2 = app._kill_step("/kill CONFIRM")
    assert out2.startswith("KILL FAILED")  # backend error -> never HALTED


def test_kill_step_backend_must_confirm_halted():
    from delta_tui.app import DeltaApp

    class FakeSafety:
        mode = "MANUAL"

    class FakeBE:
        safety = FakeSafety()

        def handle(self, t):
            return ("ok-but-not-halted", None)

    app = DeltaApp()
    app._backend = FakeBE()
    out = app._kill_step("/kill CONFIRM")
    assert out.startswith("KILL FAILED")
    assert "HALTED" not in out.split("—")[0]


def test_bridge_no_hardcoded_fakes():
    from delta_os.bridge import DeltaBridge
    b = DeltaBridge()
    st = b.get_state()
    assert st["broker"]["connected"] == "UNAVAILABLE"
    assert st["risk"]["killswitch_armed"] == "UNAVAILABLE"
    assert st["models"]["confidence"] is None
    assert st["execution"] == []
    assert st["agents"] == []
    assert "provenance" in st["market_status_provenance"].lower() or st["market_status_provenance"] in ("LIVE", "UNAVAILABLE")


def test_bridge_kill_requires_true_and_unlock_denied():
    from delta_os.bridge import DeltaBridge
    b = DeltaBridge()
    assert b.kill_switch(confirm=False)["status"] == "ARMED"
    assert b.unlock(actor="anyone", reason="x")["status"] == "DENIED"


def test_open_and_finance_agent_honest():
    from delta_tui.app import DeltaApp
    app = DeltaApp()
    o = app._cmd_open([])
    assert "NOT IMPLEMENTED" in o
    f = app.dispatch("/finance-agent")
    assert "0.76" not in f and "3 relevant" not in f
