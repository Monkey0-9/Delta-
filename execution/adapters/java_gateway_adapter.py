"""Hardened Java Execution Gateway Adapter for DELTA OS.

Supervises the pure-JDK25 Disruptor gateway (CONTRACT v1.0.0 FROZEN) as a
PAPER/SIM-only execution worker. Fail-closed: VERSION handshake, flap/HALT,
PENDING_RECONCILE on disconnect, audit hash-chain subordination, and a hard
ERR_LIVE_PROHIBITED block. Live routing stays refused until Group29 R-gates
+ Sprint-10 sign-off.
"""
from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional

CONTRACT_MAJOR = "1"
CONTRACT_VERSION = "1.0.0"
SOCKET_TIMEOUT = 1.0
JVM_FLAGS = ["-Xms64m", "-Xmx256m", "-XX:+UseParallelGC"]
MAX_RESTARTS = 3
FLAP_WINDOW_S = 5.0
PIDFILE = Path.home() / ".delta" / "run" / "java_gateway.pid"

HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
HALTED = "HALTED"
JAVA_UNAVAILABLE = "JAVA_UNAVAILABLE"

PENDING_RECONCILE = "PENDING_RECONCILE"


class JavaGatewayError(Exception):
    """Base failure for the Java execution lane."""


class VersionMismatch(JavaGatewayError):
    pass


class LiveProhibited(JavaGatewayError):
    """Raised when a LIVE-routed order hits the PAPER/SIM-only lane."""


class BufferOverflow(JavaGatewayError):
    pass


class ProtocolError(JavaGatewayError):
    pass


class LaneHalted(JavaGatewayError):
    pass


