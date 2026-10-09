"""Phase -1 regression battery: critical truth/safety fixes must stay fixed.

Each test pins one P-1.x bug: if the bug returns, the test fails loudly.
"""
import pytest


@pytest.fixture(autouse=True)
def _isolate_halt_marker(monkeypatch, tmp_path):
    """A2: kill/unlock now persist a HALT marker — keep these unit tests
    hermetic (no ~/.delta/session.json reads/writes)."""
    import delta_os.safety as _safety

    monkeypatch.setattr(_safety, "_session_path",
                        lambda: tmp_path / "session.json")


class _DeadKill:
    """Kill switch whose controls always raise (simulates broken linkage)."""
    active = True

    def activate(self):
        raise RuntimeError("linkage broken")

    def deactivate(self):
        raise RuntimeError("linkage broken")

    def assert_execution_allowed(self):
        raise RuntimeError("GLOBAL KILL SWITCH ACTIVE")


class _DeadCompliance:
    def append(self, *a, **k):
        raise RuntimeError("ledger unwritable")


class _FlakyKill:
    """activate() raises but state still flips (partial failure)."""
    active = False

    def activate(self):
        self.active = True
        raise RuntimeError("ack lost")

    def deactivate(self):
        self.active = False

    def assert_execution_allowed(self):
        if self.active:
            raise RuntimeError("GLOBAL KILL SWITCH ACTIVE")


def test_kill_all_records_activation_failure():
    from delta_os.safety import SafetyState
    s = SafetyState()
    s.kill = _FlakyKill()
    r = s.kill_all([], actor="test")
    assert s.mode == "HALTED"  # always freezes
    assert any("kill.activate FAILED" in e for e in r["errors"])


def test_kill_all_records_audit_failure():
    from delta_os.safety import SafetyState
    s = SafetyState()
    s.compliance = _DeadCompliance()
    r = s.kill_all([], actor="test")
    assert r.get("audit") == "COMPLIANCE-WRITE-FAILED"
    assert any("compliance.append FAILED" in e for e in r["errors"])


def test_unlock_refuses_when_release_fails():
    from delta_os.safety import SafetyError, SafetyState
    s = SafetyState()
    s.mode = "HALTED"
    s.kill = _DeadKill()
    with pytest.raises(SafetyError, match="still HALTED"):
        s.unlock("op", "reason")
    assert s.mode == "HALTED"  # never leaves HALTED on failure


def test_unlock_refreezes_when_audit_fails():
    from delta_os.safety import SafetyError, SafetyState
    s = SafetyState()
    s.mode = "HALTED"
    s.compliance = _DeadCompliance()
    with pytest.raises(SafetyError, match="re-frozen HALTED"):
        s.unlock("op", "reason")
    assert s.mode == "HALTED"


def test_boot_fails_closed_when_release_impossible(monkeypatch):
    import governance.kill_switch as ks_mod
    from delta_os.safety import SafetyError, SafetyState
    monkeypatch.setattr(ks_mod, "KillSwitch", _DeadKill)
    with pytest.raises(SafetyError, match="boot FAILED"):
        SafetyState()


def test_home_viewmodel_reports_unavailable_without_snapshot():
    from delta_tui.screens.home import HomeScreen
    from delta_tui.state.store import TerminalStore
    from delta_tui.viewmodels.models import HomeVM
    vm = HomeScreen().build_viewmodel(TerminalStore())
    assert isinstance(vm, HomeVM)
    assert vm.net_liq is None and vm.var99 is None
    assert vm.regime == "UNKNOWN"
    # A runtime snapshot populates it — the only honest source.
    store = TerminalStore()
    store.viewmodels["home_snapshot"] = {"net_liq": 500000.0, "regime": "RISK_ON"}
    vm2 = HomeScreen().build_viewmodel(store)
    assert vm2.net_liq == 500000.0 and vm2.regime == "RISK_ON"


def test_fundamental_domains_require_explicit_lag():
    import pandas as pd
    from data.pit.construction_pipeline import PITConstructionPipeline
    pipe = PITConstructionPipeline()
    df = pd.DataFrame({"event_time": pd.to_datetime(["2024-01-01", "2024-02-01"])})
    # Market/tick default still works (zero lag is legitimate there).
    out = pipe.assign_asof(df, domain="market")
    assert out.attrs["lag_explicit"] is False
    # Fundamentals without explicit lag: lookahead hole, must raise.
    with pytest.raises(ValueError, match="explicit publish lag"):
        pipe.assign_asof(df, domain="fundamentals")
    with pytest.raises(ValueError, match="explicit publish lag"):
        pipe.build_snapshot(df, asof="2024-06-01", domain="earnings")
    # Explicit lag works everywhere.
    ok = pipe.assign_asof(df, domain="earnings", lag="45D")
    assert ok.attrs["lag_explicit"] is True


