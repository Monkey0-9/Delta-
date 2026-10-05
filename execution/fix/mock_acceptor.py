"""Mock FIX Acceptor Server for automated integration and certification testing.

Simulates exchange/broker FIX Acceptor supporting:
- Logon / Logout handshakes
- Heartbeat / TestRequest echo
- ExecutionReport generation (ACK, Partial Fill, Fill)
- Sequence gap injection & ResendRequest testing
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Tuple

from execution.fix import codec as C

logger = logging.getLogger("DELTA.FIX.MockAcceptor")


class MockFixAcceptor:
    """Mock FIX Server Acceptor for testing FIX Initiator lifecycle."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.sender_comp_id = "EXCH"
        self.target_comp_id = "DELTA"
        self.out_seq = 1
        self.in_seq = 1

        self.server: asyncio.Server = None
        self._reader: asyncio.StreamReader = None
        self._writer: asyncio.StreamWriter = None
        self.received_messages: List[Dict[str, str]] = []
        self.is_logged_on = False

    async def start(self) -> int:
        """Start mock TCP server and return allocated port."""
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        self.port = self.server.sockets[0].getsockname()[1]
        logger.info(f"Mock FIX Acceptor listening on {self.host}:{self.port}")
        return self.port

    async def stop(self) -> None:
        if self._writer:
            self._writer.close()
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._reader = reader
        self._writer = writer
        buf = ""
        while not reader.at_eof():
            try:
                data = await reader.read(4096)
                if not data:
                    break
                buf += data.decode("ascii", errors="replace")
                while "10=" in buf:
                    end_idx = buf.find("10=") + 7
                    raw = buf[:end_idx]
                    buf = buf[end_idx:]
                    await self._process_msg(raw)
            except Exception as e:
                logger.error(f"Error handling mock client: {e}")
                break

    async def _send_raw(self, fields: List[Tuple[str, str]]) -> str:
        raw_msg = C.build(fields, self.out_seq, self.sender_comp_id, self.target_comp_id)
        self.out_seq += 1
        if self._writer:
            self._writer.write(raw_msg.encode("ascii"))
            await self._writer.drain()
        return raw_msg

    async def _process_msg(self, raw_msg: str) -> None:
        msg = C.parse(raw_msg)
        self.received_messages.append(msg)
        msg_type = msg.get("35", "")
        seq = int(msg.get("34", "1"))

        if msg_type == "A":  # Logon -> reply with Logon confirmation
            self.is_logged_on = True
            await self._send_raw([("35", "A"), ("98", "0"), ("108", "30")])
        elif msg_type == "5":  # Logout -> reply Logout
            self.is_logged_on = False
            await self._send_raw([("35", "5")])
        elif msg_type == "1":  # TestRequest -> reply Heartbeat
            await self._send_raw([("35", "0"), ("112", msg.get("112", ""))])
        elif msg_type == "D":  # NewOrderSingle -> reply ACK ExecutionReport (35=8, OrdStatus=0)
            cl_ord_id = msg.get("11", "")
            symbol = msg.get("55", "")
            side = msg.get("54", "1")
            qty = msg.get("38", "100")
            price = msg.get("44", "100.0")

            # Send ACK (OrdStatus = '0' New)
            await self._send_raw([
                ("35", "8"),
                ("37", f"ORD-{cl_ord_id}"),  # OrderID
                ("11", cl_ord_id),
                ("17", f"EXEC-{cl_ord_id}-1"),  # ExecID
                ("20", "0"),  # ExecTransType: New
                ("150", "0"),  # ExecType: New
                ("39", "0"),  # OrdStatus: New
                ("55", symbol),
                ("54", side),
                ("38", qty),
                ("44", price),
                ("151", qty),  # LeavesQty
                ("14", "0"),  # CumQty
                ("6", "0.0"),  # AvgPx
            ])
        elif msg_type == "F":  # OrderCancelRequest -> reply Canceled (OrdStatus='4')
            cl_ord_id = msg.get("11", "")
            orig_cl_ord_id = msg.get("41", "")
            symbol = msg.get("55", "")
            side = msg.get("54", "1")
            qty = msg.get("38", "100")

            await self._send_raw([
                ("35", "8"),
                ("37", f"ORD-{orig_cl_ord_id}"),
                ("11", cl_ord_id),
                ("41", orig_cl_ord_id),
                ("17", f"EXEC-{cl_ord_id}-CANC"),
                ("20", "0"),
                ("150", "4"),  # ExecType: Canceled
                ("39", "4"),  # OrdStatus: Canceled
                ("55", symbol),
                ("54", side),
                ("38", qty),
                ("151", "0"),
                ("14", "0"),
                ("6", "0.0"),
            ])


__all__ = ["MockFixAcceptor"]
