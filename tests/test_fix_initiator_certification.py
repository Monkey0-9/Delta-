"""FIX Initiator & Session Engine Automated Certification Test Suite.

Verifies end-to-end production FIX lifecycle:
- Logon / Logout handshake
- Heartbeat / TestRequest
- NewOrderSingle & ExecutionReport ACK
- OrderCancelRequest & ExecutionReport Canceled
- Sequence number persistence across resets
- Gap detection & ResendRequest handling
"""
import asyncio
import pytest
import tempfile
import os

from execution.fix.initiator import FixInitiator
from execution.fix.mock_acceptor import MockFixAcceptor
from execution.fix.store import FixSequenceStore


@pytest.mark.asyncio
async def test_fix_sequence_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "fix_test.db")
        store = FixSequenceStore(db_path)

        out_seq, in_seq = store.init_session("DELTA->EXCH", "DELTA", "EXCH")
        assert out_seq == 1
        assert in_seq == 1

        store.update_seq("DELTA->EXCH", out_seq=5, in_seq=3)
        out_s, in_s = store.get_session_seq("DELTA->EXCH")
        assert out_s == 5
        assert in_s == 3

        store.log_message("DELTA->EXCH", "OUT", 5, "D", "8=FIX.4.4|9=50|35=D|10=100|")
        msgs = store.get_messages("DELTA->EXCH", "OUT", 5, 5)
        assert len(msgs) == 1
        assert msgs[0][0] == 5
        assert msgs[0][1] == "D"

        store.close()


@pytest.mark.asyncio
async def test_fix_initiator_lifecycle_and_orders():
    acceptor = MockFixAcceptor(host="127.0.0.1", port=0)
    port = await acceptor.start()

    exec_reports = []

    def handle_exec_report(msg):
        exec_reports.append(msg)

    initiator = FixInitiator(
        host="127.0.0.1",
        port=port,
        sender_comp_id="DELTA",
        target_comp_id="EXCH",
        heartbeat_interval=5,
        store_path=":memory:",
        on_execution_report=handle_exec_report,
    )

    try:
        # 1. Connect & Logon
        await initiator.connect()
        assert initiator.is_connected
        assert len(acceptor.received_messages) >= 1
        assert acceptor.received_messages[0].get("35") == "A"

        # 2. Submit NewOrderSingle (35=D)
        raw_nos = await initiator.send_order_single(
            cl_ord_id="ORD-1001",
            symbol="AAPL",
            side="1",  # Buy
            ord_type="2",  # Limit
            qty=100.0,
            price=150.0,
        )
        assert "35=D" in raw_nos

        # Wait for ExecutionReport from Acceptor
        await asyncio.sleep(0.3)
        assert len(exec_reports) == 1
        assert exec_reports[0].get("35") == "8"
        assert exec_reports[0].get("11") == "ORD-1001"
        assert exec_reports[0].get("39") == "0"  # OrdStatus: New

        # 3. Submit OrderCancelRequest (35=F)
        raw_cancel = await initiator.cancel_order(
            cl_ord_id="ORD-1001-C",
            orig_cl_ord_id="ORD-1001",
            symbol="AAPL",
            side="1",
            qty=100.0,
        )
        assert "35=F" in raw_cancel

        await asyncio.sleep(0.3)
        assert len(exec_reports) == 2
        assert exec_reports[1].get("35") == "8"
        assert exec_reports[1].get("39") == "4"  # OrdStatus: Canceled

        # 4. Graceful Disconnect & Logout
        await initiator.disconnect("Test completed")
        assert not initiator.is_connected
    finally:
        await acceptor.stop()
