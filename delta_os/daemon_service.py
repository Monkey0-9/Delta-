"""DELTA OS — Background Quantitative Service Daemon.

Orchestrates the 24/7 Autonomous Portfolio Sentinel and JSON-RPC Bridge
in a detached background process with atomic PID management, heartbeats,
readiness probes, and logging.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _delta_dir() -> Path:
    base = Path(os.environ.get("DELTA_HOME", str(Path.home() / ".delta")))
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_daemon_paths() -> Tuple[Path, Path]:
    d = _delta_dir()
    return d / "daemon.pid", d / "daemon.log"


def get_heartbeat_path() -> Path:
    return _delta_dir() / "daemon_heartbeat.json"


def is_daemon_running() -> Tuple[bool, Optional[int]]:
    pid_file, _ = get_daemon_paths()
    if not pid_file.exists():
        return False, None
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        # Probe process existence via signal 0
        os.kill(pid, 0)

        # Verify process identity via /proc/{pid}/cmdline to prevent PID reuse on Linux
        cmdline_path = Path(f"/proc/{pid}/cmdline")
        if cmdline_path.exists():
            try:
                cmdline = cmdline_path.read_text(encoding="utf-8", errors="replace")
                if "daemon_service" not in cmdline and "delta_os" not in cmdline:
                    # PID belongs to an unrelated reused process
                    pid_file.unlink(missing_ok=True)
                    return False, None
            except (PermissionError, ProcessLookupError):
                pass
        return True, pid
    except (ValueError, OSError, ProcessLookupError):
        # Stale PID file
        try:
            pid_file.unlink(missing_ok=True)
        except Exception:
            pass
        return False, None


def start_daemon(max_dd: float = 2.0, interval_s: float = 3.0) -> Dict[str, Any]:
    running, pid = is_daemon_running()
    if running:
        return {"status": "ALREADY_RUNNING", "pid": pid, "message": f"Daemon already running (PID: {pid})."}

    pid_file, log_file = get_daemon_paths()
    hb_file = get_heartbeat_path()
    hb_file.unlink(missing_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "delta_os.daemon_service",
        "--worker",
        "--max-dd",
        str(max_dd),
        "--interval",
        str(interval_s),
    ]

    with open(log_file, "a", encoding="utf-8") as out:
        out.write(f"\n--- DELTA SERVICE BOOT {datetime.now(timezone.utc).isoformat()} ---\n")
        out.flush()
        proc = subprocess.Popen(
            cmd,
            stdout=out,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

    pid_file.write_text(str(proc.pid), encoding="utf-8")

    # Wait up to 5 seconds for readiness probe with successful risk monitoring cycle
    start_wait = time.time()
    readiness_achieved = False
    while time.time() - start_wait < 5.0:
        if proc.poll() is not None:
            pid_file.unlink(missing_ok=True)
            return {"status": "FAILED", "code": proc.returncode, "message": "Daemon failed to start. Check logs."}
        if hb_file.exists():
            try:
                hb = json.loads(hb_file.read_text(encoding="utf-8"))
                if hb.get("ready") and hb.get("last_successful_cycle_utc"):
                    readiness_achieved = True
                    break
            except Exception:
                pass
        time.sleep(0.1)

    if not readiness_achieved:
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        pid_file.unlink(missing_ok=True)
        return {"status": "FAILED", "message": "Readiness deadline expired without a successful risk monitoring cycle."}

    return {"status": "STARTED", "pid": proc.pid, "log": str(log_file)}


def stop_daemon() -> Dict[str, Any]:
    running, pid = is_daemon_running()
    pid_file, _ = get_daemon_paths()
    hb_file = get_heartbeat_path()

    if not running or pid is None:
        if pid_file.exists():
            pid_file.unlink(missing_ok=True)
        if hb_file.exists():
            hb_file.unlink(missing_ok=True)
        return {"status": "NOT_RUNNING", "message": "Daemon is not running."}

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.15)
            try:
                os.kill(pid, 0)
            except OSError:
                break
        else:
            # Force kill if SIGTERM didn't terminate in 3s
            os.kill(pid, signal.SIGKILL)
    except OSError:
        pass

    if pid_file.exists():
        pid_file.unlink(missing_ok=True)
    if hb_file.exists():
        hb_file.unlink(missing_ok=True)

    return {"status": "STOPPED", "pid": pid, "message": f"Stopped daemon (PID: {pid})."}


def restart_daemon(max_dd: float = 2.0, interval_s: float = 3.0) -> Dict[str, Any]:
    """Gracefully stop existing daemon, verify termination, and spawn fresh daemon process."""
    stop_daemon()
    for _ in range(30):
        running, _ = is_daemon_running()
        if not running:
            break
        time.sleep(0.1)
    return start_daemon(max_dd=max_dd, interval_s=interval_s)


def get_daemon_status() -> Dict[str, Any]:
    running, pid = is_daemon_running()
    pid_file, log_file = get_daemon_paths()
    hb_file = get_heartbeat_path()

    heartbeat = None
    if hb_file.exists():
        try:
            heartbeat = json.loads(hb_file.read_text(encoding="utf-8"))
        except Exception:
            heartbeat = {"corrupt": True}

    return {
        "running": running,
        "pid": pid,
        "pid_file": str(pid_file),
        "log_file": str(log_file),
        "state": "RUNNING" if running else "STOPPED",
        "heartbeat": heartbeat,
    }


def get_daemon_logs(lines: int = 50) -> str:
    _, log_file = get_daemon_paths()
    if not log_file.exists():
        return "No daemon logs found."
    try:
        content = log_file.read_text(encoding="utf-8", errors="replace")
        split = content.splitlines()
        return "\n".join(split[-lines:])
    except Exception as exc:
        return f"Error reading logs: {exc}"


def _run_worker(max_dd: float, interval_s: float) -> None:
    """Worker process running the 24/7 Sentinel loop with real portfolio wiring."""
    from delta_os.brain import DeltaSentinel
    from delta_os.repl import Terminal
    from delta_os import service_config as sc

    try:
        cfg = sc.load_config()
    except sc.ConfigurationCorruptError as exc:
        print(f"[{datetime.now(timezone.utc).isoformat()}] FATAL: Service configuration corrupt: {exc}")
        sys.exit(1)

    eff_max_dd = float(cfg.get("max_dd_pct", max_dd))
    eff_interval = float(cfg.get("interval_s", interval_s))
    active_revision = int(cfg.get("revision", 1))

    # Initialize terminal to access authoritative paper ledger, broker adapter, and safety
    term = Terminal()
    safety = term.safety
    d_dir = _delta_dir()
    state_path = str(d_dir / "sentinel.json")
    hb_file = get_heartbeat_path()

    def _read_portfolio_equity() -> float | None:
        try:
            cur = term.router.current()
            if hasattr(cur, "get_account_snapshot"):
                snap = cur.get_account_snapshot()
                if snap.equity is not None and not snap.degraded:
                    return float(snap.equity)
                return None
            ledger = getattr(cur, "_ledger", None)
            if ledger is None:
                return None
            cash = float(getattr(ledger, "cash", 0.0))
            # Calculate market value of held positions
            mkt_val = 0.0
            for sym, pos in getattr(ledger, "positions", {}).items():
                qty = float(getattr(pos, "quantity", getattr(pos, "qty", 0.0)))
                # NEVER fallback to avg_price! Missing quote means UNAVAILABLE
                try:
                    q = term.data.quote(sym)
                    px = float(q.frame["close"].iloc[-1])
                except Exception:
                    return None
                mkt_val += qty * px
            return cash + mkt_val
        except Exception:
            return None

    def _read_portfolio_positions() -> Dict[str, float]:
        try:
            cur = term.router.current()
            ledger = getattr(cur, "_ledger", None)
            if ledger is None:
                return {}
            return {
                sym: float(getattr(pos, "quantity", getattr(pos, "qty", 0.0)))
                for sym, pos in getattr(ledger, "positions", {}).items()
            }
        except Exception:
            return {}

    broker_adapters = []
    if hasattr(term.router, "current"):
        broker_adapters.append(term.router.current())
    elif hasattr(term.router, "paper"):
        broker_adapters.append(term.router.paper)

    from delta_os.paging import PagingDispatcher
    pager = PagingDispatcher(ledger_path=_delta_dir() / "alerts.jsonl")

    def _durable_alert_sink(alert: Dict[str, Any]) -> None:
        """Durable alert delivery to daemon log and append-only alert ledger via PagingDispatcher."""
        lvl = alert.get("level", "WARNING")
        msg = alert.get("message", "")
        pager.dispatch(severity=lvl, component="SENTINEL", message=msg, metadata=alert)

    sentinel = DeltaSentinel(
        brain=term.brain,
        safety_state=safety,
        max_drawdown_pct=eff_max_dd,
        check_interval_s=eff_interval,
        equity_fn=_read_portfolio_equity,
        positions_fn=_read_portfolio_positions,
        alert_sink=_durable_alert_sink,
        broker_adapters=broker_adapters,
        state_path=state_path,
    )

    keep_running = True

    def _sig_handler(_sig, _frame):
        nonlocal keep_running
        print(f"[{datetime.now(timezone.utc).isoformat()}] Received shutdown signal; stopping.")
        keep_running = False

    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)

    print(f"[{datetime.now(timezone.utc).isoformat()}] DELTA 24/7 Sentinel Service active. Interval: {eff_interval}s, MaxDD: {eff_max_dd}%, Rev: {active_revision}.")

    last_successful_cycle_utc: Optional[str] = None
    consecutive_errors = 0
    last_error: Optional[str] = None

    def _write_heartbeat(status: str = "INITIALIZING", ticks: int = 0) -> None:
        is_ready = status == "HEALTHY" and last_successful_cycle_utc is not None
        hb_data = {
            "pid": os.getpid(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "applied_revision": active_revision,
            "ticks": ticks,
            "ready": is_ready,
            "last_successful_cycle_utc": last_successful_cycle_utc,
            "consecutive_errors": consecutive_errors,
            "last_error": last_error,
            "max_dd_pct": sentinel.max_drawdown_pct,
            "interval_s": sentinel.check_interval_s,
        }
        tmp_hb = hb_file.with_suffix(f".tmp.{os.getpid()}")
        try:
            tmp_hb.write_text(json.dumps(hb_data), encoding="utf-8")
            tmp_hb.replace(hb_file)
        except Exception:
            pass

    # Initial boot state (INITIALIZING — never claim HEALTHY or ready before cycle completion)
    _write_heartbeat(status="INITIALIZING", ticks=0)

    tick_count = 0
    while keep_running:
        # Check config hot-reload
        try:
            new_cfg = sc.load_config()
            new_rev = int(new_cfg.get("revision", 1))
            if new_rev != active_revision:
                for k in sc.RESTART_REQUIRED_KEYS:
                    if new_cfg.get(k) != cfg.get(k):
                        print(f"[{datetime.now(timezone.utc).isoformat()}] NOTICE: Configuration key '{k}' changed. RESTART_REQUIRED for daemon to apply.")
                sentinel.max_drawdown_pct = float(new_cfg.get("max_dd_pct", sentinel.max_drawdown_pct))
                sentinel.check_interval_s = float(new_cfg.get("interval_s", sentinel.check_interval_s))
                eff_interval = sentinel.check_interval_s
                active_revision = new_rev
                cfg = new_cfg
                print(f"[{datetime.now(timezone.utc).isoformat()}] Applied configuration revision {new_rev} (interval: {eff_interval}s, max_dd: {sentinel.max_drawdown_pct}%).")
        except sc.ConfigurationCorruptError as exc:
            print(f"[{datetime.now(timezone.utc).isoformat()}] WARNING: Invalid configuration file detected ({exc}); retaining active settings.")
        except Exception:
            pass

        tick_count += 1
        cycle_ok = False
        try:
            res = sentinel.tick_once()
            if res.get("halted"):
                print(f"[{datetime.now(timezone.utc).isoformat()}] CRITICAL: Circuit Breaker TRIPPED! Halted: {res}")
                pager.dispatch(severity="CRITICAL", component="CIRCUIT_BREAKER", message=f"Automated circuit breaker tripped: {res}", metadata=res, force=True)
            last_successful_cycle_utc = datetime.now(timezone.utc).isoformat()
            consecutive_errors = 0
            last_error = None
            cycle_ok = True
        except Exception as exc:
            consecutive_errors += 1
            last_error = str(exc)
            print(f"[{datetime.now(timezone.utc).isoformat()}] Sentinel tick error ({consecutive_errors}): {exc}")
            if consecutive_errors == 3:
                pager.dispatch(severity="CRITICAL", component="SENTINEL_DAEMON", message=f"Sentinel monitoring entered FAILED status after {consecutive_errors} consecutive errors: {last_error}", force=True)

        if cycle_ok:
            status = "HEALTHY"
        elif consecutive_errors >= 3:
            status = "FAILED"
        else:
            status = "DEGRADED"

        _write_heartbeat(status=status, ticks=tick_count)
        time.sleep(eff_interval)

    try:
        _write_heartbeat(status="STOPPED", ticks=tick_count)
    except Exception:
        pass
    print(f"[{datetime.now(timezone.utc).isoformat()}] DELTA Service terminated cleanly.")


def main() -> None:
    parser = argparse.ArgumentParser(description="DELTA Background Service Worker")
    parser.add_argument("--worker", action="store_true", help="Run the continuous sentinel worker")
    parser.add_argument("--max-dd", type=float, default=2.0, help="Max drawdown %")
    parser.add_argument("--interval", type=float, default=3.0, help="Surveillance interval in seconds")
    args = parser.parse_args()

    if args.worker:
        _run_worker(max_dd=args.max_dd, interval_s=args.interval)
    else:
        print("Usage: python -m delta_os.daemon_service --worker")


if __name__ == "__main__":
    main()
