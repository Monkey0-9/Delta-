"""DELTA OS — Background Quantitative Service Daemon.

Orchestrates the 24/7 Autonomous Portfolio Sentinel and JSON-RPC Bridge
in a detached background process with atomic PID management and logging.
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


def is_daemon_running() -> Tuple[bool, Optional[int]]:
    pid_file, _ = get_daemon_paths()
    if not pid_file.exists():
        return False, None
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        # Probe process existence via signal 0
        os.kill(pid, 0)
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
    # Brief grace pause to verify process did not immediately crash
    time.sleep(0.3)
    if proc.poll() is not None:
        pid_file.unlink(missing_ok=True)
        return {"status": "FAILED", "code": proc.returncode, "message": "Daemon failed to start. Check logs."}

    return {"status": "STARTED", "pid": proc.pid, "log": str(log_file)}


def stop_daemon() -> Dict[str, Any]:
    running, pid = is_daemon_running()
    pid_file, _ = get_daemon_paths()
    if not running or pid is None:
        if pid_file.exists():
            pid_file.unlink(missing_ok=True)
        return {"status": "NOT_RUNNING", "message": "Daemon is not running."}

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(15):
            time.sleep(0.2)
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

    return {"status": "STOPPED", "pid": pid, "message": f"Stopped daemon (PID: {pid})."}


def get_daemon_status() -> Dict[str, Any]:
    running, pid = is_daemon_running()
    pid_file, log_file = get_daemon_paths()
    return {
        "running": running,
        "pid": pid,
        "pid_file": str(pid_file),
        "log_file": str(log_file),
        "state": "RUNNING" if running else "STOPPED",
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

    # Load persistent service configuration overrides
    cfg = sc.load_config()
    eff_max_dd = float(cfg.get("max_dd_pct", max_dd))
    eff_interval = float(cfg.get("interval_s", interval_s))

    # Initialize terminal to access authoritative paper ledger, broker adapter, and safety
    term = Terminal()
    safety = term.safety
    d_dir = _delta_dir()
    state_path = str(d_dir / "sentinel.json")

    def _read_portfolio_equity() -> float | None:
        try:
            cur = term.router.current()
            ledger = getattr(cur, "_ledger", None)
            if ledger is None:
                return None
            cash = float(getattr(ledger, "cash", 0.0))
            # Calculate market value of held positions
            mkt_val = 0.0
            for sym, pos in getattr(ledger, "positions", {}).items():
                qty = float(getattr(pos, "quantity", getattr(pos, "qty", 0.0)))
                px = float(getattr(pos, "avg_price", getattr(pos, "price", 0.0)))
                try:
                    q = term.data.quote(sym)
                    px = float(q.frame["close"].iloc[-1])
                except Exception:
                    pass
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
    if hasattr(term.router, "paper"):
        broker_adapters.append(term.router.paper)

    sentinel = DeltaSentinel(
        brain=term.brain,
        safety_state=safety,
        max_drawdown_pct=eff_max_dd,
        check_interval_s=eff_interval,
        equity_fn=_read_portfolio_equity,
        positions_fn=_read_portfolio_positions,
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

    print(f"[{datetime.now(timezone.utc).isoformat()}] DELTA 24/7 Sentinel Service active. Interval: {eff_interval}s, MaxDD: {eff_max_dd}%.")

    while keep_running:
        try:
            res = sentinel.tick_once()
            if res.get("halted"):
                print(f"[{datetime.now(timezone.utc).isoformat()}] CRITICAL: Circuit Breaker TRIPPED! Halted: {res}")
        except Exception as exc:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Sentinel tick error: {exc}")
        time.sleep(eff_interval)

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
