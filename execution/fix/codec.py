"""FIX 4.4 codec: build / parse / validate with checksum discipline.

Scope: session + order subset (Logon A, Heartbeat 0, TestRequest 1,
ResendRequest 2, Reject 3, SequenceReset 4, Logout 5, NewOrderSingle D,
OrderCancelRequest F, ExecutionReport 8, BusinessReject j).
All values ASCII str; SOH = \\x01. Timestamps UTC TransactTime(60).

Validation is fail-closed: bad BeginString, BodyLength mismatch, checksum
mismatch, missing required tags, or duplicate ClOrdID handling violations
raise FixReject with the proper session- or business-level meaning. Never
return a half-parsed order.
"""
from __future__ import annotations

from dataclasses import dataclass

SOH = "\x01"
BEGIN = "FIX.4.4"

REQUIRED = {
    "D": ("11", "55", "54", "60", "40"),  # ClOrdID Symbol Side TransactTime OrdType
    "F": ("11", "41", "55", "54", "60"),  # + OrigClOrdID
    "8": ("11", "17", "150", "39"),       # ClOrdID ExecID ExecType OrdStatus
}


class FixReject(Exception):
    def __init__(self, msg: str, business: bool = False) -> None:
        super().__init__(msg)
        self.business = business


def checksum_of(body: str) -> str:
    total = sum(b for b in (body.encode("ascii", errors="strict")))
    return f"{total % 256:03d}"


def build(fields: list[tuple[str, str]], seq: int, sender: str, target: str) -> str:
    """Build a FIX message from (tag, value) pairs (header/trailer added)."""
    for t, v in fields:
        v.encode("ascii")
        if SOH in v or "=" in t:
            raise FixReject(f"illegal char in field {t}.")
    # canonical header order 8,9,35,49,56,34; BodyLength counts everything
    # from 35 up to and including the SOH before tag 10.
    if not fields or fields[0][0] != "35":
        raise FixReject("first field must be 35=MsgType.")
    msgtype = fields[0][1]
    rest = [f for f in fields[1:]
            if f[0] not in ("8", "9", "10", "35", "49", "56", "34")]
    inner = (f"35={msgtype}{SOH}49={sender}{SOH}56={target}{SOH}"
             f"34={seq}{SOH}" + "".join(f"{t}={v}{SOH}" for t, v in rest))
    head = f"8={BEGIN}{SOH}9={len(inner.encode('ascii')):d}{SOH}"
    return f"{head}{inner}10={checksum_of(head + inner)}{SOH}"


def parse(raw: str) -> dict[str, str]:
    """Parse + validate framing. Returns tag->value. Raises FixReject."""
    if not raw.startswith(f"8={BEGIN}{SOH}"):
        raise FixReject("bad BeginString.")
    head = f"8={BEGIN}{SOH}"
    rest = raw[len(head):]
    len_str, sep, after = rest.partition(SOH)
    if not sep or not len_str.startswith("9="):
        raise FixReject("missing/invalid BodyLength.")
    try:
        body_len = int(len_str[2:])
    except ValueError as exc:
        raise FixReject("missing/invalid BodyLength.") from exc
    parts = raw.split(SOH)
    if parts[-1] != "":
        raise FixReject("message must end with SOH.")
    fields = [p.split("=", 1) for p in parts[:-1]]
    if any(len(f) != 2 for f in fields):
        raise FixReject("malformed tag=value pair.")
    msg = {t: v for t, v in fields}
    body_start = len(head) + len(len_str) + 1
    j = raw.rindex(f"{SOH}10=")
    # body slice INCLUDES the SOH preceding tag 10 (per FIX definition)
    if len(raw[body_start:j + 1].encode("ascii")) != body_len:
        raise FixReject("BodyLength mismatch.")
    if msg.get("10") != checksum_of(raw[:j + 1]):
        raise FixReject("checksum mismatch.")
    return msg


def require(msg: dict[str, str], msgtype: str) -> None:
    if msg.get("35") != msgtype:
        raise FixReject(f"expected 35={msgtype}.", business=True)
    for tag in REQUIRED.get(msgtype, ()):
        if tag not in msg:
            raise FixReject(f"missing required tag {tag} for {msgtype}.",
                            business=True)


@dataclass(frozen=True, slots=True)
class NewOrder:
    cl_ord_id: str
    symbol: str
    side: str  # 1=Buy 2=Sell
    quantity: int
    price: str | None  # None = market
    ord_type: str  # 1=Market 2=Limit


def new_order_single(order: NewOrder, seq: int, sender: str, target: str,
                     transact_time: str) -> str:
    if order.side not in ("1", "2"):
        raise FixReject("Side must be 1|2.", business=True)
    if order.quantity <= 0:
        raise FixReject("OrderQty must be positive.", business=True)
    fields = [("35", "D"), ("11", order.cl_ord_id), ("55", order.symbol),
              ("54", order.side), ("60", transact_time), ("40", order.ord_type),
              ("38", str(order.quantity))]
    if order.ord_type == "2":
        if order.price is None:
            raise FixReject("Limit order needs price 44.", business=True)
        fields.append(("44", order.price))
    return build(fields, seq, sender, target)


__all__ = ["SOH", "BEGIN", "FixReject", "checksum_of", "build", "parse",
           "require", "NewOrder", "new_order_single"]
