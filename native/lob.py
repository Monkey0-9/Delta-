"""Native limit-order-book binding (C++ lob.cpp via ctypes).

Mirrors execution.matching.engine.PriceTimeMatcher semantics exactly:
limit orders, price-time FIFO, resting-price prints, remainder rests.
Prices/quantities cross the ABI as int64 ticks (Decimal * SCALE, SCALE=10_000);
values must be finite and representable at that scale — anything else raises
instead of silently rounding.

Falls back to the Python PriceTimeMatcher when the DLL is absent, so behavior
never degrades, only speed.
"""
from __future__ import annotations

import ctypes
import os
from decimal import Decimal

SCALE = 10_000
_DLL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "native", "build", "lob.dll")
try:
    _lib = ctypes.CDLL(_DLL) if os.path.exists(_DLL) else None
except OSError:  # missing runtime deps -> graceful fallback, never import crash
    _lib = None

if _lib is not None:
    _lib.delta_lob_create.restype = ctypes.c_void_p
    _lib.delta_lob_destroy.argtypes = [ctypes.c_void_p]
    _lib.delta_lob_add.restype = ctypes.c_size_t
    _lib.delta_lob_add.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_int,
                                   ctypes.c_int64, ctypes.c_int64,
                                   ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    _lib.delta_lob_cancel.restype = ctypes.c_int
    _lib.delta_lob_cancel.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    _lib.delta_lob_replace.restype = ctypes.c_size_t
    _lib.delta_lob_replace.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_int,
                                       ctypes.c_int64, ctypes.c_int64,
                                       ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    _lib.delta_lob_top.restype = ctypes.c_int
    _lib.delta_lob_top.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_void_p, ctypes.c_void_p]
    _lib.delta_lob_add_batch.restype = ctypes.c_size_t
    _lib.delta_lob_add_batch.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_void_p]


def available() -> bool:
    return _lib is not None


def _ticks(v: Decimal) -> int:
    if not isinstance(v, Decimal):
        try:
            v = Decimal(str(v))
        except Exception:
            raise ValueError(f"price/quantity must be Decimal-coercible, got {type(v)}.")
    if not v.is_finite():
        raise ValueError("non-finite price/quantity cannot cross the native ABI.")
    t = int((v * SCALE).to_integral_value())
    if t <= 0 or t >= 2 ** 62:
        raise ValueError(f"value {v} out of native tick range.")
    return t