def test_universe_excludes_unknown_listing_dates():
    from datetime import datetime, timezone
    from uuid import uuid4
    from data.security_master.master import AssetMetadata, SecurityMaster
    m = SecurityMaster()
    known = AssetMetadata(asset_id=uuid4(), ticker="KNOWN",
                          listed_date=datetime(2020, 1, 1, tzinfo=timezone.utc))
    ghost = AssetMetadata(asset_id=uuid4(), ticker="GHOST")  # no listed_date
    m.add_asset(known)
    m.add_asset(ghost)
    uni = m.get_universe_at_date(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert known.asset_id in uni
    assert ghost.asset_id not in uni  # unprovable membership, not immortal


def test_tick_timestamps_basis_guard():
    from datetime import datetime, timezone
    from data.tick_pit.timestamps import TimestampManager
    mgr = TimestampManager()
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mgr.create_timestamps(t, "X")  # tick default fine
    with pytest.raises(ValueError, match="never instantly available"):
        mgr.create_timestamps(t, "X", delay_basis="fundamentals")


def test_purge_embargo_defaults_are_fail_closed():
    from research.walk_forward.production import WalkForward
    import inspect
    sig = inspect.signature(WalkForward.__init__)
    assert sig.parameters["purge"].default == 1
    assert sig.parameters["embargo"].default == 1
    from research.alpha_factory import AlphaFactory
    sig2 = inspect.signature(AlphaFactory.run)
    assert sig2.parameters["purge"].default == 1
    assert sig2.parameters["embargo"].default == 1
    # And the windows actually separate train/test by purge+embargo.
    w = WalkForward(train_size=50, test_size=10, step=10).windows(100)[0]
    assert w.test_start - w.train_end == 2


def test_replay_exactness_is_verified_not_asserted():
    from data.pit.gate import dataset_sha, reproduce_manifest
    recs = [{"a": 1}]
    assert reproduce_manifest("E", "c", "x")["replays_pit_exactly"] is False
    assert reproduce_manifest("E", "c", dataset_sha(recs), recs)["replays_pit_exactly"] is True


def test_value_validate_is_not_vacuous():
    import pandas as pd
    from data.market.feature_engine import ValueFeature
    vf = ValueFeature(ratio="pe")
    assert vf.validate(pd.DataFrame({"pe": [1.0]})) is True
    assert vf.validate(pd.DataFrame({"close": [1.0]})) is False


def test_calibrator_refuses_without_data():
    from execution.impact.calibrator import ImpactCalibrator
    with pytest.raises(ValueError, match="insufficient fills"):
        ImpactCalibrator().calibrate_almgren_chriss()


def test_paper_report_marks_unknown_adv():
    from execution.ems.adapter import ExecutionRequest
    from execution.paper.broker import PaperBroker
    b = PaperBroker({"SPY": 100.0})  # no adv map
    ack = b.submit(ExecutionRequest("o1", "SPY", 10.0))
    assert ack.accepted
    rep = b.execution_report("o1")
    assert rep["adv_known"] is False
    assert rep["participation_rate"] is None
    assert rep["impact_bps"] is None
    assert rep["sim_status"] == "ok"
    # With adv supplied, participation is computed again.
    b2 = PaperBroker({"SPY": 100.0}, adv={"SPY": 1_000_000.0})
    b2.submit(ExecutionRequest("o2", "SPY", 10.0))
    rep2 = b2.execution_report("o2")
    assert rep2["adv_known"] is True
    assert rep2["participation_rate"] > 0


def test_calendar_fallback_is_visible():
    from data.market_reality import SessionReconstructor
    rec = SessionReconstructor()
    assert rec.calendar_status in ("REAL", "INJECTED")
    assert rec.fallback_count == 0

    class _BadCal:
        def session(self, dt):
            raise RuntimeError("boom")
    bad = SessionReconstructor(calendar=_BadCal())
    assert bad.calendar_status == "INJECTED"
    bad.label(1_000_000_000_000_000_000)  # falls back, but counted
    assert bad.fallback_count == 1
    assert bad.calendar_status == "INJECTED"  # injected cal failure is caller-owned
    assert "boom" in (bad.last_calendar_error or "")