def _audit(entry_type: str, data: dict[str, Any]) -> str:
    """Subordinate audit emit: canonical ledger when importable, else local hash."""
    try:
        from core.audit import AuditLedger  # type: ignore

        return AuditLedger().add_entry(entry_type, data)
    except Exception:
        payload = json.dumps({"t": entry_type, "d": data}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()


class JavaGatewayAdapter:
    """Subprocess supervisor + wire client for DeltaJavaGatewayServer."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8999,
        auto_spawn: bool = True,
        mode: str = "PAPER",
        jvm_flags: Optional[list[str]] = None,
    ):
        self.host = host
        self.port = port
        self.auto_spawn = auto_spawn
        self.mode = mode.upper()
        self.jvm_flags = list(jvm_flags) if jvm_flags else list(JVM_FLAGS)
        self._proc: Optional[subprocess.Popen] = None
        self.lane = JAVA_UNAVAILABLE
        self._boot_times: list[float] = []
        self.pending_reconcile: dict[str, dict[str, Any]] = {}
        self.last_cursor: int = 0
        self._conn: Optional[socket.socket] = None
        self._rfile = None
        self._lock = threading.Lock()

    # -- lifecycle -----------------------------------------------------
    def start(self) -> None:
        if self.lane == HALTED:
            raise LaneHalted("java lane HALTED after flap; manual reset required")
        if self._is_running():
            self._handshake()
            return
        if not self.auto_spawn:
            self.lane = JAVA_UNAVAILABLE
            raise JavaGatewayError("java gateway not running and auto_spawn=False")
        self._record_boot()
        bin_dir = Path(__file__).resolve().parent.parent / "java_gateway" / "bin"
        cmd = ["java", *self.jvm_flags, "-cp", str(bin_dir),
               "delta.execution.DeltaJavaGatewayServer", str(self.port)]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            PIDFILE.parent.mkdir(parents=True, exist_ok=True)
            PIDFILE.write_text(str(self._proc.pid))
        except Exception:
            pass
        deadline = time.time() + 20.0
        while time.time() < deadline:
            if self._is_running():
                self._handshake()
                return
            time.sleep(0.1)
        self._mark_degraded("spawn-timeout")
        raise JavaGatewayError("java gateway failed to answer PING after spawn")

    def _record_boot(self) -> None:
        now = time.time()
        self._boot_times.append(now)
        self._boot_times = [t for t in self._boot_times if now - t < FLAP_WINDOW_S + 1]
        recent = [t for t in self._boot_times if now - t < FLAP_WINDOW_S]
        if len(recent) >= MAX_RESTARTS:
            self.lane = HALTED
            _audit("java_lane_halted", {"reason": "flap", "boots": len(recent)})
            raise LaneHalted("flap detected: 3 boots within 5s — lane HALTED")

    def _is_running(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=0.2) as s:
                s.settimeout(1.0)
                s.sendall(b"PING\n")
                resp = s.recv(1024).decode().strip()
                return resp == "PONG"
        except Exception:
            return False

    def _conn_pair(self):
        """Single persistent connection + reader (µs hot path, no re-connect)."""
        if self._conn is None:
            s = socket.create_connection((self.host, self.port), timeout=SOCKET_TIMEOUT)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.settimeout(SOCKET_TIMEOUT)
            self._conn = s
            self._rfile = s.makefile("r", encoding="utf-8", newline="\n")
        return self._conn, self._rfile

    def _drop_conn(self) -> None:
        try:
            if self._rfile is not None:
                self._rfile.close()
        except Exception:
            pass
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass
        self._conn, self._rfile = None, None

    def _rpc(self, cmd: str) -> str:
        """Line-framed request/response over the persistent socket.

        Reads the first line, then — for MATCH_OK headers — exactly that many
        report lines. Reconnects once on failure; else fail-closed.
        """
        with self._lock:
            for attempt in (0, 1):
                try:
                    s, f = self._conn_pair()
                    assert f is not None
                    s.sendall(cmd.encode("utf-8"))
                    first = f.readline()
                    if not first:
                        raise JavaGatewayError("java lane closed connection")
                    lines = [first]
                    if first.startswith("MATCH_OK"):
                        try:
                            count = int(first.split()[1]) if len(first.split()) > 1 else 0
                        except ValueError:
                            count = 0
                        for _ in range(count):
                            ln = f.readline()
                            if not ln:
                                break
                            lines.append(ln)
                    return "".join(lines)
                except JavaGatewayError:
                    self._drop_conn()
                    if attempt == 1:
                        self._mark_degraded("read-failure")
                        raise
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    self._drop_conn()
                    if attempt == 1:
                        self._mark_degraded(f"disconnect: {type(e).__name__}")
                        raise JavaGatewayError(f"java lane disconnect: {e}") from e
            raise JavaGatewayError("java lane reconnect exhausted")

    def _ensure(self) -> None:
        """Fast-path readiness: HALT check + reuse live conn, else full start."""
        if self.lane == HALTED:
            raise LaneHalted("lane HALTED; resolve flap before submitting")
        if self._conn is not None and self.lane == HEALTHY:
            return
        self.start()

    def _handshake(self) -> None:
        try:
            resp = self._rpc("VERSION\n").strip().splitlines()
            line = resp[0] if resp else ""
            if not line.startswith("VERSION_OK"):
                raise VersionMismatch(f"bad handshake: {line!r}")
            ver = line.split()[1] if len(line.split()) > 1 else ""
            if not ver.startswith(CONTRACT_MAJOR + "."):
                raise VersionMismatch(f"contract major mismatch: {ver!r}")
            self.lane = HEALTHY
        except (VersionMismatch, JavaGatewayError):
            raise
        except Exception as e:
            raise ProtocolError(f"handshake failed: {e}") from e

    def _mark_degraded(self, reason: str) -> None:
        if self.lane != HALTED:
            self.lane = DEGRADED
        for oid in list(self.pending_reconcile):
            self.pending_reconcile[oid]["status"] = PENDING_RECONCILE
        _audit("java_lane_degraded", {"reason": reason, "lane": self.lane})

    def _check_err(self, text: str) -> None:
        first = text.strip().splitlines()[0] if text.strip() else ""
        if first.startswith("ERR"):
            if "ERR_VERSION_MISMATCH" in first:
                raise VersionMismatch(first)
            if "ERR_LIVE_PROHIBITED" in first:
                raise LiveProhibited(first)
            if "ERR_BUFFER_OVERFLOW" in first:
                raise BufferOverflow(first)
            raise ProtocolError(first)

    # -- order path ----------------------------------------------------
    def match_order(
        self,
        cl_ord_id: str,
        symbol: str,
        side: str,
        order_type: str,
        price_dollars: float,
        quantity: int,
        mode: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        eff_mode = (mode or self.mode).upper()
        if eff_mode == "LIVE":
            _audit("java_live_blocked", {"cl_ord_id": cl_ord_id, "symbol": symbol})
            raise LiveProhibited("ERR_LIVE_PROHIBITED: java lane is PAPER/SIM-only")
        if self.lane == HALTED:
            raise LaneHalted("lane HALTED; resolve flap before submitting")
        self._ensure()
        price_ticks = int(round(price_dollars * 100))
        cmd = f"MATCH {cl_ord_id} {symbol.upper()} {side.upper()} {order_type.upper()} {price_ticks} {quantity}\n"
        self.pending_reconcile[cl_ord_id] = {
            "symbol": symbol.upper(), "qty": quantity, "status": "IN_FLIGHT",
        }
        raw = self._rpc(cmd)
        self._check_err(raw)
        lines = [ln for ln in raw.strip().splitlines() if ln.strip()]
        if not lines or not lines[0].startswith("MATCH_OK"):
            self.pending_reconcile[cl_ord_id]["status"] = PENDING_RECONCILE
            raise ProtocolError(f"bad MATCH header: {lines[0] if lines else ''!r}")
        count = int(lines[0].split()[1]) if len(lines[0].split()) > 1 else 0
        reports: list[dict[str, Any]] = []
        for line in lines[1:1 + count]:
            parts = line.split(",", 7)
            if len(parts) >= 8:
                reports.append({
                    "cl_ord_id": parts[0], "symbol": parts[1], "side": parts[2],
                    "fill_qty": int(parts[3]), "cum_qty": int(parts[4]),
                    "price": float(parts[5]) / 100.0, "exec_type": int(parts[6]),
                    "fix_report": parts[7],
                })
        _audit("java_match", {"cl_ord_id": cl_ord_id, "symbol": symbol.upper(),
                              "qty": quantity, "reports": len(reports), "mode": eff_mode})
        if reports:
            self.pending_reconcile.pop(cl_ord_id, None)
        return reports

    def cancel_order(self, symbol: str, cl_ord_id: str) -> bool:
        self._ensure()
        raw = self._rpc(f"CANCEL {symbol.upper()} {cl_ord_id}\n")
        if raw.strip().startswith("ERR"):
            self._check_err(raw)
        ok = raw.strip().splitlines()[0] == "CANCEL_OK" if raw.strip() else False
        _audit("java_cancel", {"cl_ord_id": cl_ord_id, "ok": ok})
        return ok

    def status(self) -> dict[str, Any]:
        self._ensure()
        raw = self._rpc("STATUS\n")
        self._check_err(raw)
        parts = raw.strip().split()
        if len(parts) >= 5 and parts[0] == "STATUS_OK":
            return {"ring_depth": int(parts[1]), "cursor": int(parts[2]),
                    "uptime_ms": int(parts[3]), "active_symbols": int(parts[4]),
                    "lane": self.lane}
        raise ProtocolError(f"bad STATUS: {raw!r}")

    # -- OMS reconcile (no-fork invariant) ------------------------------
    def reconcile_with_oms(self, oms, engine) -> tuple:
        """Feed Java fills into the canonical OMS + three-way engine.

        Returns engine results; unmatched fills stay PENDING_RECONCILE.
        """
        from execution.reconciliation.engine import ExternalFill, InternalOrder

        orders, fills = {}, {}
        for oid, o in getattr(oms, "orders", {}).items():
            orders[oid] = InternalOrder(order_id=oid, asset=getattr(o, "asset", ""),
                                       quantity=float(getattr(o, "quantity", 0)))
        for oid, p in self.pending_reconcile.items():
            if p.get("fill_qty"):
                fills[oid] = ExternalFill(order_id=oid, asset=p.get("symbol", ""),
                                         quantity=float(p["fill_qty"]),
                                         price=float(p.get("price", 0.0)))
        return engine.reconcile(orders, fills)

    def reset_lane(self) -> None:
        """Manual operator reset after HALT triage."""
        self._boot_times.clear()
        self.lane = JAVA_UNAVAILABLE
        _audit("java_lane_reset", {})

    def stop(self) -> None:
        self._drop_conn()
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        else:
            # Adopted lane (server predates this object): stop via pidfile.
            try:
                if PIDFILE.exists():
                    pid = int(PIDFILE.read_text().strip())
                    import os
                    import signal

                    os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        try:
            if PIDFILE.exists():
                PIDFILE.unlink()
        except Exception:
            pass
        if self.lane != HALTED:
            self.lane = JAVA_UNAVAILABLE


__all__ = ["JavaGatewayAdapter", "JavaGatewayError", "VersionMismatch",
           "LiveProhibited", "BufferOverflow", "ProtocolError", "LaneHalted",
           "HEALTHY", "DEGRADED", "HALTED", "JAVA_UNAVAILABLE", "PENDING_RECONCILE"]
