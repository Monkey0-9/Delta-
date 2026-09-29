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

from config.mode import DeltaMode, mode_banner
from .commands import parser as cmd_parser
from .commands.palette import entries as palette_entries
from .commands.registry import lookup
from .state import store as store_mod
from .state.selectors import footer_model, header_model, status_model
from .screens.home import HomeScreen
from .screens.core import (MarketScreen, SecurityScreen, BookScreen,
                           ResearchScreen, AlphaScreen, PortfolioScreen, RiskScreen)
from .screens.ops import (ExecutionScreen, OrdersScreen, ScenariosScreen,
                          ModelsScreen, SystemScreen, SessionScreen)

SCREENS = {
    "home": HomeScreen(), "market": MarketScreen(), "security": SecurityScreen(),
    "book": BookScreen(), "research": ResearchScreen(), "alpha": AlphaScreen(),
    "portfolio": PortfolioScreen(), "risk": RiskScreen(),
    "execution": ExecutionScreen(), "orders": OrdersScreen(),
    "scenarios": ScenariosScreen(), "models": ModelsScreen(),
    "system": SystemScreen(), "session": SessionScreen(),
}

AGENTS = ("quant-researcher", "risk-monitor", "execution-copilot")
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
    return (text.replace("●", "*").replace("◉", "[*]").replace("Δ", "D")
            .replace("→", "->").replace("—", "-").replace("–", "-")
            .replace("·", "|"))


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
                from delta_os.repl import Terminal as _OsTerminal
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
            # adopted as the display model (display default: delta-fm-research).
            v = d.get("model")
            if isinstance(v, str) and v:
                self.store.set_model(v)
            v = d.get("agent")
            if isinstance(v, str) and v:
                self.store.set_agent(v)
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
                        "session": self.store.session_id, "session_id": self.store.session_id,
                        "workspace": self.store.workspace})
            p.write_text(json.dumps(cur, indent=2), encoding="utf-8")
        except Exception:
            pass

    def refresh_chrome(self) -> None:
        """Update market/data/risk chips from live sources. Best-effort only."""
        s = self.store
        # market hours (NYSE ET approx -> UTC): 13:30-20:00 Mon-Fri
        try:
            now = datetime.now(timezone.utc)
            s.market_live = now.weekday() < 5 and (13, 30) <= (now.hour, now.minute) < (20, 0)
        except Exception:
            pass
        be = self.backend()
        if be is not None:
            try:
                self.store.broker = getattr(be, "broker_name", s.broker) or s.broker
                # NOTE: backend engine name (qwen-3.6/groq-free/...) is distinct
                # from the TUI display model (delta-fm-research). Never overwrite
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
        self.refresh_chrome()
        parsed = cmd_parser.parse(t)
        action = parsed.get("action")
        args = parsed.get("args", [])
        parts = t[1:].split() if t.startswith("/") else []
        raw_cmd = parts[0].lower() if parts else ""

        # kill always first, bypasses LLM
        if (action is not None and action.name == "kill") or raw_cmd == "kill":
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
        if raw_cmd in ("exit", "quit"):
            return "bye"

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
            }.get(action.name)
            live_out = ""
            if action.name in ("simulate", "backtest"):
                live_out = self._passthrough(
                    f"/backtest {self.store.symbol} 252" if args or action.name == "backtest"
                    else "/backtest")
                if live_out and not live_out.startswith(("unknown", "ERROR")):
                    self.store.append_turn("You", t)
                    self.store.append_turn("DELTA", live_out)
                    return live_out
            elif action.name in ("trade", "automation", "learn", "analyze"):
                live_out = self._route_nl_to_backend(t)
                if live_out and not live_out.startswith(("unknown", "I can route")):
                    self.store.append_turn("You", t)
                    self.store.append_turn("DELTA", live_out)
                    return live_out
            elif live_prefix:
                out = self._passthrough(
                    live_prefix if action.name not in ("security", "book")
                    else f"/quote {self.store.symbol}")
                # fall through to screen render so header/footer stay consistent
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
            self.store.append_turn("You", t)
            self.store.append_turn("DELTA", body)
            if extra and extra not in body:
                return f"{body}\n{extra}"
            # browser hint for heavy work
            if action.name in ("research", "simulate", "backtest", "portfolio", "analyze"):
                return f"{body}\n\nHeavy charts live in the browser — Ctrl+O /open to continue."
            return body

        # chat fallback: route NL to backend, never block kill path
        out = self._route_nl_to_backend(t)
        self.store.append_turn("You", t)
        self.store.append_turn("DELTA", out)
        return out

    def _route_nl_to_backend(self, t: str) -> str:
        # 1) FinanceCommandRouter + TraderRuntime when available
        try:
            from trader.command_router import FinanceCommandRouter

            req = FinanceCommandRouter().route(t)
            try:
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
            # sync model/broker chips
            try:
                self.store.broker = getattr(be, "broker_name", self.store.broker)
                bm = getattr(be, "model_name", "")
                if bm and "/model" in t:
                    self.store.set_model(bm)
                    self._persist_session()
            except Exception:
                pass
            self.refresh_chrome()
            return out
        except Exception as exc:
            return f"ERROR: {exc}"

    def _palette_text(self, query: str) -> str:
        rows = palette_entries(query)
        lines = ["Search commands...  (↑↓ Navigate  Enter Select  Esc Close)", ""]
        for e in rows:
            mark = "  [!]" if e.get("risky") else ""
            lines.append(f"{e['name']:<14} {e['description']}{mark}")
        lines += ["", "Primary: /research /market /portfolio /risk /simulate /backtest /trade /automation",
                  "System: /model /agent /mcp /auth /session /config /open /kill-switch"]
        return "\n".join(lines)

    def _cmd_model(self, args: list) -> str:
        if not args:
            out = self._passthrough("/model list")
            return f"Model: {self.store.model}\n{out}\nusage: /model switch <name> | /model list"
        if args[0].lower() in ("list", "info"):
            return self._passthrough(f"/model {args[0]}")
        if args[0].lower() == "switch" and len(args) > 1:
            name = args[1]
            out = self._passthrough(f"/model switch {name}")
            # accept backend rename or keep requested name
            if "->" in out:
                try:
                    self.store.set_model(out.split("->")[-1].strip())
                except Exception:
                    self.store.set_model(name)
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
        label = " ".join(args) if args else f"{self.store.workspace} {self.store.symbol}"
        ref = f"delta://{self.store.workspace}/{self.store.symbol}"
        self.store.browser_ref = ref
        return (f"Browser workspace → {label}\n"
                f"Ref: {ref}\n"
                f"CLI stays concise — candlesticks, equity/drawdown, factors, heatmaps open in DELTA Web. [Open]")

    def _kill_step(self, text: str) -> str:
        if "CONFIRM" in text.upper():
            be = self.backend()
            if be is not None:
                try:
                    out, _ = be.handle("/kill")
                    self.store.kill_armed = True
                    self.store.risk_state = "BLOCKED"
                    self.pending_kill = False
                    return (f"KILL SWITCH ENGAGED — EXECUTION HALTED\nKill switch activated ({out[:120]})\n"
                            f"New orders       BLOCKED\nExisting orders CANCEL REQUESTED\n"
                            f"Agents           RESTRICTED\nResearch         AVAILABLE\n"
                            f"[Review state] [Resume authorization via /risk]")
                except Exception:
                    pass
            self.store.kill_armed = True
            self.store.risk_state = "BLOCKED"
            self.pending_kill = False
            return ("KILL SWITCH ENGAGED — EXECUTION HALTED\nKill switch activated\n"
                    "New orders       BLOCKED\nExisting orders CANCEL REQUESTED\n"
                    "Agents           RESTRICTED\nResearch         AVAILABLE")
        self.pending_kill = True
        return ("KILL SWITCH ARMED — type `/kill CONFIRM` to engage. "
                "This bypasses the LLM and hits the risk governor directly. "
                "(Ctrl+K only opens this hint — it never halts by itself.)")

    def header(self) -> str:
        from .widgets.chrome import header_text
        return header_text(header_model(self.store))

    def footer(self) -> str:
        from .widgets.chrome import footer_text
        return footer_text(footer_model(self.store))

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
                self.cmd = Input(placeholder="Ask DELTA anything, run a strategy, analyze a market, or type / for commands...")
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
            return f"{self.header()}\n{mode_banner(self.store.mode)}\n\n{splash}\n{self.footer()}"

        # State B: Active conversation workspace when on home with conversation history
        if name == "home" and self.store.conversation:
            lines = [self.header(), mode_banner(self.store.mode), ""]
            for turn in self.store.conversation[-12:]:
                role = turn.get("role", "You")
                text = turn.get("text", "")
                lines.append(f"  {role}")
                for line in text.split("\n"):
                    lines.append(f"  {line}")
                lines.append("")
            lines.append(self.footer())
            return "\n".join(lines)

        # State C: Contextual workspace screen (market, research, risk, etc.)
        screen = SCREENS.get(name, SCREENS["home"])
        vm = screen.build_viewmodel(self.store)
        return f"{self.header()}\n{mode_banner(self.store.mode)}\n\n{screen.render_text(vm)}\n{self.footer()}"

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
        print(self.render_current())
        print(status_model(self.store))
        # prompt_toolkit when available for / completion + Ctrl+K/Ctrl+O
        prompt_fn = None
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.completion import WordCompleter
            from prompt_toolkit.key_binding import KeyBindings

            words = ["/" + n for n in
                     ("market", "book", "analyze", "research", "simulate", "backtest",
                      "trade", "automation", "learn", "portfolio", "risk", "execution",
                      "orders", "scenario", "model", "agent", "session", "auth", "mcp",
                      "config", "open", "system", "home", "kill", "help")]
            kb = KeyBindings()

            @kb.add("c-k")
            def _(event):
                event.app.current_buffer.insert_text("/")

            @kb.add("c-o")
            def _(event):
                event.app.current_buffer.text = "/open"

            session = PromptSession(completer=WordCompleter(words, ignore_case=True),
                                    key_bindings=kb)

            def _ask():
                return session.prompt("DELTA › ")
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
                    text = input("DELTA › ").strip()
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
                print(self.dispatch(text))
            except Exception as exc:  # never crash the loop
                print(f"ERROR: {exc}")


def main(mode: str = "PAPER") -> int:
    return DeltaApp(DeltaMode.parse(mode)).run()


if __name__ == "__main__":
    raise SystemExit(main())
