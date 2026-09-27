"""Phase 5 gates: FIX, real-time risk, compliance, ops health, live refusal."""
from __future__ import annotations

import pytest


def test_fix_roundtrip_and_tamper():
    from execution.fix import codec as C

    raw = C.new_order_single(C.NewOrder("C1", "AAPL", "1", 100, "150.25", "2"),
                             7, "DELTA", "VENUE", "20260927-12:00:00.000")
    msg = C.parse(raw)
    assert msg["35"] == "D" and msg["34"] == "7" and msg["44"] == "150.25"
    C.require(msg, "D")
    bad_sum = raw[:-7] + "000" + C.SOH
    with pytest.raises(C.FixReject):
        C.parse(bad_sum)
    bad_len = raw.replace("9=", "9=1", 1)
    with pytest.raises(C.FixReject):
        C.parse(bad_len)
    with pytest.raises(C.FixReject):
        C.parse("8=FIX.4.2" + C.SOH + raw.split(C.SOH, 1)[1])
    with pytest.raises(C.FixReject):
        C.new_order_single(C.NewOrder("C2", "A", "9", 1, None, "2"), 1, "S", "T",
                           "20260927-12:00:00.000")


def test_fix_session_gap_heartbeat_stale():
    from execution.fix import codec as C
    from execution.fix.session import FixSession

    a, b = FixSession("A", "B"), FixSession("B", "A")
    assert C.parse(a.send_logon())["35"] == "A"
    # advance b's outbound so its next message has seq 2; deliver to a first
    _ = b.send_heartbeat()
    late = b.send_heartbeat()
    gap = a.receive(late)
    assert "__gap__" in gap and "__resend__" in gap
    # test-request echo
    a2 = FixSession("A", "B")
    b2 = FixSession("B", "A")
    echo_parsed = C.parse(b2.send([("35", "1"), ("112", "PING")]))
    out = a2.receive(b2.log[-1])
    assert out["35"] == "1"  # received; echo queued in a2's log
    assert C.parse(a2.log[-1])["35"] == "0"
    assert echo_parsed["112"] == "PING"
    # stale sequence halts
    c = FixSession("A", "B")
    c.in_seq = 50
    stale = C.build([("35", "0")], 3, "B", "A")
    with pytest.raises(C.FixReject):
        c.receive(stale)
    assert c.halted
    with pytest.raises(C.FixReject):
        c.send_heartbeat()
    c.reset()
    assert not c.halted


def test_paper_venue_full_fill_and_cancel():
    from execution.fix import codec as C
    from execution.fix.paper_venue import VENUE, PaperFixVenue
    from execution.fix.session import FixSession

    v2 = PaperFixVenue(seed=7)
    cli = FixSession("DELTA", VENUE)
    # proper handshake: logon (1) then order (2), delivered in order
    assert C.parse(v2.on_message(cli.send_logon(), 100.0, "t")[0])["35"] == "A"
    nos = C.new_order_single(C.NewOrder("O1", "AAPL", "1", 100, "150.00", "2"),
                             cli.out_seq, "DELTA", VENUE, "20260927-12:00:00.000")
    cli.out_seq += 1
    reps = v2.on_message(nos, 100.0, "20260927-12:00:01.000")
    rep = C.parse(reps[0])
    assert rep["35"] == "8" and rep["39"] == "2" and rep["122"] == VENUE
    assert float(rep["31"]) == pytest.approx(100.0 * 1.00025, rel=1e-9)
    # duplicate ClOrdID rejected at business level (fresh seq, same ClOrdID)
    nos2 = C.new_order_single(C.NewOrder("O1", "AAPL", "1", 100, "150.00", "2"),
                              cli.out_seq, "DELTA", VENUE, "20260927-12:00:02.000")
    cli.out_seq += 1
    dup = v2.on_message(nos2, 100.0, "t")
    assert C.parse(dup[0])["35"] == "j"
    # resting paper order cancelable (client seq now 3)
    v2.rest("R1", {"symbol": "AAPL", "qty": 10})
    cx = C.build([("35", "F"), ("11", "C9"), ("41", "R1"), ("55", "AAPL"),
                  ("54", "1"), ("60", "t")], cli.out_seq, "DELTA", VENUE)
    cli.out_seq += 1
    assert C.parse(v2.on_message(cx, 100.0, "t")[0])["39"] == "4"
    cx2 = C.build([("35", "F"), ("11", "C10"), ("41", "R1"), ("55", "AAPL"),
                   ("54", "1"), ("60", "t")], cli.out_seq, "DELTA", VENUE)
    cli.out_seq += 1
    assert C.parse(v2.on_message(cx2, 100.0, "t")[0])["39"] == "8"  # already gone


