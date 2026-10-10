"""Java lane promotion gates: Group29 R-gates pre-certification (PAPER/SIM only).

Fail-closed evidence: VERSION handshake, STATUS telemetry, LIVE refusal,
flap/HALT + reset, disconnect -> PENDING_RECONCILE + DEGRADED, audit hash,
OMS three-way MATCHED, spec error codes.
"""
import socket

import pytest

from execution.adapters import java_gateway_adapter as adapter_mod
from execution.adapters.java_gateway_adapter import (
    JavaGatewayAdapter,
    LaneHalted,
    LiveProhibited,
)


@pytest.fixture(scope="module")
def gw():
    import shutil
    if shutil.which("java") is None:
        pytest.skip("java not available in this environment — Java lane UNAVAILABLE (PAPER/SIM Python OMS remains authoritative).")
    a = JavaGatewayAdapter(port=9011, auto_spawn=True)
    a.start()
    yield a
    a.stop()


def test_version_handshake_and_status(gw):
    assert gw.lane == "HEALTHY"
    st = gw.status()
    assert set(st) >= {"ring_depth", "cursor", "uptime_ms", "active_symbols", "lane"}
    assert st["uptime_ms"] >= 0


def test_live_routed_order_refused_without_socket():
    a = JavaGatewayAdapter(port=9199, auto_spawn=False)
    with pytest.raises(LiveProhibited):
        a.match_order("LIVE-1", "NVDA", "BUY", "LMT", 100.0, 10, mode="LIVE")


def test_flap_detector_halts_and_reset_clears():
    a = JavaGatewayAdapter(port=9198, auto_spawn=False)
    with pytest.raises(LaneHalted):
        for _ in range(3):
            a._record_boot()
    assert a.lane == "HALTED"
    with pytest.raises(LaneHalted):
        a.start()
    a.reset_lane()
    assert a.lane == "JAVA_UNAVAILABLE"


def test_disconnect_marks_pending_reconcile_and_degraded(gw):
    gw.pending_reconcile["ORPHAN-1"] = {"symbol": "NVDA", "qty": 5, "status": "IN_FLIGHT"}
    gw._mark_degraded("test-disconnect")
    assert gw.lane in ("DEGRADED", "HALTED")
    assert gw.pending_reconcile["ORPHAN-1"]["status"] == adapter_mod.PENDING_RECONCILE
    gw.pending_reconcile.pop("ORPHAN-1", None)
    gw.lane = "HEALTHY"


def test_audit_emit_returns_sha256():
    h = adapter_mod._audit("java_promotion_probe", {"ok": True})
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_oms_reconcile_matched(gw):
    from execution.oms.state_machine import OMS
    from execution.reconciliation.engine import ReconciliationEngine, ReconciliationStatus

    oms = OMS()
    oms.create(order_id="REC-1", idempotency_key="k-rec-1", asset="NVDA", quantity=10.0)
    gw.pending_reconcile["REC-1"] = {"symbol": "NVDA", "fill_qty": 10.0,
                                    "price": 185.0, "status": "IN_FLIGHT"}
    try:
        results = gw.reconcile_with_oms(oms, ReconciliationEngine())
        row = next(r for r in results if r.order_id == "REC-1")
        assert row.status == ReconciliationStatus.MATCHED
    finally:
        gw.pending_reconcile.pop("REC-1", None)


def test_spec_error_code_on_unknown_command(gw):
    with socket.create_connection((gw.host, gw.port), timeout=2.0) as s:
        s.sendall(b"FROBNICATE\n")
        resp = s.recv(1024).decode()
    assert resp.strip() == "ERR ERR_UNKNOWN_COMMAND"
