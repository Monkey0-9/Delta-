"""Production FIX 4.2 / 4.4 Initiator Engine.

Implements full institutional FIX protocol lifecycle:
- Async TCP / TLS socket connection management
- Logon (MsgType A), Heartbeat (0), TestRequest (1), Logout (5)
- NewOrderSingle (D), ExecutionReport (8), OrderCancelReplaceRequest (G), OrderCancelRequest (F), OrderCancelReject (9)
- ResendRequest (2), SequenceReset (4) gap-fill recovery state machine
- Durable SQLite sequence persistence across reconnects
"""
from __future__ import annotations

import asyncio
import logging
import ssl
import time
from typing import Callable, Dict, List, Optional, Tuple

from execution.fix import codec as C
from execution.fix.store import FixSequenceStore

logger = logging.getLogger("DELTA.FIX.Initiator")


class FixInitiator:
    """Institutional FIX 4.2/4.4 Initiator Protocol Engine."""

    def __init__(
        self,
        host: str,
        port: int,
        sender_comp_id: str,
        target_comp_id: str,
        heartbeat_interval: int = 30,
        use_tls: bool = False,
        store_path: str = ":memory:",
        on_execution_report: Optional[Callable[[Dict[str, str]], None]] = None,
        on_cancel_reject: Optional[Callable[[Dict[str, str]], None]] = None,
    ):
        self.host = host
        self.port = port
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.session_id = f"{sender_comp_id}->{target_comp_id}"
        self.heartbeat_interval = heartbeat_interval
        self.use_tls = use_tls

        self.store = FixSequenceStore(store_path)
        self.out_seq, self.in_seq = self.store.init_session(
            self.session_id, sender_comp_id, target_comp_id
        )

        self.on_execution_report = on_execution_report
        self.on_cancel_reject = on_cancel_reject

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._logged_on = False
        self._halted = False

        self._read_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._last_received_time = 0.0

        self.pending_resends: Dict[int, Dict[str, str]] = {}

    @property
    def is_connected(self) -> bool:
        return self._connected and self._logged_on and not self._halted

    async def connect(self) -> None:
        """Establish TCP/TLS socket connection and initiate FIX Logon."""
        if self._connected:
            return

        logger.info(f"Connecting FIX Initiator {self.session_id} to {self.host}:{self.port}...")
        ssl_ctx = ssl.create_default_context() if self.use_tls else None

        self._reader, self._writer = await asyncio.open_connection(
            self.host, self.port, ssl=ssl_ctx
        )
        self._connected = True
        self._last_received_time = time.time()

        # Start background read pump
        self._read_task = asyncio.create_task(self._read_loop())

        # Send Logon (MsgType A)
        await self._send_logon()

        # Wait for logon confirmation
        for _ in range(50):
            if self._logged_on:
                break
            await asyncio.sleep(0.1)

        if not self._logged_on:
            await self.disconnect("Logon confirmation timeout")
            raise ConnectionError("FIX Logon failed to confirm within 5 seconds.")

        # Start background heartbeat timer
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"FIX Initiator {self.session_id} LOGGED ON successfully.")

    async def disconnect(self, reason: str = "Client disconnect") -> None:
        """Send Logout (5) and gracefully close transport."""
        if not self._connected:
            return

        logger.info(f"Disconnecting FIX Initiator {self.session_id}: {reason}")
        if self._logged_on:
            try:
                await self._send_logout(reason)
            except Exception as e:
                logger.warning(f"Error sending FIX Logout: {e}")

        self._logged_on = False
        self._connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._read_task:
            self._read_task.cancel()

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

    async def _send_raw(self, fields: List[Tuple[str, str]]) -> str:
        """Build, log, persist, and transmit FIX message over socket."""
        if self._halted:
            raise RuntimeError("FIX Session is HALTED due to safety violation.")

        raw_msg = C.build(fields, self.out_seq, self.sender_comp_id, self.target_comp_id)
        msg_type = dict(fields).get("35", "0")

        # Log & persist
        self.store.log_message(self.session_id, "OUT", self.out_seq, msg_type, raw_msg)
        self.out_seq += 1
        self.store.update_seq(self.session_id, out_seq=self.out_seq)

        if self._writer:
            self._writer.write(raw_msg.encode("ascii"))
            await self._writer.drain()
        return raw_msg

    async def _send_logon(self) -> str:
        return await self._send_raw([
            ("35", "A"),
            ("98", "0"),  # EncryptMethod: None
            ("108", str(self.heartbeat_interval)),  # HeartBtInt
        ])

    async def _send_logout(self, text: str = "") -> str:
        fields = [("35", "5")]
        if text:
            fields.append(("58", text))
        return await self._send_raw(fields)

    async def _send_heartbeat(self, test_req_id: str = "") -> str:
        fields = [("35", "0")]
        if test_req_id:
            fields.append(("112", test_req_id))
        return await self._send_raw(fields)

    async def _send_test_request(self, test_req_id: str) -> str:
        return await self._send_raw([("35", "1"), ("112", test_req_id)])

    async def send_order_single(
        self,
        cl_ord_id: str,
        symbol: str,
        side: str,  # '1' = Buy, '2' = Sell
        ord_type: str,  # '1' = Market, '2' = Limit
        qty: float,
        price: Optional[float] = None,
        time_in_force: str = "0",  # '0' = Day, '1' = GTC, '3' = IOC, '4' = FOK
    ) -> str:
        """Send NewOrderSingle (35=D)."""
        fields = [
            ("35", "D"),
            ("11", cl_ord_id),
            ("55", symbol),
            ("54", side),
            ("40", ord_type),
            ("38", str(qty)),
            ("59", time_in_force),
            ("60", time.strftime("%Y%m%d-%H:%M:%S.000", time.gmtime())),
        ]
        if price is not None and ord_type == "2":
            fields.append(("44", str(price)))
        return await self._send_raw(fields)

    async def cancel_order(
        self,
        cl_ord_id: str,
        orig_cl_ord_id: str,
        symbol: str,
        side: str,
        qty: float,
    ) -> str:
        """Send OrderCancelRequest (35=F)."""
        fields = [
            ("35", "F"),
            ("11", cl_ord_id),
            ("41", orig_cl_ord_id),
            ("55", symbol),
            ("54", side),
            ("38", str(qty)),
            ("60", time.strftime("%Y%m%d-%H:%M:%S.000", time.gmtime())),
        ]
        return await self._send_raw(fields)

    async def replace_order(
        self,
        cl_ord_id: str,
        orig_cl_ord_id: str,
        symbol: str,
        side: str,
        ord_type: str,
        qty: float,
        price: Optional[float] = None,
    ) -> str:
        """Send OrderCancelReplaceRequest (35=G)."""
        fields = [
            ("35", "G"),
            ("11", cl_ord_id),
            ("41", orig_cl_ord_id),
            ("55", symbol),
            ("54", side),
            ("40", ord_type),
            ("38", str(qty)),
            ("60", time.strftime("%Y%m%d-%H:%M:%S.000", time.gmtime())),
        ]
        if price is not None:
            fields.append(("44", str(price)))
        return await self._send_raw(fields)

    async def _read_loop(self) -> None:
        """Socket framing reader loop."""
        buf = ""
        while self._connected and self._reader:
            try:
                data = await self._reader.read(4096)
                if not data:
                    logger.warning("FIX connection closed by remote peer.")
                    break
                buf += data.decode("ascii", errors="replace")
                while "10=" in buf:
                    end_idx = buf.find("10=") + 7
                    if len(buf) >= end_idx:
                        raw_msg = buf[:end_idx]
                        buf = buf[end_idx:]
                        await self._process_inbound_message(raw_msg)
                    else:
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"FIX read loop exception: {e}")
                break
        self._connected = False
        self._logged_on = False

    async def _process_inbound_message(self, raw_msg: str) -> None:
        self._last_received_time = time.time()
        try:
            msg = C.parse(raw_msg)
        except C.FixReject as exc:
            self._halted = True
            logger.critical(f"FIX framing violation: {exc}")
            return

        seq = int(msg.get("34", "-1"))
        msg_type = msg.get("35", "")
        poss_dup = msg.get("43") == "Y"

        self.store.log_message(self.session_id, "IN", seq, msg_type, raw_msg)

        # Sequence checking & Gap handling
        if seq < self.in_seq and not poss_dup:
            self._halted = True
            logger.critical(f"Stale sequence received: got {seq}, expected {self.in_seq}")
            return

        if seq > self.in_seq:
            logger.warning(f"Sequence gap detected: got {seq}, expected {self.in_seq}. Requesting Resend...")
            await self._send_raw([("35", "2"), ("7", str(self.in_seq)), ("16", str(seq - 1))])
            self.pending_resends[seq] = msg
            return

        # Correct sequence number
        self.in_seq += 1
        self.store.update_seq(self.session_id, in_seq=self.in_seq)

        # Dispatch message type
        if msg_type == "A":  # Logon
            self._logged_on = True
            logger.info("FIX Logon confirmed by remote acceptor.")
        elif msg_type == "5":  # Logout
            logger.info(f"FIX Logout received: {msg.get('58', '')}")
            self._logged_on = False
        elif msg_type == "1":  # TestRequest
            await self._send_heartbeat(msg.get("112", ""))
        elif msg_type == "2":  # ResendRequest
            begin_seq = int(msg.get("7", "1"))
            end_seq = int(msg.get("16", "0"))
            if end_seq == 0:
                end_seq = self.out_seq - 1
            await self._handle_resend_request(begin_seq, end_seq)
        elif msg_type == "4":  # SequenceReset / GapFill
            new_seq = int(msg.get("36", str(self.in_seq)))
            if new_seq > self.in_seq:
                self.in_seq = new_seq
                self.store.update_seq(self.session_id, in_seq=self.in_seq)
        elif msg_type == "8":  # ExecutionReport
            if self.on_execution_report:
                self.on_execution_report(msg)
        elif msg_type == "9":  # OrderCancelReject
            if self.on_cancel_reject:
                self.on_cancel_reject(msg)

    async def _handle_resend_request(self, start_seq: int, end_seq: int) -> None:
        """Fulfill incoming ResendRequest (2)."""
        logger.info(f"Fulfilling ResendRequest for seq {start_seq} to {end_seq}")
        msgs = self.store.get_messages(self.session_id, "OUT", start_seq, end_seq)

        # Group gaps or resend administrative/trade messages
        if not msgs:
            await self._send_raw([
                ("35", "4"),
                ("36", str(end_seq + 1)),
                ("123", "Y"),  # GapFillFlag
            ])
        else:
            for s_num, m_type, raw in msgs:
                if m_type in ("A", "5", "0", "1", "2", "4"):
                    # Admin message -> send SequenceReset / GapFill
                    await self._send_raw([
                        ("35", "4"),
                        ("36", str(s_num + 1)),
                        ("123", "Y"),
                    ])
                else:
                    # Application message -> send with PossDupFlag = Y
                    m_parsed = C.parse(raw)
                    fields = [(k, v) for k, v in m_parsed.items() if k not in ("8", "9", "35", "49", "56", "34", "10")]
                    fields.append(("43", "Y"))
                    await self._send_raw([("35", m_type)] + fields)

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat generator & stale link detector."""
        while self._connected and self._logged_on:
            await asyncio.sleep(self.heartbeat_interval / 2.0)
            now = time.time()
            if now - self._last_received_time > (self.heartbeat_interval * 1.5):
                logger.warning("No FIX data received within heartbeat window. Sending TestRequest...")
                await self._send_test_request(f"TR-{int(now)}")
            else:
                await self._send_heartbeat()


__all__ = ["FixInitiator"]