def test_realtime_monitor_trips_and_audits():
    from risk.realtime import RealtimeRiskMonitor

    m = RealtimeRiskMonitor(max_orders_per_min=3, max_gross_position=1000,
                            max_day_loss=100.0)
    assert m.on_order(now_s=0.0) is True
    assert m.on_order(now_s=1.0) is True
    assert m.on_order(now_s=2.0) is True
    assert m.on_order(now_s=3.0) is False  # 4th inside 60s window trips
    assert m.tripped and m.verify_audit()
    with pytest.raises(ValueError):
        m.reset("", "")
    st = m.status()
    assert st["tripped"] and st["audit_ok"]
    m.reset(actor="ops", reason="test reset")
    assert not m.tripped


def test_realtime_loss_trip():
    from risk.realtime import RealtimeRiskMonitor

    m = RealtimeRiskMonitor(max_day_loss=100.0)
    assert m.on_fill("A", 10.0, 10.0) is True
    assert m.on_fill("A", 0.0, 10.0, realized_delta=-150.0) is False
    assert m.tripped


def test_compliance_chain_and_best_exec():
    from governance.compliance import ComplianceLog

    log = ComplianceLog()
    log.append("order", {"order_id": "O1"})
    log.append("fill", {"order_id": "O1", "side": "buy", "price": 100.10,
                        "arrival_px": 100.00})
    log.append("fill", {"order_id": "O2", "side": "buy", "price": 102.00,
                        "arrival_px": 100.00})
    assert log.verify()
    rep = log.best_execution_report(tolerance_bps=10.0)
    assert rep["fills"] == 2 and rep["violations"] == 1
    assert rep["rows"][0]["flag"] is False and rep["rows"][1]["flag"] is True


def test_ops_health_rollup_and_ack():
    from operations.health import HealthMonitor

    h = HealthMonitor()
    h.register("feed", stale_after_s=10, down_after_s=20)
    h.register("risk", stale_after_s=10, down_after_s=20)
    T0 = 1_700_000_000.0
    h.heartbeat("feed", now_s=T0)
    h.heartbeat("risk", now_s=T0)
    assert h.health(now_s=T0)["rollup"] == "UP"
    assert h.health(now_s=T0 + 100)["rollup"] == "DOWN"
    h.acknowledge("feed", actor="ops")
    h.acknowledge("risk", actor="ops")
    assert h.health(now_s=T0 + 100)["rollup"] == "DEGRADED"
    h.heartbeat("feed", now_s=T0 + 100)
    h.heartbeat("risk", now_s=T0 + 100)
    assert h.health(now_s=T0 + 100)["rollup"] == "UP"
    h.dead_letter({"id": 1}, "parse fail")
    assert h.health(now_s=T0 + 100)["dead_letters"] == 1
    import pytest as _pt

    with _pt.raises(ValueError):
        h.register("feed")
    with _pt.raises(ValueError):
        h.heartbeat("ghost")


def test_live_gateway_refuses_and_arms_paper_only(monkeypatch):
    monkeypatch.delenv("DELTA_LIVE", raising=False)
    from brokers.live import LiveAuthorization, LiveBlocked, submit_live

    with pytest.raises(LiveBlocked):
        submit_live({"symbol": "AAPL", "quantity": 1})
    with pytest.raises(LiveBlocked):  # no real venue adapter exists, ever
        submit_live({"symbol": "AAPL", "quantity": 1}, venue="NYSE")
    monkeypatch.setenv("DELTA_LIVE", "ARMED")
    with pytest.raises(LiveBlocked):  # armed but no authorization
        submit_live({"symbol": "AAPL", "quantity": 1})
    auth = LiveAuthorization("risk-committee", "paper verification", "DELTA-PAPER",
                             "2999-01-01T00:00:00+00:00")
    with pytest.raises(LiveBlocked):  # kill switch active blocks
        submit_live({"symbol": "AAPL", "quantity": 1}, auth=auth, kill_active=True)
    r = submit_live({"symbol": "AAPL", "quantity": 1}, auth=auth, kill_active=False)
    assert r["status"] == "ROUTED-TO-TEST-VENUE" and "NOT a live" in r["warning"]
    expired = LiveAuthorization("a", "b", "DELTA-PAPER", "2000-01-01T00:00:00+00:00")
    with pytest.raises(LiveBlocked):
        submit_live({"symbol": "AAPL", "quantity": 1}, auth=expired, kill_active=False)
