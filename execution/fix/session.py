"""FIX session: sequence discipline, heartbeat, gap detection, resend.

Outbound seq increments per message; inbound expects nextSeq (gap -> queue +
ResendRequest 2, duplicates via PossDupFlag 43=Y are verified, not executed
twice — caller checks msg.get('43') == 'Y'). Heartbeat TestReqID echo.
All state machine transitions are explicit; any framing violation raises
FixReject and the session halts (fail-closed) until reset().
"""
from __future__ import annotations

from dataclasses import dataclass, field

from execution.fix import codec as C

SESSION_VERSION = "fix-session-v1"


@dataclass
class FixSession:
    sender: str
    target: str
    out_seq: int = 1
    in_seq: int = 1
    halted: bool = False
    log: list[str] = field(default_factory=list)

    def _guard(self) -> None:
        if self.halted:
            raise C.FixReject("session halted after violation; reset() required.")

    def send(self, fields: list[tuple[str, str]]) -> str:
        self._guard()
        raw = C.build(fields, self.out_seq, self.sender, self.target)
        self.out_seq += 1
        self.log.append(raw)
        return raw

    def send_heartbeat(self, test_req_id: str = "") -> str:
        f = [("35", "0")]
        if test_req_id:
            f.append(("112", test_req_id))
        return self.send(f)

    def send_logon(self, heartbeat_s: int = 30) -> str:
        return self.send([("35", "A"), ("98", "0"), ("108", str(heartbeat_s))])

    def send_logout(self, text: str = "") -> str:
        f = [("35", "5")]
        if text:
            f.append(("58", text))
        return self.send(f)

    def receive(self, raw: str) -> dict[str, str]:
        """Validate framing + sequence. Returns parsed msg.

        Gap (34 > in_seq): returns {'__gap__': ...} AND queues a ResendRequest
        via send() — caller must process queued messages first. Stale/duplicate
        (34 < in_seq without 43=Y) halts the session.
        """
        self._guard()
        try:
            msg = C.parse(raw)
        except C.FixReject:
            self.halted = True
            raise
        try:
            seq = int(msg.get("34", "-1"))
        except ValueError as exc:
            self.halted = True
            raise C.FixReject("invalid MsgSeqNum.") from exc
        if seq < self.in_seq and msg.get("43") != "Y":
            self.halted = True
            raise C.FixReject(f"stale sequence {seq} < {self.in_seq}.")
        if seq > self.in_seq:
            resend = self.send([("35", "2"), ("7", str(self.in_seq)), ("16", str(seq - 1))])
            return {"__gap__": f"expected {self.in_seq}, got {seq}", "__resend__": resend}
        self.in_seq += 1
        if msg.get("35") == "1":  # TestRequest -> echo Heartbeat
            self.send_heartbeat(msg.get("112", ""))
        return msg

    def reset(self, out_seq: int = 1, in_seq: int = 1) -> None:
        self.out_seq, self.in_seq, self.halted = out_seq, in_seq, False


__all__ = ["SESSION_VERSION", "FixSession"]