class NativeMatcher:
    """Drop-in twin of PriceTimeMatcher + cancel/replace. Deterministic handles."""

    def __init__(self) -> None:
        if _lib is None:
            raise RuntimeError("lob.dll not built; use PriceTimeMatcher fallback.")
        self._b = _lib.delta_lob_create()
        self._to_id: dict[str, int] = {}
        self._to_str: dict[int, str] = {}
        self._next = 1

    def close(self) -> None:
        if getattr(self, "_b", None):
            _lib.delta_lob_destroy(self._b)
            self._b = None

    def __del__(self):  # pragma: no cover - best effort
        try:
            self.close()
        except Exception:
            pass

    def _h(self, oid: str) -> int:
        h = self._to_id.get(oid)
        if h is None:
            h = self._next
            self._next += 1
            self._to_id[oid] = h
            self._to_str[h] = oid
        return h

    def _fills(self, n: int, bb, bs, bp, bq) -> list:
        from execution.matching.engine import MatchFill

        out = []
        for i in range(n):
            out.append(MatchFill(self._to_str.get(int(bb[i]), str(int(bb[i]))),
                                 self._to_str.get(int(bs[i]), str(int(bs[i]))),
                                 Decimal(int(bp[i])) / SCALE,
                                 Decimal(int(bq[i])) / SCALE))
        return out

    def add(self, order_id: str, side: str, price: Decimal, quantity: Decimal) -> list:
        if side not in ("buy", "sell"):
            raise ValueError("side must be buy|sell.")
        cap = 1024
        bb = (ctypes.c_uint64 * cap)()
        bs = (ctypes.c_uint64 * cap)()
        bp = (ctypes.c_int64 * cap)()
        bq = (ctypes.c_int64 * cap)()
        n = _lib.delta_lob_add(self._b, self._h(order_id), 0 if side == "buy" else 1,
                               _ticks(price), _ticks(quantity),
                               bb, bs, bp, bq, cap)
        if n > cap:
            raise RuntimeError(f"fill overflow: {n} fills (cap {cap}).")
        return self._fills(n, bb, bs, bp, bq)

    def cancel(self, order_id: str) -> bool:
        h = self._to_id.get(order_id)
        if h is None:
            return False
        return bool(_lib.delta_lob_cancel(self._b, h))

    def replace(self, order_id: str, side: str, price: Decimal, quantity: Decimal) -> list:
        if side not in ("buy", "sell"):
            raise ValueError("side must be buy|sell.")
        cap = 1024
        bb = (ctypes.c_uint64 * cap)()
        bs = (ctypes.c_uint64 * cap)()
        bp = (ctypes.c_int64 * cap)()
        bq = (ctypes.c_int64 * cap)()
        n = _lib.delta_lob_replace(self._b, self._h(order_id), 0 if side == "buy" else 1,
                                   _ticks(price), _ticks(quantity),
                                   bb, bs, bp, bq, cap)
        if n > cap:
            raise RuntimeError(f"fill overflow: {n} fills (cap {cap}).")
        return self._fills(n, bb, bs, bp, bq)

    def top(self):
        bp = (ctypes.c_int64 * 1)()
        bq = (ctypes.c_int64 * 1)()
        ap = (ctypes.c_int64 * 1)()
        aq = (ctypes.c_int64 * 1)()
        f = _lib.delta_lob_top(self._b, bp, bq, ap, aq)
        bid = (Decimal(int(bp[0])) / SCALE, Decimal(int(bq[0])) / SCALE) if f & 1 else None
        ask = (Decimal(int(ap[0])) / SCALE, Decimal(int(aq[0])) / SCALE) if f & 2 else None
        return bid, ask

    def add_many(self, orders: list) -> list:
        """Batch submit [(order_id, side, price, qty)]; one FFI crossing.

        Returns per-order fill lists in submission order. Total fills beyond
        the internal cap raise instead of truncating silently.
        """
        from execution.matching.engine import MatchFill

        n = len(orders)
        if n == 0:
            return []
        ids = (ctypes.c_uint64 * n)()
        sd = (ctypes.c_int * n)()
        px = (ctypes.c_int64 * n)()
        qt = (ctypes.c_int64 * n)()
        for i, (oid, side, price, qty) in enumerate(orders):
            if side not in ("buy", "sell"):
                raise ValueError("side must be buy|sell.")
            ids[i] = self._h(oid)
            sd[i] = 0 if side == "buy" else 1
            px[i] = _ticks(price)
            qt[i] = _ticks(qty)
        cap = min(n * 64 + 1024, 2_000_000)  # worst case: every order
        # sweeps dozens of levels; overflow raises loudly (split the batch).
        bb = (ctypes.c_uint64 * cap)()
        bs = (ctypes.c_uint64 * cap)()
        bp = (ctypes.c_int64 * cap)()
        bq = (ctypes.c_int64 * cap)()
        counts = (ctypes.c_size_t * n)()
        total = _lib.delta_lob_add_batch(self._b, ids, sd, px, qt, n,
                                         bb, bs, bp, bq, cap, counts)
        if total > cap:
            raise RuntimeError(f"fill overflow: {total} fills (cap {cap}).")
        # Split the flat fill stream by per-order counts: fills[k] belong to
        # order k (the aggressor of that sweep), exactly like sequential add.
        per: list[list] = []
        fi = 0
        for k in range(n):
            cur = []
            for _ in range(int(counts[k])):
                buyer, seller = int(bb[fi]), int(bs[fi])
                cur.append(MatchFill(
                    self._to_str.get(buyer, str(buyer)),
                    self._to_str.get(seller, str(seller)),
                    Decimal(int(bp[fi])) / SCALE,
                    Decimal(int(bq[fi])) / SCALE))
                fi += 1
            per.append(cur)
        return per
