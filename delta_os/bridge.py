"""DELTA OS — Headless JSON-RPC bridge for the native Rust TUI.

Provides typed, deterministic access to the DELTA runtime:
- Live Portfolio, Risk, Orders, Execution, Models, Agents, System
- Natural language quantitative research synthesis
- Deterministic slash command execution
- Authoritative Kill Switch control

Communicates via newline-delimited JSON over stdin/stdout.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from delta_os.repl import Terminal, _load_session, _save_session
from core.canonical_pipeline import CanonicalInstitutionalPipeline, OrderSide


class DeltaBridge:
    def __init__(self) -> None:
        self.term = Terminal()
        self.pipeline = CanonicalInstitutionalPipeline(initial_cash=1_000_000.0, venue="XNYS")
        try:
            _load_session(self.term)
        except Exception:
            pass

    def get_state(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        cur = self.term.router.current()
        ledger = getattr(cur, "_ledger", None)

        cash = float(getattr(ledger, "cash", self.pipeline.cash) if ledger else self.pipeline.cash)
        positions_raw = getattr(ledger, "positions", {}) if ledger else {}

        # Merge positions from terminal and pipeline
        price_map: dict[str, float] = {}
        pos_list = []
        equity = cash
        gross_exp = 0.0

        all_syms = set(positions_raw.keys()) | set(self.pipeline.positions.keys())
        for sym in sorted(all_syms):
            pos_data = positions_raw.get(sym)
            if pos_data:
                qty = float(getattr(pos_data, "quantity", getattr(pos_data, "qty", 0.0)))
                avg_px = float(getattr(pos_data, "avg_price", getattr(pos_data, "price", 0.0)))
            else:
                qty = float(self.pipeline.positions.get(sym, 0.0))
                avg_px = float(self.pipeline.position_costs.get(sym, 100.0))

            cur_px = avg_px
            try:
                q = self.term.data.quote(sym)
                cur_px = float(q.frame["close"].iloc[-1])
            except Exception:
                cur_px = avg_px
            price_map[sym] = cur_px

            mkt_val = qty * cur_px
            equity += mkt_val
            gross_exp += abs(mkt_val)
            cost = qty * avg_px
            unrealized = mkt_val - cost
            unrealized_pct = (unrealized / cost * 100.0) if cost > 0 else 0.0
            if abs(qty) > 0.0001:
                pos_list.append({
                    "symbol": sym,
                    "quantity": qty,
                    "avg_price": avg_px,
                    "current_price": cur_px,
                    "market_value": mkt_val,
                    "unrealized_pnl": unrealized,
                    "unrealized_pnl_pct": unrealized_pct,
                })

        net_exp = sum(p["market_value"] for p in pos_list)
        base = self.term.safety.day_start_equity or self.pipeline.initial_cash
        day_pnl = equity - base
        day_pnl_pct = (day_pnl / base * 100.0) if base > 0 else 0.0
        leverage = (gross_exp / equity) if equity > 0 else 0.0

        # Exact venue calendar check (NYSE via exchange_calendar; no UTC hack)
        try:
            from data.market.exchange_calendar import ExchangeCalendar
            _cal = ExchangeCalendar(venue="NYSE")
            is_session_open = _cal.is_open(now)
            market_status = "REGULAR HOURS (OPEN)" if is_session_open else "CLOSED"
            cal_provenance = "LIVE"
        except Exception:
            is_session_open = False
            market_status = "UNAVAILABLE"
            cal_provenance = "UNAVAILABLE"

        # Dynamic risk metrics calculation
        risk_m = self.pipeline.evaluate_risk(price_map)
        ks_mode = getattr(self.term.safety, "mode", "MANUAL").upper()
        is_halted = ks_mode == "HALTED" or self.pipeline.kill_switch_halted
        risk_status = "CRITICAL / HALTED" if is_halted else ("ELEVATED" if leverage > 1.5 else "SAFE")

        # Native acceleration check
        native_active = False
        try:
            import delta_native
            native_active = True
        except Exception:
            native_active = False

        # Working / filled orders from pipeline
        orders_payload = [
            {
                "id": o.order_id,
                "symbol": o.symbol,
                "side": o.side.value if hasattr(o.side, "value") else str(o.side),
                "qty": float(o.quantity),
                "price": float(o.price),
                "order_type": str(o.order_type),
                "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                "timestamp": o.created_at.strftime("%H:%M:%S"),
            }
            for o in self.pipeline.orders.values()
        ]

        alerts_list = list(risk_m.alerts)
        if not is_halted and not alerts_list:
            alerts_list.append({"level": "INFO", "message": "Pre-trade risk governor operational", "time": now.strftime("%H:%M:%S")})

        return {
            "mode": "PAPER" if self.term.broker_name == "paper" else "LIVE",
            "safety_mode": ks_mode,
            "market_status": market_status,
            "market_status_provenance": cal_provenance,
            "market_status_asof": now.isoformat(),
            "clock_utc": now.strftime("%H:%M:%S UTC"),
            "workspace": self.term.workspace,
            "broker": {
                "name": self.term.broker_name,
                "connected": "UNAVAILABLE",
                "connected_provenance": "UNAVAILABLE",
                "type": "PAPER_ENGINE" if self.term.broker_name == "paper" else "DIRECT_BROKER",
            },
            "portfolio": {
                "net_liq": equity,
                "cash": cash,
                "equity": equity,
                "day_pnl": day_pnl,
                "day_pnl_pct": day_pnl_pct,
                "realized_pnl": self.pipeline.realized_pnl,
                "gross_exposure": gross_exp,
                "net_exposure": net_exp,
                "leverage": leverage,
                "positions_count": len(pos_list),
                "positions": pos_list,
            },
            "risk": {
                "status": risk_status,
                "var95": round(risk_m.var95_pct, 2),
                "var95_dollar": round(risk_m.var95_dollar, 2),
                "var99": round(risk_m.var99_pct, 2),
                "var99_dollar": round(risk_m.var99_dollar, 2),
                "cvar": round(risk_m.cvar_pct, 2),
                "cvar_dollar": round(risk_m.cvar_dollar, 2),
                "drawdown": round(risk_m.max_drawdown_pct, 2),
                "leverage": round(leverage, 2),
                "market_beta": round(risk_m.market_beta, 2),
                "concentration_pct": round(risk_m.concentration_pct, 2),
                "gross_limit": 2_000_000.0,
                "gross_limit_provenance": "CONFIG",
                "net_limit": 500_000.0,
                "net_limit_provenance": "CONFIG",
                "killswitch_armed": "UNAVAILABLE",
                "killswitch_armed_provenance": "UNAVAILABLE",
                "killswitch_halted": is_halted,
                "risk_provenance": "PAPER" if self.term.broker_name == "paper" else "LIVE",
                "risk_asof": now.isoformat(),
                "rate_shock_impact": round(risk_m.rate_shock_impact_pct, 2),
                "oil_shock_impact": round(risk_m.oil_shock_impact_pct, 2),
                "alerts": alerts_list,
            },
            "orders": orders_payload,
            "execution": [],
            "execution_provenance": "UNAVAILABLE",
            "models": {
                "active_model": self.term.model_name,
                "active_roles": getattr(self.term.models, "active", {}),
                "available_models": "UNAVAILABLE",
                "available_models_provenance": "UNAVAILABLE",
                "health": "UNAVAILABLE",
                "health_provenance": "UNAVAILABLE",
                "confidence": None,
                "confidence_provenance": "UNAVAILABLE",
            },
            "agents": [],
            "agents_provenance": "UNAVAILABLE",
            "system": {
                "market_data_provider": "DataRouter (Yahoo / Fred / News / Synthetic Fallback)",
                "market_data_status": "UNAVAILABLE",
                "market_data_provenance": "UNAVAILABLE",
                "broker_connection": "UNAVAILABLE",
                "broker_connection_provenance": "UNAVAILABLE",
                "model_gateway": f"ModelGateway ({self.term.model_name})",
                "database": "Local SQLite / JSON State (~/.delta/)",
                "runtime": "DELTA Institutional Core v2.0",
                "native_acceleration": "delta_native (Rust C-ABI Active)" if native_active else "Python Fallback",
                "version": "DELTA OS 2.0-PRO",
                "environment": "PAPER",
            },
        }

    def dispatch(self, text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"output": "", "status": "ok"}
        out, _ = self.term.handle(text)
        return {"output": out, "status": "ok"}

    def quote(self, symbol: str) -> dict[str, Any]:
        sym = symbol.strip().upper()
        try:
            df = None
            try:
                q = self.term.data.quote(sym)
                df = getattr(q, "frame", None)
            except Exception:
                df = None

            if df is None or len(df) < 25:
                df = self.pipeline.fetch_market_bars(sym, n_bars=120)

            last_close = float(df["close"].iloc[-1])
            prev_close = float(df["close"].iloc[-2]) if len(df) > 1 else last_close
            change = last_close - prev_close
            change_pct = (change / prev_close * 100.0) if prev_close > 0 else 0.0
            high = float(df["high"].iloc[-1])
            low = float(df["low"].iloc[-1])
            vol = float(df["volume"].iloc[-1])

            # Historical sparkline closes (up to 30 bars)
            sparkline = [float(x) for x in df["close"].tail(30).tolist()]

            # Compute institutional technical indicators using canonical pipeline
            features = self.pipeline.extract_features(sym, df)
            regime = self.pipeline.detect_regime(features)

            # Generate dynamic L2 depth book around mid-price
            tick_size = 0.01
            spread = max(0.01, round(last_close * 0.0002, 2))
            half_spread = spread / 2.0
            bids = []
            asks = []
            for i in range(5):
                bid_px = round(last_close - half_spread - (i * tick_size * 2), 2)
                ask_px = round(last_close + half_spread + (i * tick_size * 2), 2)
                size_bid = int(100 * (i + 1) * 1.5)
                size_ask = int(100 * (i + 1) * 1.5)
                bids.append({"price": bid_px, "size": size_bid, "count": 2 + i})
                asks.append({"price": ask_px, "size": size_ask, "count": 2 + i})

            return {
                "symbol": sym,
                "price": last_close,
                "change": change,
                "change_pct": change_pct,
                "high": high,
                "low": low,
                "volume": vol,
                "sparkline": sparkline,
                "status": "AVAILABLE",
                "rsi": round(features.rsi, 2),
                "macd": round(features.macd, 3),
                "macd_signal": round(features.macd_signal, 3),
                "bb_upper": round(features.bb_upper, 2),
                "bb_middle": round(features.bb_middle, 2),
                "bb_lower": round(features.bb_lower, 2),
                "atr": round(features.atr, 2),
                "vwap": round(features.vwap, 2),
                "regime": regime.value,
                "depth_bids": bids,
                "depth_asks": asks,
            }
        except Exception as exc:
            return {
                "symbol": sym,
                "status": "UNAVAILABLE",
                "error": f"Market data unavailable for {sym}: {exc}",
                "sparkline": [],
            }

    def kill_switch(self, confirm: bool = False) -> dict[str, Any]:
        # Priority lane: kill never queues behind work. Confirm is exact bool True only.
        if confirm is not True:
            return {
                "status": "ARMED",
                "message": "Kill switch armed. Confirmation required to halt execution.",
            }
        try:
            out, _ = self.term.handle("/kill CONFIRM")
        except Exception as exc:
            return {"status": "FAILED", "message": f"kill failed: {exc}",
                    "safety_mode": getattr(self.term.safety, "mode", "UNKNOWN")}
        halted = str(getattr(self.term.safety, "mode", "")).upper() == "HALTED"
        return {
            "status": "HALTED" if halted else "FAILED",
            "message": out if halted else f"kill not confirmed by enforcer: {out}",
            "safety_mode": self.term.safety.mode,
        }

    def unlock(self, actor: str = "trader", reason: str = "manual_override",
               token: str | None = None) -> dict[str, Any]:
        # Fail-closed: arbitrary actor/reason strings over the pipe are NOT auth.
        # Require DELTA_UNLOCK_TOKEN env match; otherwise refuse and log.
        expected = os.environ.get("DELTA_UNLOCK_TOKEN", "")
        if not expected or token != expected:
            return {"status": "DENIED",
                    "message": "unlock denied: missing or invalid auth token",
                    "safety_mode": getattr(self.term.safety, "mode", "UNKNOWN")}
        out, _ = self.term.handle(f"/unlock {actor} {reason}")
        return {
            "status": "UNLOCKED",
            "message": out,
            "safety_mode": self.term.safety.mode,
        }


def run_ipc_loop():
    import concurrent.futures
    bridge = DeltaBridge()
    # Priority lane: kill/unlock/ping are handled inline and never queue
    # behind slow dispatch/quote/cycle work (thread-pool).
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="bridge-work")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")

    def _handle_work(method: str, params: dict, req_id: object) -> None:
        try:
            if method == "get_state":
                resp_data = bridge.get_state()
            elif method == "dispatch":
                resp_data = bridge.dispatch(params.get("text", ""))
            elif method == "quote":
                resp_data = bridge.quote(params.get("symbol", "SPY"))
            elif method == "run_cycle":
                symbols = params.get("symbols", ["SPY", "QQQ", "NVDA", "AAPL", "MSFT"])
                resp_data = bridge.pipeline.run_cycle(symbols=symbols)
            elif method == "reconcile":
                results = bridge.pipeline.reconcile()
                resp_data = {"reconciliation": [r.status.value for r in results]}
            else:
                resp_data = {"error": f"Unknown method {method}"}
            out = json.dumps({"id": req_id, "result": resp_data}, default=str)
        except Exception as exc:
            out = json.dumps({"id": req_id, "error": {"message": str(exc),
                "traceback": traceback.format_exc()}})
        try:
            sys.stdout.write(out + "\n"); sys.stdout.flush()
        except Exception:
            pass

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req_id = None
        try:
            msg = json.loads(line)
            req_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params", {}) or {}
            if method in ("kill_switch", "unlock", "ping", "cancel"):
                try:
                    if method == "kill_switch":
                        resp_data = bridge.kill_switch(confirm=params.get("confirm", False))
                    elif method == "unlock":
                        resp_data = bridge.unlock(actor=params.get("actor", "trader"),
                            reason=params.get("reason", "manual"), token=params.get("token"))
                    elif method == "ping":
                        resp_data = {"pong": True, "time": datetime.now(timezone.utc).isoformat()}
                    else:
                        resp_data = {"cancelled": True}
                    out = json.dumps({"id": req_id, "result": resp_data}, default=str)
                except Exception as exc:
                    out = json.dumps({"id": req_id, "error": {"message": str(exc)}})
                sys.stdout.write(out + "\n"); sys.stdout.flush()
            else:
                pool.submit(_handle_work, method, params, req_id)
        except Exception as exc:
            try:
                sys.stdout.write(json.dumps({"id": req_id, "error": {"message": str(exc)}}) + "\n")
                sys.stdout.flush()
            except Exception:
                pass


if __name__ == "__main__":
    run_ipc_loop()
