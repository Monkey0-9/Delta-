"""DELTA workstation app — ONE interactive frontend.

Textual full-screen when installed; Rich scrolling fallback otherwise.
Backend returns typed viewmodels; this layer only renders them.
Kill path bypasses the LLM and requires typed confirmation.

Image 1 contract:
  header  Δ DELTA | QUANT INTELLIGENCE CLI | ● MARKETS | ● DATA | ● RISK | ◉ MODE | clock
  hero    RESEARCH | SIMULATE | ANALYZE | EXECUTE | LEARN (clickable/shortcut)
  input   Ask DELTA anything ... / for commands ... [Ctrl+K -> palette]
  footer  Model: ... | Agent: ... | Session: ... (all switchable, persisted)
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone

# pyrefly: ignore [missing-import]
from config.mode import DeltaMode, mode_banner
# pyrefly: ignore [missing-import]
from .commands import parser as cmd_parser
from .commands.palette import format_palette_box
from .commands.registry import lookup
from .state import store as store_mod
from .state.selectors import footer_model, header_model, status_model
from .screens.home import HomeScreen
from .screens.core import (MarketScreen, SecurityScreen, BookScreen,
                           ResearchScreen, AlphaScreen, PortfolioScreen, RiskScreen)
from .screens.ops import (ExecutionScreen, OrdersScreen, ScenariosScreen,
                           ModelsScreen, SystemScreen, SessionScreen,
                           AutomationScreen, DataScreen)
from .screens.assurance import ReconScreen, AuditScreen

SCREENS = {
    "home": HomeScreen(), "market": MarketScreen(), "security": SecurityScreen(),
    "book": BookScreen(), "research": ResearchScreen(), "alpha": AlphaScreen(),
    "portfolio": PortfolioScreen(), "risk": RiskScreen(),
    "execution": ExecutionScreen(), "orders": OrdersScreen(),
    "scenarios": ScenariosScreen(), "models": ModelsScreen(),
    "system": SystemScreen(), "session": SessionScreen(),
    "automation": AutomationScreen(), "data": DataScreen(),
    "reconciliation": ReconScreen(), "audit": AuditScreen(),
}

# Single AGENTS source: agent/orchestrator (8 personas). Fallback keeps the
# legacy 3 only if the orchestrator module is unimportable (never silent).
try:
    from agent.orchestrator import AGENTS as AGENTS
except Exception:
    AGENTS = ("quant-researcher", "risk-monitor", "execution-copilot")  # fallback
HERO_TARGETS = {
    "research": "/research",
    "simulate": "/simulate",
    "analyze": "/analyze",
    "execute": "/execution",
    "learn": "/learn",
}


def _safe(text: str) -> str:
    """Console-safe: degrade glyphs that crash cp1252 Windows consoles."""
    if not isinstance(text, str):
        text = str(text)
    try:
        enc = getattr(__import__("sys").stdout, "encoding", "utf-8") or "utf-8"
        text.encode(enc)
        return text
    except Exception:
        return (text.replace("●", "*").replace("○", "o").replace("◉", "[*]")
                .replace("Δ", "D").replace("→", "->").replace("—", "-")
                .replace("–", "-").replace("·", "|").replace("✓", "v")
                .replace("↗", "^").replace("×", "x"))


try:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _mcp_summary() -> str:
    """Best-effort MCP registry census. Liveness stays UNPROBED (honest)."""
    from agent.mcp_registry import McpRegistry
    dash = McpRegistry().dashboard()
    n = sum(len(v) for v in dash.values())
    return f"registry readable ({n} servers, UNPROBED liveness)"


def _gpu_summary() -> str:
    """Best-effort GPU census. Anything unreadable raises to the caller."""
    import torch
    if torch.cuda.is_available():
        return "READY " + torch.cuda.get_device_name(0)
    return "UNAVAILABLE (no CUDA)"


def build_completer_words() -> list[str]:
    """prompt_toolkit completion words from the REAL command registry.

    Slash + NL + alias + terminal surfaces all register into REGISTRY, so
    new commands complete the day they register — never a hardcoded list.
    """
    try:
        from .commands import aliases as _aliases  # noqa: F401 loads aliases
        from .commands import terminal as _terminal  # noqa: F401 loads surface
        from .commands.registry import REGISTRY
        return sorted("/" + n for n in REGISTRY)
    except Exception:
        return ["/help", "/kill", "/quit"]


class DeltaApp:
    """Workstation controller (UI-framework agnostic)."""

    def __init__(self, mode: DeltaMode = DeltaMode.PAPER) -> None:
        self.store = store_mod.reset_store(mode)
        self.pending_kill = False
        self._backend = None
        self._restore_session()
        self.refresh_chrome()

    # -- backend (lazy, never crashes UI) ---------------------------------
    def backend(self):
        if self._backend is None:
            try:
                # pyrefly: ignore [missing-import]
                from delta_os.repl import Terminal as _OsTerminal
                # pyrefly: ignore [missing-import]
                from delta_os.repl import _load_session as _ls

                term = _OsTerminal()
                try:
                    _ls(term)
                except Exception:
                    pass
                self._backend = term
            except Exception:
                self._backend = None
        return self._backend

    def _restore_session(self) -> None:
        try:
            import json
            from pathlib import Path
            import os

            p = Path(os.path.expanduser("~")) / ".delta" / "session.json"
            if not p.exists():
                return
            d = json.loads(p.read_text(encoding="utf-8"))
            # New TUI keys take precedence; legacy backend model_name is NOT
            # adopted as the display model (display default: delta).
            # Legacy display names migrate to delta.
            v = d.get("model")
            if isinstance(v, str) and v:
                if v == "delta-fm-research":
                    v = "delta"
                self.store.set_model(v)
            v = d.get("agent")
            if isinstance(v, str) and v:
                if v in ("quant-researcher", "delta"):
                    v = "research-agent"
                self.store.set_agent(v)
            for _k in ("effort", "thinking"):
                _v = d.get(_k)
                if isinstance(_v, str) and _v:
                    setattr(self.store, _k, _v.upper())
            v = d.get("session") or d.get("session_id")
            if isinstance(v, str) and v:
                self.store.set_session(v)
        except Exception:
            pass

    def _persist_session(self) -> None:
        try:
            import json
            from pathlib import Path
            import os

            p = Path(os.path.expanduser("~")) / ".delta" / "session.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            cur: dict = {}
            try:
                if p.exists():
                    cur = json.loads(p.read_text(encoding="utf-8"))
                    if not isinstance(cur, dict):
                        cur = {}
            except Exception:
                cur = {}
            cur.update({"model": self.store.model, "model_name": self.store.model,
                        "agent": self.store.agent,
                        "effort": getattr(self.store, "effort", "AUTO"),
                        "thinking": getattr(self.store, "thinking", "SUMMARY"),
                        "session": self.store.session_id, "session_id": self.store.session_id,
                        "workspace": self.store.workspace})
            p.write_text(json.dumps(cur, indent=2), encoding="utf-8")
        except Exception:
            pass

    def refresh_chrome(self) -> None:
        """Update market/data/risk chips from live sources. Best-effort only."""
        s = self.store
        # Venue calendar authority (no UTC hack): NYSE via exchange_calendar.
        try:
            from data.market.exchange_calendar import ExchangeCalendar
            now = datetime.now(timezone.utc)
            s.market_live = ExchangeCalendar(venue="NYSE").is_open(now)
        except Exception:
            s.market_live = False
        be = self.backend()
        if be is not None:
            try:
                self.store.broker = getattr(be, "broker_name", s.broker) or s.broker
                # NOTE: backend engine name (qwen-3.6/groq-free/...) is distinct
                # from the TUI display model (delta). Never overwrite
                # the display selector from the engine; /model switch syncs both.
                safety = getattr(be, "safety", None)
                smode = str(getattr(safety, "mode", "") or "").upper()
                if smode == "HALTED":
                    s.risk_state = "BLOCKED"
                elif s.risk_state == "BLOCKED" and smode != "HALTED":
                    s.risk_state = "REVIEW"
            except Exception:
                pass
        s.touch()

    # -- command dispatch (slash + NL converge) -------------------------
    def dispatch(self, text: str) -> str:
        t = (text or "").strip()
        if not t:
            return ""
        # Fresh command, fresh backend echo: never bleed a previous command's
        # backend output into an unrelated screen (stale-content shame).
        self._last_live = ""
        self.refresh_chrome()
        parsed = cmd_parser.parse(t)
        action = parsed.get("action")
        args = parsed.get("args", [])
        parts = t[1:].split() if t.startswith("/") else []
        raw_cmd = parts[0].lower() if parts else ""

        # kill always first, bypasses LLM
        if (action is not None and action.name in ("kill", "kill-switch")) or raw_cmd in ("kill", "kill-switch", "killswitch"):
            return self._kill_step(t)

        # palette
        if raw_cmd in ("palette", "commands", "help", "?") or t.strip() == "/":
            return self._palette_text("")

        # selectors
        if raw_cmd == "model":
            return self._cmd_model(args)
        if raw_cmd == "agent":
            return self._cmd_agent(args)
        if raw_cmd in ("session", "workspace"):
            return self._cmd_session(args)
        if raw_cmd == "open":
            return self._cmd_open(args)
        if raw_cmd in ("mcp", "config", "auth"):
            return self._passthrough(t)
        # model-adjacent verbs: deterministic backend passthrough (never screen-only)
        if raw_cmd in ("effort", "thinking", "key"):
            return self._passthrough(t)
        # brain/automation verbs: deterministic backend passthrough
        if raw_cmd in ("brain", "sentinel", "alerts", "protect", "dipbuy",
                       "crash", "models"):
            return self._passthrough(t)
        if raw_cmd in ("exit", "quit"):
            return "bye"

        # A4: doctor/status/data run REAL probes — never screen-only renders.
        if raw_cmd == "doctor":
            return self._cmd_doctor(args)
        if raw_cmd == "status":
            return self._cmd_status(args)
        if raw_cmd == "data":
            return self._cmd_data(args)

        # finance-chat (conversational explanation)
        if raw_cmd == "finance-chat" or (action is not None and action.name == "finance-chat"):
            query = " ".join(parts[1:]) if len(parts) > 1 else "Explain current market conditions and macro drivers."
            out = self._route_nl_to_backend(query)
            self.store.append_turn("You", t)
            self.store.append_turn("DELTA", out)
            return out

        # finance-agent (autonomous quant research & evidence)
        # Truth rule: no scripted regime/confidence. Real backend or UNAVAILABLE.
        if raw_cmd == "finance-agent" or (action is not None and action.name == "finance-agent"):
            out = self._route_nl_to_backend(t)
            if not out or out.startswith(("unknown", "I can route", "ERROR")):
                out = ("finance-agent UNAVAILABLE — no live research backend. "
                       "No regime/confidence to report (provenance: UNAVAILABLE).")
            self.store.append_turn("You", t)
            self.store.append_turn("DELTA", out)
            return out

        # automation
        if raw_cmd == "automation" or (action is not None and action.name == "automation"):
            screen = SCREENS["automation"]
            vm = screen.build_viewmodel(self.store)
            body = screen.render_text(vm)
            self.store.append_turn("You", t)
            self.store.append_turn("DELTA", body)
            return body

        if action is not None:
            # symbol capture
            if args:
                maybe_sym = str(args[0]).upper()
                if maybe_sym.isalpha() and len(maybe_sym) <= 6:
                    self.store.symbol = maybe_sym
            # live backend first for finance verbs; screens render the chrome
            live_prefix = {
                "market": "/macro", "security": f"/quote {self.store.symbol}",
                "book": f"/quote {self.store.symbol}", "research": "/report",
                "portfolio": "/portfolio", "risk": "/risk",
                "execution": "/trade", "orders": "/portfolio",
                "scenarios": None, "alpha": None, "models": "/model list",
                "system": None, "session": None, "home": None,
                # Shame-proofing: analytic verbs route to the real REPL backend.
                "forecast": f"/forecast {self.store.symbol} 5",
                "crash": "/crash", "sentinel": "/sentinel status",
                "algo": "/algo momentum", "ask": None,
                "key": "/key", "lab": None, "recon": None,
                "audit": None, "halt": None, "mcps": "/mcps",
                "exec": "/trade", "desk": None, "markets": "/macro",
            }.get(action.name)
            live_out = ""
            if action.name in ("simulate", "backtest"):
                live_out = self._passthrough(
                    f"/backtest {self.store.symbol} 252" if args or action.name == "backtest"
                    else "/backtest")
                if live_out and not live_out.startswith(("unknown", "ERROR")):
                    handoff = f"{live_out}\n\n[Open analysis ↗] [Run research] [Simulate]"
                    self.store.append_turn("You", t)
                    self.store.append_turn("DELTA", handoff)
                    return handoff
            elif action.name in ("trade", "learn", "analyze"):
                live_out = self._route_nl_to_backend(t)
                if live_out and not live_out.startswith(("unknown", "I can route")):
                    self.store.append_turn("You", t)
                    self.store.append_turn("DELTA", live_out)
                    return live_out
            elif live_prefix:
                out = self._passthrough(
                    live_prefix if action.name not in ("security", "book")
                    else f"/quote {self.store.symbol}")
                if out and not out.startswith(("unknown", "ERROR")):
                    pass

            screen = SCREENS.get(action.screen)
            if screen is None:
                return f"unknown screen {action.screen}"
            self.store.set_screen(screen.name)
            vm = screen.build_viewmodel(self.store)
            self.store.publish(screen.name, vm)
            body = screen.render_text(vm)
            # attach backend output when useful (quote/risk/portfolio)
            extra = getattr(self, "_last_live", "")
            if extra and extra not in body:
                body = f"{body}\n{extra}"
            # browser hint for heavy work (terminal-native export; no web UI per ADR-0006)
            if action.name in ("research", "simulate", "backtest", "portfolio", "analyze"):
                if "[Open analysis" not in body:
                    body = f"{body}\n\n[Run research] [Simulate] [Export]\n(Full detail available via /export markdown|json|csv)"
            self.store.append_turn("You", t)
            self.store.append_turn("DELTA", body)
            return body

        # chat fallback: route NL to backend, never block kill path
        out = self._route_nl_to_backend(t)
        self.store.append_turn("You", t)
        self.store.append_turn("DELTA", out)
        return out

    def _route_nl_to_backend(self, t: str) -> str:
        # 1) FinanceCommandRouter + TraderRuntime when available
        try:
            # pyrefly: ignore [missing-import]
            from trader.command_router import FinanceCommandRouter

            req = FinanceCommandRouter().route(t)
            try:
                # pyrefly: ignore [missing-import]
                from apps.cli.delta import ExistingSystemBackend

                resp = ExistingSystemBackend().dispatch(req)
                if resp:
                    return resp
            except Exception:
                pass
        except Exception:
            pass
        # 2) delta_os conversational engine
        be = self.backend()
        if be is not None:
            try:
                out, _ = be.handle(t)
                if out:
                    return out
            except Exception as exc:
                return f"ERROR: {exc}"
        return ("I can route that to a workspace: try /market, /book NVDA, "
                "/research, /portfolio, /risk, /execution, /system.  ( / for all )")

    def _passthrough(self, t: str) -> str:
        be = self.backend()
        if be is None:
            return "ERROR: engine unavailable (try /system)"
        try:
            out, _ = be.handle(t)
            self._last_live = out
            # sync model/broker/effort/thinking chips
            try:
                self.store.broker = getattr(be, "broker_name", self.store.broker)
                bm = getattr(be, "model_name", "")
                if bm and "/model" in t:
                    self.store.set_model(bm)
                    self._persist_session()
                for _chip, _attr in (("effort", "effort"), ("thinking", "thinking")):
                    if f"/{_chip}" in t:
                        v = getattr(be, _attr, "")
                        if v:
                            setattr(self.store, _attr, v)
                            self._persist_session()
            except Exception:
                pass
            self._drain_sentinel_alerts(be)
            self.refresh_chrome()
            return out
        except Exception as exc:
            return f"ERROR: {exc}"

    def _drain_sentinel_alerts(self, be) -> None:
        """Surface backend sentinel alerts in the alerts column (TUI-hosted
        brain fan-out). Never raises; dedupes by timestamp+event."""
        try:
            sent = getattr(be, "sentinel", None)
            pending = list(getattr(sent, "alerts", []) or [])
        except Exception:
            return
        if not pending:
            return
        try:
            seen = getattr(self, "_surfaced_alert_ids", None)
            if seen is None:
                seen = self._surfaced_alert_ids = set()
            try:
                from delta_tui.widgets.toast import ToastManager
                tm = getattr(self, "_toasts", None)
                if tm is None:
                    tm = self._toasts = ToastManager()
            except Exception:
                tm = None
            for a in pending[-20:]:
                aid = (str(a.get("timestamp", "")), str(a.get("event", "")))
                if aid in seen:
                    continue
                seen.add(aid)
                line = f"[{aid[0][11:19]}] {a.get('level', '?')}: {a.get('message', '')}"
                try:
                    self.store.alerts.append(line)
                    self.store.alerts = self.store.alerts[-50:]
                except Exception:
                    pass
                if tm is not None:
                    try:
                        if str(a.get("level", "")).upper() == "CRITICAL":
                            tm.breach(line)
                        else:
                            tm.push("warn" if str(a.get("level", "")).upper() == "WARNING" else "info", line)
                    except Exception:
                        pass
        except Exception:
            pass

    def _palette_text(self, query: str) -> str:
        return format_palette_box(query)

    # -- A4: doctor/status/data (real probes, honest states, never faked) --
    def _run_doctor_probes(self):
        """Run the real probe layer (mock point: patch run_all in tests)."""
        from delta_os import doctor_connections as _D
        be = self.backend()
        vault = getattr(be, "vault", None) if be is not None else None
        try:
            return _D.run_all(vault=vault)
        except TypeError:
            return _D.run_all()

    def _cmd_doctor(self, args: list) -> str:
        try:
            checks = self._run_doctor_probes()
            from delta_os import doctor_connections as _D
            body = ("DOCTOR — live connection probes (never faked)\n"
                    + _D.render_table(checks))
        except Exception as exc:
            body = f"DOCTOR UNAVAILABLE [SOURCE/no-probe] — {exc}"
        self.store.append_turn("You", ("/doctor " + " ".join(args)).strip())
        self.store.append_turn("DELTA", body)
        return body

    def _cmd_status(self, args: list) -> str:
        s = self.store
        be = self.backend()

        def _safe(fn, fallback="UNAVAILABLE"):
            try:
                v = fn()
                return v if v not in (None, "") else fallback
            except Exception:
                return fallback

        broker = _safe(lambda: getattr(be, "broker_name", s.broker), s.broker)
        safety_mode = _safe(
            lambda: str(getattr(getattr(be, "safety", None), "mode", "")
                        or s.risk_state or "?"))
        regime = _safe(lambda: getattr(be, "regime_chip", "n/a"), "n/a")
        var_chip = _safe(lambda: getattr(be, "var_chip", "n/a"), "n/a")
        model = _safe(lambda: getattr(be, "model_name", s.model), s.model)
        portfolio = _safe(be._ledger_equity) if be is not None else "UNAVAILABLE"
        if isinstance(portfolio, float):
            try:
                positions = be._ledger_positions()
                portfolio = (f"equity ${portfolio:,.2f} "
                             f"positions {positions or 'flat'}")
            except Exception:
                portfolio = f"equity ${portfolio:,.2f}"
        elif portfolio is None:
            portfolio = "UNAVAILABLE (ledger equity unreadable)"
        orders = _safe(lambda: f"{len(be._ledger_positions())} symbols tracked "
                       "(paper rail)")
        mcp = _safe(lambda: _mcp_summary(), "UNPROBED (use /mcp)")
        gpu = _safe(lambda: _gpu_summary(), "UNAVAILABLE (torch unreadable)")
        import sys as _sys
        runtime = f"python {_sys.version.split()[0]}"
        market = "LIVE" if s.market_live else "CLOSED"
        lines = [
            (f"STATUS workspace={s.workspace} session={s.session_id} "
             f"symbol={s.symbol} mode={s.mode.value}"),
            f"runtime: {runtime} | data: {s.data_health} (live={s.data_live})",
            f"portfolio: {portfolio}",
            (f"risk: safety={safety_mode} state={s.risk_state} "
             f"regime={regime} var99={var_chip}"),
            f"model: {model} | agent: {s.agent} | broker: {broker} | market: {market}",
            f"orders: {orders}",
            f"mcp: {mcp} | gpu: {gpu}",
        ]
        body = "\n".join(lines)
        self.store.append_turn("You", ("/status " + " ".join(args)).strip())
        self.store.append_turn("DELTA", body)
        return body

    def _snapshot_feed_health(self) -> None:
        """Best-effort feed probe feeding DataScreen. Never raises.

        Fresh TIER1/TIER2 quotes publish a READY feed snapshot; anything else
        (stale cache, synthetic, offline) leaves feeds empty so the honest
        UNAVAILABLE render stays — the fix is attempting, not inventing.
        """
        try:
            be = self.backend()
            data = getattr(be, "data", None) if be is not None else None
            if data is None:
                from delta_os.data_router import DataRouter
                data = DataRouter()
            qf = data.quote(self.store.symbol, days=30)
            prov = getattr(qf, "provenance", None)
            tier = getattr(prov, "tier", "")
            if tier in ("TIER1", "TIER2"):
                try:
                    age = float(getattr(prov, "age_s", 0.0) or 0.0)
                except Exception:
                    age = 0.0
                self.store.viewmodels["data_snapshot"] = {
                    "feeds": ((self.store.symbol, "READY"),),
                    "quality": "FRESH",
                    "freshness_s": age,
                }
                self.store.data_live = True
                self.store.data_health = "HEALTHY"
            else:
                self.store.data_live = False
                self.store.data_health = ("DEGRADED" if tier == "TIER3-CACHE"
                                          else "UNAVAILABLE")
        except Exception:
            pass

    def _cmd_data(self, args: list) -> str:
        try:
            self._snapshot_feed_health()
        except Exception:
            pass
        screen = SCREENS["data"]
        self.store.set_screen(screen.name)
        vm = screen.build_viewmodel(self.store)
        self.store.publish(screen.name, vm)
        body = screen.render_text(vm)
        self.store.append_turn("You", ("/data " + " ".join(args)).strip())
        self.store.append_turn("DELTA", body)
        return body

    def _cmd_model(self, args: list) -> str:
        if not args:
            out = self._passthrough("/model list")
            return f"Model: {self.store.model}\n{out}\nusage: /model switch <name> | /model list"
        if args[0].lower() in ("list", "info"):
            return self._passthrough(f"/model {args[0]}")
        if args[0].lower() == "switch" and len(args) > 1:
            name = args[1]
            out = self._passthrough(f"/model switch {name}")
            # Parse ONLY the model token after '->' (never the trailing
            # sentence — a prior build poisoned store.model with it).
            import re as _re
            m = _re.search(r"->\s*([A-Za-z0-9][A-Za-z0-9._-]*)", out)
            if m:
                self.store.set_model(m.group(1))
            else:
                self.store.set_model(name)
            self._persist_session()
            be = self.backend()
            if be is not None:
                try:
                    be.model_name = self.store.model
                except Exception:
                    pass
            return f"Model: {self.store.model}\n{out}"
        # bare name = switch shorthand
        return self._cmd_model(["switch"] + list(args))

    def _cmd_agent(self, args: list) -> str:
        if not args:
            return f"Agent: {self.store.agent}\nAvailable: {', '.join(AGENTS)}\nusage: /agent <name>"
        name = args[0].lower()
        # legacy alias: the long-time default persona name
        if name in ("quant-researcher", "quant", "delta"):
            name = "research-agent"
        match = next((a for a in AGENTS if a.lower() == name or name in a.lower()), None)
        if match is None:
            return f"unknown agent {args[0]} — Available: {', '.join(AGENTS)}"
        self.store.set_agent(match)
        self._persist_session()
        return f"Agent: {self.store.agent} ● ready"

    def _cmd_session(self, args: list) -> str:
        if not args:
            return f"Session: {self.store.session_id}\nusage: /session <name> | /session new <name>"
        if args[0].lower() == "new" and len(args) > 1:
            self.store.set_session(args[1])
        else:
            self.store.set_session(args[0])
        self.store.conversation.clear()
        self.store.set_screen("home")
        self._persist_session()
        be = self.backend()
        if be is not None:
            try:
                be.workspace = self.store.session_id
            except Exception:
                pass
        return f"Session: {self.store.session_id} — fresh context (history preserved on disk)"

    def _cmd_open(self, args: list) -> str:
        # Truth rule: no web app exists — do not claim one opened.
        label = " ".join(args) if args else f"{self.store.workspace} {self.store.symbol}"
        ref = f"delta://{self.store.workspace}/{self.store.symbol}"
        self.store.browser_ref = ref
        return (f"Browser workspace ref → {label}\n"
                f"Ref: {ref}\n"
                f"DELTA Web is NOT IMPLEMENTED — ref stored for future viewer.\n"
                f"(provenance: UNAVAILABLE)")

    def _kill_step(self, text: str) -> str:
        # Exact token only: bare "CONFIRM" word. "unconfirmed" must NOT match.
        import re as _re
        if _re.search(r"(?i)(?:^|\s|/|\")CONFIRM(?:\s|$|\"|'|\))", f" {text} "):
            be = self.backend()
            if be is None:
                return "KILL FAILED — engine unavailable (no halt performed)."
            try:
                out, _ = be.handle("/kill")
            except Exception as exc:
                return f"KILL FAILED — backend error, no halt performed: {exc}"
            try:
                smode = str(getattr(getattr(be, 'safety', None), 'mode', '') or '').upper()
            except Exception:
                smode = ""
            if smode != "HALTED":
                return (f"KILL FAILED — enforcer did not confirm halt (mode={smode or 'UNKNOWN'}). "
                        f"Backend said: {out}")
            self.store.kill_armed = True
            self.store.risk_state = "BLOCKED"
            self.pending_kill = False
            return (
                "┌──────────────────────────────────────────┐\n"
                "│            EXECUTION HALTED              │\n"
                "│                                          │\n"
                "│ Kill switch activated                    │\n"
                "│                                          │\n"
                "│ New orders       BLOCKED                 │\n"
                "│ Existing orders CANCEL REQUESTED         │\n"
                "│ Agents           RESTRICTED              │\n"
                "│ Research         AVAILABLE               │\n"
                "│                                          │\n"
                "│ [Review state] [Resume authorization]    │\n"
                "└──────────────────────────────────────────┘"
            )
        self.pending_kill = True
        return ("KILL SWITCH ARMED — type `/kill CONFIRM` or `/kill-switch CONFIRM` to engage.\n"
                "This bypasses the LLM and hits the risk governor directly.\n"
                "(Ctrl+K only opens this hint — it never halts without confirmation.)")

    def header(self, state: str = "A") -> str:
        # pyrefly: ignore [missing-import]
        from .widgets.chrome import header_text
        return header_text(header_model(self.store), state=state)

    def footer(self, state: str = "A") -> str:
        # pyrefly: ignore [missing-import]
        from .widgets.chrome import footer_text
        return footer_text(footer_model(self.store), state=state)

    # -- runners ---------------------------------------------------------
    def run_textual(self):  # pragma: no cover
        from textual.app import App, ComposeResult
        from textual.widgets import Header, Footer, Input, Static

        controller = self

        class _TUI(App):
            CSS = "Screen { layout: vertical; }"

            def compose(self) -> ComposeResult:
                yield Header()
                self.chrome = Static(controller.render_current())
                yield self.chrome
                self.cmd = Input(placeholder="Ask DELTA anything, research a strategy, analyze a market...")
                yield self.cmd
                yield Footer()

            def on_input_submitted(self, ev) -> None:
                txt = ev.value
                if txt.strip() == "/":
                    out = controller._palette_text("")
                    self.chrome.update(f"{controller.render_current()}\n\n{out}")
                else:
                    out = controller.dispatch(txt)
                    self.chrome.update(f"{controller.render_current()}\n\n{out}")
                self.cmd.value = ""

        _TUI().run()

    def render_current(self) -> str:
        self.refresh_chrome()
        name = self.store.workspace
        # State A: New-session splash while no conversation turns yet
        if not self.store.conversation and name == "home":
            screen = SCREENS["home"]
            try:
                splash = screen.render_for(self.store)  # type: ignore[attr-defined]
            except Exception:
                vm = screen.build_viewmodel(self.store)
                splash = screen.render_text(vm)
            return f"{self.header('A')}\n\n{splash}\n{self.footer('A')}"

        # State B: Active conversation workspace when on home with conversation history
        if name == "home" and self.store.conversation:
            lines = [self.header("B"), ""]
            for turn in self.store.conversation[-8:]:
                role = turn.get("role", "You")
                text = turn.get("text", "")
                lines.append(f"{role}")
                for line in text.split("\n"):
                    lines.append(f"{line}")
                lines.append("")
            lines.append(self.footer("B"))
            lines.append("> _")
            return "\n".join(lines)

        # State C: Contextual workspace screen (market, research, risk, etc.)
        screen = SCREENS.get(name, SCREENS["home"])
        vm = screen.build_viewmodel(self.store)
        return f"{self.header('B')}\n\n{screen.render_text(vm)}\n\n{self.footer('context')}"

    def run(self) -> int:
        try:
            import textual  # noqa: F401
            has_textual = True
        except Exception:
            has_textual = False
        width = shutil.get_terminal_size((120, 30)).columns
        if has_textual and width >= 80:
            try:
                return self.run_textual() or 0
            except Exception:
                pass
        # Rich/plain fallback loop (SSH / small terminals / CI)
        c = None
        try:
            from rich.console import Console
            c = Console()
        except Exception:
            c = None

        if c is not None and not self.store.conversation and self.store.workspace == "home":
            # pyrefly: ignore [missing-import]
            from .widgets.chrome import header_rich, render_frontpart
            width = shutil.get_terminal_size((100, 30)).columns
            hdr = header_rich(header_model(self.store), state="A", width=width)
            body = render_frontpart(self.store, width=width, use_rich=True)
            c.print(hdr)
            c.print(body)
        else:
            print(self.render_current())
        # prompt_toolkit when available for / completion + Ctrl+K/Ctrl+O
        prompt_fn = None
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.completion import WordCompleter
            from prompt_toolkit.key_binding import KeyBindings

            # A4: completer from the real command registry (never hardcoded).
            words = build_completer_words()
            kb = KeyBindings()

            @kb.add("c-k")
            def _(event):
                # Keymap truth: Ctrl+K opens the palette (never instant kill).
                # Kill stays Ctrl+X K (risk cockpit) + typed /kill CONFIRM only.
                event.app.current_buffer.text = "/"

            @kb.add("c-o")
            def _(event):
                event.app.current_buffer.text = "/open"

            # A4: leader sequences per delta_tui.keymap (Ctrl+X then key).
            # Each chord stages its slash text — nothing dispatches without
            # Enter. Fallback-loop scope: the minimal Textual shell passes
            # raw text (slash works there; chords don't — see keymap notes).
            try:
                from . import keymap as _km

                def _bind_leader(second: str, _action: str) -> None:
                    @kb.add("c-x", second)
                    def _go(event, _a=_action):
                        text = _km.leader_slash(_a)
                        if text:
                            event.app.current_buffer.text = text

                for _seq, _action in _km.BINDINGS.items():
                    _parts = _seq.split(" ")
                    if (len(_parts) == 2 and _parts[0] == "ctrl+x"
                            and len(_parts[1]) == 1):
                        _bind_leader(_parts[1], _action)
            except Exception:
                pass

            session = PromptSession(completer=WordCompleter(words, ignore_case=True),
                                    key_bindings=kb)

            def _ask():
                return session.prompt("> ")
            prompt_fn = _ask
        except Exception:
            prompt_fn = None
        while True:
            try:
                if prompt_fn is not None:
                    try:
                        text = prompt_fn().strip()
                    except (EOFError, KeyboardInterrupt):
                        print("\nbye (session preserved).")
                        return 0
                else:
                    text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nbye (session preserved).")
                return 0
            if not text:
                continue
            if text.lower() in ("/exit", "/quit", "exit", "quit"):
                print("bye")
                return 0
            try:
                if text.strip() == "/":
                    print(self._palette_text(""))
                    continue
                out = self.dispatch(text)
                if out:
                    if not out.startswith(("DELTA", "You", "┌", "╭", "AUTOMATIONS", "RESEARCH", "MARKET")):
                        print(f"\nDELTA\n{out}\n")
                    else:
                        print(f"\n{out}\n")
            except Exception as exc:  # never crash the loop
                print(f"ERROR: {exc}")


def main(mode: str = "PAPER") -> int:
    return DeltaApp(DeltaMode.parse(mode)).run()


if __name__ == "__main__":
    raise SystemExit(main())
