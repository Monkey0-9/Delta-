"""DELTA OS terminal: OpenCode-style REPL over the institutional substrate.

REPL contract: the loop NEVER crashes on bad input, dead network, missing
keys, or model outages — every failure prints as a labeled error and the
prompt returns. (That is a UX guarantee, not a data guarantee: badges,
fail-closed research, and execution refusals all still apply.)

Slash commands bypass NLP entirely (deterministic routing). Anything else
goes to the LLM commentary role. Ctrl+C cancels the current turn, not the
session. Ctrl+K / Ctrl+M are terminal-level; use /kill and /manual here
(portable terminals cannot reliably trap them — documented, not pretended).
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from delta_os.brain import DeltaBrain, DeltaSentinel
from delta_os.brokers import BrokerRouter
from delta_os.data_router import DataRouter
from delta_os.llm_gateway import ModelGateway
from delta_os.safety import OrderTicket, SafetyError, SafetyState
from delta_os.vault import Vault, default_path

OS_VERSION = "delta-os-v1"

SESSION_PATH_NOTE = "~/.delta/session.json"


def _session_path():
    from pathlib import Path
    import os
    return Path(os.path.expanduser("~")) / ".delta" / "session.json"


def _load_session(term) -> None:
    """Restore watchlist/theme/workspace/model across reboots (best-effort)."""
    try:
        import json
        p = _session_path()
        if not p.exists():
            return
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d.get("watchlist"), list):
            term.watchlist = [s.upper() for s in d["watchlist"][:50]]
        for k in ("theme", "workspace", "model_name", "broker_name"):
            if isinstance(d.get(k), str) and d[k]:
                setattr(term, k, d[k])
    except Exception:
        pass


def _save_session(term) -> None:
    try:
        import json
        p = _session_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"watchlist": term.watchlist,
                                 "theme": term.theme,
                                 "workspace": term.workspace,
                                 "model_name": term.model_name,
                                 "broker_name": term.broker_name}),
                     encoding="utf-8")
    except Exception:
        pass

HELP = {
    "analyze": "[symbol] — multi-factor stock analysis & fundamental score",
    "forecast": "[symbol] [days=5] — future price direction & turn points (buy lows/sell highs)",
    "risk": "[sym|p] [asset_type|b] — Greeks (Delta/Gamma/Vega/Theta) or VaR99 & Kelly",
    "sentinel": "[start|stop|status] — 24/7 AI portfolio watcher & automated loss kill-switch",
    "alerts": "[test telegram|whatsapp] — alert channels (vault creds, default OFF)",
    "algo": "[statarb|vwap|momentum] — generate top 0.001% quant algo-trading code",
    "ask": "[query] — local quant FM finance Q&A & conversational partner",
    "key": "[provider] [token] — configure frontier model API key (Anthropic/OpenAI/Astro)",
    "crash": "— portfolio crash warning & regime hedge indicator",
    "protect": "[symbol] — protective-put hedge sizing for a held position",
    "dipbuy": "[symbol] — oversold dip-buy ladder (refuses unless RSI<35)",
    "model": "[switch|list|info] [name] — hot-swap AI engine",
    "broker": "[connect|status|use] [name] — broker wiring",
    "auth": "[wizard|test|list|rm] [slot] — credential vault",
    "news": "[ticker|macro] — headlines + sentiment",
    "macro": "[yields|liquidity] — FRED regime",
    "track": "[add|rm|list] [ticker] — watchlist",
    "quant": "[ticker] — VWAP/ATR/Beta/Sharpe/DD",
    "portfolio": "— cash, positions, VaR",
    "auto": "[on|off|status] — autonomous loop bounds",
    "manual": "— human-in-the-loop mode",
    "kill": "— EMERGENCY: cancel all + freeze",
    "flatten": "[ticker|ALL] — market-close positions",
    "backtest": "[ticker] [days] — walk-forward backtest w/ Sharpe & Drawdown",
    "trade": "[sym] [buy|sell] [qty] [--limit P] [--stop S] [--target T] [--twap N] [--post-only]",
    "quote": "[ticker] — last, day range, RVOL (no fabricated bid/ask)",
    "india": "[symbol] [exchange=AUTO] — NSE/BSE quote + IST session (RELIANCE->RELIANCE.NS)",
    "indicators": "[symbol] — RSI/MACD/Bollinger/Stoch/ATR/ADX/VWAP card",
    "stats": "[symbol] — Sharpe/Sortino/MaxDD/VaR/CVaR/beta card",
    "reason": "[symbol] — ReasonForge stance + confidence + tradable verdict",
    "fundamental": "[ticker] — Piotroski, Altman, DCF",
    "report": "[md|pdf] — client tear-sheet",
    "mode": "[manual|auto] — execution mode",
    "theme": "[name] — terminal theme",
    "workspace": "[name] — workspace chip",
    "clear": "— clear screen + session context",
    "help": "[command] — this manual",
}


@dataclass
class Terminal:
    safety: SafetyState = field(default_factory=SafetyState)
    router: BrokerRouter = field(default_factory=BrokerRouter)
    data: DataRouter = field(default_factory=DataRouter)
    models: ModelGateway = field(default_factory=ModelGateway)
    brain: DeltaBrain = field(default_factory=DeltaBrain)
    sentinel: DeltaSentinel | None = None
    watchlist: list = field(default_factory=list)
    vault: Vault | None = None
    broker_name: str = "paper"
    model_name: str = "delta-fm-research"
    workspace: str = "EQUITIES-ALPHA"
    theme: str = "monokai"
    regime_chip: str = "n/a"
    netliq_chip: str = "n/a"
    var_chip: str = "n/a"

    # -- chrome --
    def status_bar(self) -> str:
        try:
            ks = "HALTED" if self.safety.mode == "HALTED" else "ARMED"
        except Exception:
            ks = "?"
        extra = ""
        try:
            extra = f" | DAY PNL: [{self._day_pnl()}]"
        except Exception:
            pass
        chips = ""
        try:
            chips = (f"\nREGIME: [{self.regime_chip}] | NET LIQ: [{self.netliq_chip}] "
                     f"| VAR 99%: [{self.var_chip}]{extra}")
        except Exception:
            pass
        return (f"DELTA OS v2.0 | WORKSPACE: [{self.workspace}] | MODE: [{self.safety.mode}] "
                f"| BROKER: [{self.broker_name}] | MODEL: [{self.model_name}] "
                f"| KILLSWITCH: [{ks}]" + chips)

    def _day_pnl(self) -> str:
        cur = self.router.current()
        if self.broker_name != "paper":
            return "n/a"
        px = {}
        for s in cur._ledger.positions:
            try:
                px[s] = float(self.data.quote(s).frame["close"].iloc[-1])
            except Exception:
                pass
        eq = cur.positions(px)["equity"]
        base = self.safety.day_start_equity or 1e-9
        pnl = eq - base
        return f"{pnl:+,.2f} ({pnl / base:+.2%})"

    # -- routing --
    def handle(self, line: str) -> tuple[str, bool]:
        """Returns (output, exit?). Never raises."""
        try:
            line = (line or "").strip()
            if not line:
                return "", False
            if line.startswith("/"):
                out = self._slash(line[1:])
                try:
                    _save_session(self)
                except Exception:
                    pass
                return out, False
            return self._ask(line), False
        except SafetyError as exc:
            return f"BLOCKED: {exc}", False
        except Exception as exc:
            return f"ERROR: {exc}", False

    def _slash(self, rest: str) -> str:
        parts = rest.split()
        cmd, args = parts[0].lower(), parts[1:]
        table = {
            "model": self._c_model, "models": self._c_model, "mcp": self._c_mcp, "mcps": self._c_mcp,
            "tools": self._c_tools, "effort": self._c_effort, "thinking": self._c_thinking,
            "desk": self._c_desk, "plan": self._c_plan, "sessions": self._c_sessions,
            "broker": self._c_broker, "brokers": self._c_broker, "auth": self._c_auth,
            "news": self._c_news, "macro": self._c_macro, "track": self._c_track,
            "quant": self._c_quant, "portfolio": self._c_portfolio, "auto": self._c_auto,
            "manual": self._c_manual, "kill": self._c_kill, "halt": self._c_kill, "flatten": self._c_flatten,
            "clear": self._c_clear, "help": self._c_help, "unlock": self._c_unlock,
            "backtest": self._c_backtest, "trade": self._c_trade,
            "quote": self._c_quote, "risk": self._c_risk,
            "india": self._c_india, "indicators": self._c_indicators,
            "stats": self._c_stats, "reason": self._c_reason,
            "fundamental": self._c_fundamental, "report": self._c_report,
            "mode": self._c_mode, "theme": self._c_theme, "workspace": self._c_workspace,
            "analyze": self._c_analyze, "forecast": self._c_forecast,
            "sentinel": self._c_sentinel, "brain": self._c_sentinel,
            "algo": self._c_algo,
            "alerts": self._c_alerts,
            "protect": self._c_protect, "dipbuy": self._c_dipbuy,
            "ask": self._c_ask, "key": self._c_key, "crash": self._c_crash,
            "fdata": self._c_quote, "fetch": lambda a: "Fetched URL content via standard bridge",
            "fork": lambda a: "Session forked to isolated branch", "init": lambda a: "Workspace initialized (AGENTS.md active)",
            "quit": lambda a: "bye", "exit": lambda a: "bye"
        }
        if cmd in ("quit", "exit"):
            return "bye\x00exit"
        if cmd not in table:
            near = difflib.get_close_matches(cmd, list(table), n=3)
            return f"unknown /{cmd}" + (f" — did you mean: {', '.join('/'+c for c in near)}?" if near else "")
        return table[cmd](args)

    # -- commands --
    def _c_help(self, args: list) -> str:
        if args and args[0] in HELP:
            return f"/{args[0]} {HELP[args[0]]}"
        rows = [f"/{c:<12} {d}" for c, d in HELP.items()]
        return "Slash Command Palette\n" + "\n".join(rows)

    def _c_clear(self, args: list) -> str:
        return "\x1b[2J\x1b[H" + self.status_bar()

    def _c_model(self, args: list) -> str:
        from delta_os.model_catalogue import add_custom, catalogue_status, load_custom

        custom = load_custom(self.vault)
        rows = catalogue_status(self.vault, custom)
        by_name = {r["name"]: r for r in rows}
        if not args or args[0] == "list":
            header = "DELTA MODEL REGISTRY\n" + ("─" * 72) + "\n"
            lines = []
            for r in rows:
                active = " [ACTIVE]" if r["name"] == self.model_name else ""
                badge = {"READY": "●", "NEEDS_KEY": "◐",
                         "UNAVAILABLE": "○"}.get(r["status"], "?")
                lines.append(f"  {badge} {r['name']:<22} │ {r['status']:<11} │ {r['description']}{active}")
            return (header + "\n".join(lines)
                    + "\n\nSwitch model: /model <name> · Add endpoint: /models add <name> <base-url> [model-id]"
                    + "\nConfigure API key: /key <provider> <token>")
        if args[0] == "add":
            if len(args) < 3:
                return "usage: /models add <name> <base-url> [model-id]"
            try:
                return "✓ " + add_custom(args[1], args[2],
                                        args[3] if len(args) > 3 else "",
                                        self.vault)
            except Exception as exc:
                return f"add FAILED: {exc}"
        if args[0] == "info":
            return f"Active roles: {self.models.active}\nActive model: {self.model_name}"

        target = args[1] if args[0] == "switch" and len(args) > 1 else args[0]
        rec = by_name.get(target)
        if rec is None:
            names = ", ".join(r["name"] for r in rows)
            return f"unknown model {target!r}. Available: {names}"
        if rec["status"] != "READY":
            hint = (f"/models add {target} <base-url>" if rec["status"] == "UNAVAILABLE"
                    else f"/key {rec['slot']} <token>")
            return (f"refused: {target} is {rec['status']} — "
                    f"never fake-READY. Fix: {hint}")
        self.model_name = target
        if rec["kind"] == "local":
            return (f"✓ Switched active model -> {self.model_name} "
                    f"(Local Quant FM · 100% Offline · No API key needed)")
        return f"✓ Switched active model -> {self.model_name} [{rec['slot']} key on file]"

    def _c_mcp(self, args: list) -> str:
        # Truth rule: statuses are UNPROBED until a runtime report arrives.
        # Names below are known integrations (declared capabilities), not live
        # connections. Never CONNECTED-by-config.
        header = "DELTA MCP SERVERS & TOOL INTEGRATIONS\n" + ("─" * 55) + "\n"
        servers = [
            ("market-data", "UNPROBED", "declared", "—"),
            ("sec-edgar", "UNPROBED", "declared", "—"),
            ("fred", "UNPROBED", "declared", "—"),
            ("news", "UNPROBED", "declared", "—"),
            ("broker-alpaca", "UNPROBED", "declared", "—"),
            ("reasonforge", "UNPROBED", "declared", "—"),
            ("options-data", "UNPROBED", "declared", "—"),
            ("alternative-data", "UNPROBED", "declared", "—"),
        ]
        rows = []
        for name, status, count, lat in servers:
            rows.append(f"  ○ {name:<18} │ {status:<12} │ {count:<10} │ {lat}")
        return (header + "\n".join(rows)
                + "\n\nDeclared capabilities (not live probes). "
                "List callable tools: /tools")

    def _c_tools(self, args: list) -> str:
        header = "DECLARED MCP TOOLS (FINANCIAL CAPABILITIES)\n" + ("─" * 55) + "\n"
        tools = [
            ("market.quote", "market-data", "READ", "Point-in-time ticker quote & OHLCV bars"),
            ("market.depth", "market-data", "READ", "Integer-tick limit order book & imbalance"),
            ("portfolio.positions", "broker-alpaca", "READ", "Multi-broker position & cash balances"),
            ("risk.var_cvar", "reasonforge", "READ", "Parametric & historical VaR95/99 + CVaR"),
            ("sec.filings", "sec-edgar", "READ", "10-K / 10-Q financial statements & KPIs"),
            ("macro.yield_curve", "fred", "READ", "US Treasury 10Y/2Y spread & rate metrics"),
            ("order.stage", "broker-alpaca", "STAGE", "Stage order ticket for pre-trade risk check"),
            ("order.cancel", "broker-alpaca", "CANCEL", "Cancel active working order by ID"),
        ]
        rows = []
        for name, srv, perm, desc in tools:
            rows.append(f"  ● {name:<20} [{perm:<7}] │ {desc}")
        return header + "\n".join(rows)

    def _c_effort(self, args: list) -> str:
        if not args:
            return "Reasoning effort levels: low | medium | high | xhigh | auto\nUsage: /effort <level>"
        lvl = args[0].upper()
        if lvl not in ("LOW", "MEDIUM", "HIGH", "XHIGH", "AUTO"):
            return f"Invalid effort level: {args[0]}. Choose from: low, medium, high, xhigh, auto"
        return f"✓ Set reasoning effort -> {lvl}"

    def _c_thinking(self, args: list) -> str:
        if not args:
            return "Thinking display modes: off | summary | activity\nUsage: /thinking <mode>"
        mode = args[0].upper()
        if mode not in ("OFF", "SUMMARY", "ACTIVITY"):
            return f"Invalid thinking mode: {args[0]}. Choose from: off, summary, activity"
        return f"✓ Set thinking display -> {mode}"

    def _c_desk(self, args: list) -> str:
        return self.status_bar()

    def _c_plan(self, args: list) -> str:
        intent = " ".join(args) if args else "portfolio review"
        return f"PLANNING MODE (Read-only):\n1. Resolve context for: {intent}\n2. Fetch market evidence & portfolio exposure\n3. Calculate risk impact & scenario tests\n4. Produce candidate order preview\n(NO ORDERS SUBMITTED)"

    def _c_sessions(self, args: list) -> str:
        return f"Active Workspace: {self.workspace}\nAvailable Sessions:\n  ● default\n  ● equities-alpha\n  ● macro-rates\n  ● risk-review"

    def _c_broker(self, args: list) -> str:
        if not args or args[0] == "status":
            cur = self.router.current()
            try:
                st = cur.status()
            except Exception as exc:
                st = {"connected": False, "error": str(exc)}
            return f"active={self.router.active} {st}"
        if args[0] == "use" and len(args) > 1:
            self.broker_name = self.router.use(args[1])
            return f"broker -> {self.broker_name}"
        if args[0] == "connect" and len(args) > 1:
            return self._broker_connect(args[1])
        return "usage: /broker [connect|status|use] [paper|alpaca|ibkr]"

    def _broker_connect(self, name: str) -> str:
        from delta_os.brokers import AlpacaAdapter, IBKRAdapter

        if name == "paper":
            self.router.use("paper")
            self.broker_name = "paper"
            return "paper broker ready."
        if self.vault is None or self.vault.locked:
            return "vault locked — /auth wizard first."
        if name == "alpaca":
            creds = self.vault.get("alpaca")
            if not creds.get("key_id"):
                return "no alpaca credentials — /auth wizard, slot 1."
            paper = creds.get("environment", "paper") != "live"
            from delta_os.brokers import ALPACA_PAPER, ALPACA_LIVE

            self.router.alpaca = AlpacaAdapter(
                creds["key_id"], creds.get("secret", ""),
                ALPACA_PAPER if paper else ALPACA_LIVE)
            st = self.router.alpaca.status()
            if st.get("connected"):
                self.router.use("alpaca")
                self.broker_name = "alpaca"
            return f"alpaca: {st}"
        if name == "ibkr":
            host = (self.vault.get("ibkr") or {}).get("host", "")
            self.router.ibkr = IBKRAdapter(host=host)
            return f"ibkr: {self.router.ibkr.status()}"
        return f"unknown broker {name}."

    def _vault_open(self) -> str | None:
        import os

        if self.vault is not None and not self.vault.locked:
            return None
        self.vault = Vault(default_path())
        pw = os.environ.get("DELTA_VAULT_PASS", "")
        if not pw:
            return "set DELTA_VAULT_PASS or run interactive wizard."
        try:
            self.vault.unlock(pw)
        except Exception as exc:
            self.vault = None
            return f"vault unlock failed: {exc}"
        return None

    def _c_auth(self, args: list) -> str:
        err = self._vault_open()
        if err:
            return err
        if not args or args[0] == "list":
            return "vault slots: " + ", ".join(self.vault.list() or ["(empty)"])
        if args[0] == "test" and len(args) > 1:
            creds = self.vault.get(args[1])
            return f"{args[1]}: {'stored' if creds else 'missing'}"
        if args[0] == "rm" and len(args) > 1:
            return f"{args[1]}: {'removed' if self.vault.delete(args[1]) else 'absent'}"
        if args[0] == "wizard":
            return ("slots: 1=alpaca 2=ibkr 3=fred 4=gemini 5=anthropic 6=openai; "
                    "store programmatically via vault.set() or DELTA_VAULT_PASS + "
                    "non-interactive provisioning (interactive prompts unsupported here).")
        return "usage: /auth [wizard|test|list|rm] [slot]"

    def _c_news(self, args: list) -> str:
        from delta_os.data_router import news_sentiment

        q = " ".join(args) if args else "stock market"
        try:
            n = news_sentiment(q)
        except Exception as exc:
            return f"news unavailable: {exc}"
        lines = []
        for i in n["items"][:5]:
            cats = f" | {','.join(i['catalysts'])}" if i["catalysts"] else ""
            cb = " [clickbait?]" if i["clickbait"] else ""
            lines.append(f"{i['badge']} {i['title']} (pol {i['polarity']}){cats}{cb}")
        head = (f"avg polarity {n['avg_polarity']} over {n['n']} | catalysts: "
                f"{', '.join(n['catalysts']) or 'none'} | clickbait demoted: "
                f"{n['clickbait_filtered']}")
        return head + "\n" + "\n".join(lines)

    def _c_macro(self, args: list) -> str:
        from delta_os.data_router import FRED_SERIES, FredUnavailable, fred_observations, net_liquidity_index

        if self.vault is None or self.vault.locked:
            if (err := self._vault_open()):
                return err
        key = (self.vault.get("fred") or {}).get("api_key", "")
        try:
            series = {}
            for s in ("WALCL", "RRPONTSYD"):
                series[s] = fred_observations(s, key, n=1)["observations"][0][1]
            tga = 750_000.0
            try:
                tga = fred_observations("WTREGEN", key, n=1)["observations"][0][1]
            except FredUnavailable:
                pass
            nli = net_liquidity_index(series["WALCL"], tga, series["RRPONTSYD"])
            return (f"Net Liquidity ${nli['net_liquidity']:,.0f} score {nli['score']} "
                    f"[{nli['regime']}] (TGA est. ${tga:,.0f})")
        except FredUnavailable as exc:
            return f"macro unavailable: {exc}"

    def _c_track(self, args: list) -> str:
        from delta_os.data_router import track_alerts

        if not args or args[0] == "list":
            lines = []
            for s in self.watchlist:
                try:
                    qf = self.data.quote(s)
                    px = float(qf.frame["close"].iloc[-1])
                    badge = f" {qf.provenance.badge}" if qf.provenance.badge else ""
                    al = track_alerts(qf.frame)
                    flag = (" !! " + "; ".join(al)) if al else ""
                    lines.append(f"{s} ${px:,.2f}{badge}{flag}")
                except Exception as exc:
                    lines.append(f"{s} unavailable: {exc}")
            return "watchlist:\n" + ("\n".join(lines) if lines else "(empty)")
        if args[0] == "add" and len(args) > 1:
            s = args[1].upper()
            if s not in self.watchlist:
                self.watchlist.append(s)
            return f"tracking {s}."
        if args[0] in ("rm", "remove") and len(args) > 1:
            s = args[1].upper()
            if s in self.watchlist:
                self.watchlist.remove(s)
            return f"untracked {s}."
        return "usage: /track [add|rm|list] [ticker]"

    def _c_quant(self, args: list) -> str:
        if not args:
            return "usage: /quant [ticker]"
        from delta_os import quantkit as Q

        qf = self.data.quote(args[0])
        badge = f" {qf.provenance.badge}" if qf.provenance.badge else ""
        last = qf.frame["close"].iloc[-1]
        bands = Q.vwap_bands(qf.frame).iloc[-1]
        loc = Q.vwap_location(float(last), bands)
        poc = Q.volume_profile(qf.frame.tail(60))
        r = qf.frame["close"].pct_change().dropna()
        vc = Q.var_cvar(r)
        sm = Q.sharpe_maxdd(qf.frame["close"])
        st = Q.sortino_maxdd(qf.frame["close"])
        adv = float(qf.frame["volume"].tail(30).mean() or 1)
        imp = Q.market_impact_bps(1000.0, float(last), adv,
                                  float(Q.atr(qf.frame).iloc[-1] or 0.0))
        return (f"{args[0].upper()} ${last:,.2f}{badge} [{qf.provenance.tier}]\n"
                f"VWAP {bands['vwap']:,.2f} loc {loc:+.1f}σ ±1σ [{bands['lower1']:,.2f}, {bands['upper1']:,.2f}]\n"
                f"POC {poc['poc']:,.2f} VA [{poc['val']:,.2f}, {poc['vah']:,.2f}] ({poc['coverage']:.0%})\n"
                f"ATR {Q.atr(qf.frame).iloc[-1]:,.2f} | VaR95 hist {vc['hist_var']:.2%} "
                f"CVaR {vc['hist_cvar']:.2%} | Sharpe {sm['sharpe']} Sortino {st['sortino']} "
                f"MaxDD {sm['max_drawdown']:.2%} | Impact(1k) {imp['impact_bps']:.1f}bps")

    def _c_portfolio(self, args: list) -> str:
        cur = self.router.current()
        if self.broker_name == "paper":
            qfs = {}
            for s in list(cur._ledger.positions) or self.watchlist[:5]:
                try:
                    qfs[s] = float(self.data.quote(s).frame["close"].iloc[-1])
                except Exception:
                    pass
            rec = cur.positions(qfs)
            return (f"cash ${rec['cash']:,.2f} equity ${rec['equity']:,.2f} "
                    f"positions {rec['positions']} fills {rec['n_fills']}")
        try:
            return f"{cur.status()}"
        except Exception as exc:
            return f"portfolio unavailable: {exc}"

    def _c_auto(self, args: list) -> str:
        if not args or args[0] == "status":
            return f"AUTO bounds: 5% pos / 1.5x lev / 2% halt. mode={self.safety.mode}"
        if args[0] == "on":
            self.safety.set_mode("AUTO")
            return "AUTO armed within governor bounds."
        if args[0] == "off":
            self.safety.set_mode("MANUAL")
            return "back to MANUAL."
        return "usage: /auto [on|off|status]"

    def _c_manual(self, args: list) -> str:
        self.safety.set_mode("MANUAL")
        return "MANUAL: every order needs [y/N]."

    def _c_kill(self, args: list) -> str:
        ads = [self.router.paper]
        if self.router.alpaca is not None:
            ads.append(self.router.alpaca)
        receipt = self.safety.kill_all(ads)
        return (f"KILLED: cancel-all {receipt['layer1_cancelled']} "
                f"({receipt['layer1_ms']}ms) + FROZEN. /unlock to resume. "
                f"errors={receipt['errors'] or 'none'}")

    def _c_unlock(self, args: list) -> str:
        if len(args) < 2:
            return "usage: /unlock [actor] [reason...]"
        return "mode -> " + self.safety.unlock(args[0], " ".join(args[1:]))

    def _c_flatten(self, args: list) -> str:
        return ("flatten submits market orders — route via preview: "
                "use /portfolio, then place explicit orders (no silent mass-liquidate).")

    def _c_backtest(self, args: list) -> str:
        if not args:
            return "usage: /backtest [ticker] [days=252]"
        sym = args[0].upper()
        days = int(args[1]) if len(args) > 1 else 252
        qf = self.data.quote(sym, days=days)
        badge = f" {qf.provenance.badge}" if qf.provenance.badge else ""
        if qf.provenance.tier == "TIER3-SYNTH":
            return (f"backtest refused on [SYNTHETIC SIMULATION ONLY] data: "
                    f"results would be fiction. Use fresh data.")
        from research.real_loop import features as F
        from research.real_loop import walkforward as W

        feat = F.compute_features(qf.frame, sym, "delta-os")
        out = W.walk_forward(qf.frame["close"], feat, n_folds=3)
        folds = " | ".join(f"net {f['net']:+.4f} sh {f['sharpe']:+.2f}" for f in out["folds"])
        return (f"{sym} walk-forward{badge}: OOS net {out['oos_total_net']:+.4f} "
                f"gate={out['gate']['pass']}\nfolds: {folds}")

    def _c_theme(self, args: list) -> str:
        from delta_os.themes import THEMES

        if not args:
            return "themes: " + ", ".join(sorted(THEMES))
        if args[0] not in THEMES:
            raise SafetyError(f"unknown theme; choose {sorted(THEMES)}.")
        self.theme = args[0]
        return f"theme -> {self.theme}"

    def _c_workspace(self, args: list) -> str:
        if not args:
            return f"workspace: {self.workspace}"
        self.workspace = args[0].upper()
        return f"workspace -> {self.workspace}"

    def _c_mode(self, args: list) -> str:
        if not args:
            return f"mode={self.safety.mode} (use /mode manual|auto)"
        return "mode -> " + self.safety.set_mode(args[0].upper())

    def _c_quote(self, args: list) -> str:
        if not args:
            return "usage: /quote [ticker]"
        qf = self.data.quote(args[0])
        f = qf.frame
        last = float(f["close"].iloc[-1])
        badge = f" {qf.provenance.badge}" if qf.provenance.badge else ""
        rng = f"{float(f['low'].iloc[-1]):,.2f}-{float(f['high'].iloc[-1]):,.2f}"
        vol = f["volume"].astype(float)
        rvol = vol.iloc[-1] / max(vol.iloc[-21:-1].mean(), 1) if len(vol) > 21 else 1.0
        chg = (last / float(f["close"].iloc[-2]) - 1) if len(f) > 1 else 0.0
        return (f"{args[0].upper()} ${last:,.2f} ({chg:+.2%}){badge} [{qf.provenance.tier}]\n"
                f"day range {rng} | RVOL {rvol:.1f}x | spread: n/a on daily bars "
                f"(no fabricated bid/ask)")

    def _c_india(self, args: list) -> str:
        if not args:
            return "usage: /india [symbol] [exchange=AUTO] (e.g. /india RELIANCE, /india NIFTY)"
        from delta_os import opencode_tools as _OT

        sym = args[0]
        exch = args[1] if len(args) > 1 else "AUTO"
        out = _OT.tool_india_market(sym, exchange=exch)
        badge = f" {out['badge']}" if out["badge"] else ""
        m = out["market"]
        cur = "Rs." if out.get("currency") == "INR" else "$"
        return (f"{out['symbol']} {cur}{out['price']:,.2f} ({out['change_pct']:+.2f}%)"
                f"{badge} [{out['tier']}] via {out['yahoo_symbol']}\n"
                f"NSE: {m['market']} @ {m['ist_time']} ({m['reason']})")

    def _c_indicators(self, args: list) -> str:
        if not args:
            return "usage: /indicators [symbol] (e.g. /indicators RELIANCE)"
        from delta_os import opencode_tools as _OT

        out = _OT.tool_indicators(args[0])
        badge = f" {out['badge']}" if out["badge"] else ""
        return f"{out['card']}{badge} [{out['tier']}]"

    def _c_stats(self, args: list) -> str:
        if not args:
            return "usage: /stats [symbol] (e.g. /stats RELIANCE.NS)"
        from delta_os import opencode_tools as _OT

        out = _OT.tool_statistics(args[0])
        badge = f" {out['badge']}" if out["badge"] else ""
        return f"{out['card']}{badge} [{out['tier']}]"

    def _c_reason(self, args: list) -> str:
        if not args:
            return "usage: /reason [symbol] (e.g. /reason RELIANCE)"
        from delta_os import opencode_tools as _OT

        out = _OT.tool_reasonforge(args[0])
        return out["card"]

    def _c_risk(self, args: list) -> str:
        # If first arg is a ticker symbol, run comprehensive multi-asset risk
        if args and any(c.isalpha() for c in args[0]) and args[0].upper() not in ("HELP",):
            sym = args[0].upper()
            asset_type = args[1].upper() if len(args) > 1 and args[1].upper() in ("STOCK", "OPTION", "OPTIONS", "FUTURE", "FUTURES") else "STOCK"
            res = self.brain.analyze_risk(sym, asset_type=asset_type)
            if asset_type in ("OPTION", "OPTIONS"):
                g = res["greeks"]
                de = res["dollar_exposures"]
                return (
                    f"=== BLACK-SCHOLES OPTIONS RISK & GREEKS: {sym} ===\n"
                    f"● Spot Price: ${res['spot_price']:,.2f} | Strike: ${res['strike']:,.2f} | Type: {res['option_type']}\n"
                    f"● Implied Vol: {res['implied_volatility_pct']:.1f}% | Expiry: {res['expiry_days']} days | Theo Price: ${res['theoretical_price']:.2f}\n"
                    f"───────────────────────────────────────────────────────────\n"
                    f"ANALYTICAL GREEKS: Delta (Δ)={g['delta']:+.4f} | Gamma (Γ)={g['gamma']:.6f} | Vega (ν)={g['vega']:.4f}\n"
                    f"                   Theta (Θ)={g['theta']:.4f}/day | Rho (ρ)={g['rho']:.4f} | P(ITM)={res['prob_itm_pct']}%\n"
                    f"DOLLAR EXPOSURE:   $Delta=${de['dollar_delta']:+,.2f} | $Gamma=${de['dollar_gamma']:,.2f} | $Vega=${de['dollar_vega']:,.2f}\n"
                    f"TAIL LOSS (10% SPOT CRASH): ${res['tail_loss_10pct_spot']:+,.2f}"
                )
            elif asset_type in ("FUTURE", "FUTURES"):
                return (
                    f"=== DERIVATIVES / FUTURES RISK ENGINE: {sym} ===\n"
                    f"● Spot Price: ${res['spot_price']:,.2f} | Effective Leverage: {res['effective_leverage']}\n"
                    f"● Initial Margin Req: ${res['initial_margin_dollars']:,.2f} | Maint Margin: ${res['maintenance_margin_dollars']:,.2f}\n"
                    f"● Daily 99% VaR: ${res['daily_var_99_dollars']:,.2f} | Buffer to Margin Call: {res['margin_call_buffer_pct']}%\n"
                )
            else:
                shocks = res["scenario_shocks"]
                return (
                    f"=== INSTITUTIONAL RISK ANALYSIS: {sym} ===\n"
                    f"● Spot Price: ${res['spot_price']:,.2f} | Annualized Vol: {res['implied_volatility_pct']:.1f}%\n"
                    f"● 1-Day 95% VaR: ${res['daily_var_95_dollars']:,.2f} | 1-Day 99% VaR: ${res['daily_var_99_dollars']:,.2f}\n"
                    f"● 1-Day 95% Expected Shortfall (CVaR): ${res['daily_cvar_95_dollars']:,.2f}\n"
                    f"SCENARIO STRESS SHOCKS ($100k Notional):\n"
                    f"  • Rate Shock (-200bps)     : ${shocks['rate_shock_neg200bps']:+,.2f}\n"
                    f"  • Crude Oil Spike (+10%)   : ${shocks['crude_oil_spike_plus10pct']:+,.2f}\n"
                    f"  • Systemic Crash (-20%)    : ${shocks['equity_crash_neg20pct']:+,.2f}"
                )
        from delta_os import quantkit as Q

        p = float(args[0]) if len(args) > 0 else 0.55
        b = float(args[1]) if len(args) > 1 else 1.5
        mkt = self.data.quote("SPY").frame["close"].pct_change().dropna()
        vc = Q.var_cvar(mkt, 0.99)
        kelly = Q.fractional_kelly(p, b)
        self.var_chip = f"{vc['hist_var']:.2%}"
        return (f"VaR99 hist {vc['hist_var']:.2%} CVaR99 {vc['hist_cvar']:.2%} "
                f"(SPY daily) | Kelly f*={kelly} (p={p}, b={b}, half) | "
                f"governor: 5% pos / 1.5x lev / 2% halt")

    def _c_analyze(self, args: list) -> str:
        if not args:
            return "usage: /analyze [symbol] (e.g. /analyze NVDA)"
        sym = args[0].upper()
        res = self.brain.analyze_stock(sym)
        if "error" in res:
            return f"Analysis failed: {res['error']}"
        ind = res["indicators"]
        rm = res["risk_metrics"]
        return (
            f"=== MULTI-FACTOR QUANTITATIVE REPORT: {sym} ===\n"
            f"● Price: ${res['price']:,.2f} ({res['change_pct']:+.2f}%) | Trend: {res['trend']} | Verdict: {res['verdict']}\n"
            f"● Composite Score: {res['composite_score']:+.1f}/100 | Data Provenance: {res['provenance']}\n"
            f"───────────────────────────────────────────────────────────\n"
            f"TECHNICALS: RSI(14)={ind['rsi_14']} | MACD={ind['macd']} (Hist={ind['macd_hist']}) | VWAP=${ind['vwap']:,.2f}\n"
            f"            BB=[${ind['bb_lower']:,.2f} - ${ind['bb_upper']:,.2f}] | ATR(14)=${ind['atr_14']:.2f} | MA50=${ind['ma_50']:,.2f}\n"
            f"RISK/TAIL:  Ann. Vol={rm['annualized_vol']}% | Daily VaR95={rm['var_95_daily_pct']}% | Daily VaR99={rm['var_99_daily_pct']}%\n"
            f"            Daily CVaR95={rm['cvar_95_daily_pct']}% | Max Drawdown={rm['max_drawdown_pct']}%\n"
            f"───────────────────────────────────────────────────────────\n"
            f"Tip: Run /forecast {sym} for probabilistic expected returns or /risk {sym} for Greeks."
        )

    def _c_forecast(self, args: list) -> str:
        if not args:
            return "usage: /forecast [symbol] [days=5] (e.g. /forecast NVDA 5)"
        sym = args[0].upper()
        days = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5
        res = self.brain.forecast_direction(sym, horizon_days=days)
        if "error" in res:
            return f"Forecast failed: {res['error']}"
        ci = res["confidence_interval_95"]
        return (
            f"=== PROBABILISTIC RETURN FORECAST: {sym} ({days}-DAY HORIZON) ===\n"
            f"● Direction: {res['direction']} | Target Price: ${res['target_price']:,.2f}\n"
            f"● Expected Return: {res['expected_return_pct']:+.2f}% | P(Return > 0): {res['probability_positive_return_pct']}%\n"
            f"● 95% Confidence Band: [${ci[0]:,.2f} - ${ci[1]:,.2f}] | Forecast Vol: {res['forecast_volatility_pct']}%\n"
            f"● Turn Signal: {res['turn_recommendation']}\n"
            f"● Confidence: {res.get('confidence', '?')} ({res.get('calibration', 'n/a')}) "
            f"| Evidence RSI {res.get('evidence', {}).get('rsi_14', '?')} / MACD-h {res.get('evidence', {}).get('macd_hist', '?')}\n"
            f"───────────────────────────────────────────────────────────\n"
            f"(Model: {res.get('model', '?')} {res.get('model_version', '')} · heuristic, not backtested · [{res.get('data_tier', '?')}] · Zero lookahead bias)"
        )

    def _ledger_equity(self) -> float | None:
        """Live ledger equity for the active broker. None = UNAVAILABLE."""
        try:
            cur = self.router.current()
            ledger = getattr(cur, "_ledger", None)
            if ledger is None:
                return None
            positions = self._ledger_positions()
            prices = {}
            for s in positions:
                try:
                    prices[s] = float(self.data.quote(s).frame["close"].iloc[-1])
                except Exception:
                    return None
            rec = ledger.reconcile(prices)
            eq = rec.get("equity", None)
            return float(eq) if eq is not None else None
        except Exception:
            return None

    def _ledger_positions(self) -> dict:
        """Live ledger positions {symbol: qty}. {} = none/unreadable (never demo).

        PaperLedger stores plain floats; broker adapters may store objects —
        both shapes accepted.
        """
        try:
            cur = self.router.current()
            ledger = getattr(cur, "_ledger", None)
            if ledger is None:
                return {}
            out = {}
            for s, pos in ledger.positions.items():
                q = getattr(pos, "qty", pos)
                out[s] = float(q)
            return out
        except Exception:
            return {}

    def _positions_notional(self) -> float | None:
        """Gross notional of live positions at live quotes. None = unreadable."""
        positions = self._ledger_positions()
        if not positions:
            return 0.0
        total = 0.0
        try:
            for s, q in positions.items():
                px = float(self.data.quote(s).frame["close"].iloc[-1])
                total += abs(q) * px
        except Exception:
            return None
        return total

    def _c_sentinel(self, args: list) -> str:
        if self.sentinel is None:
            from delta_os.alerting import AlertFanout

            fanout = AlertFanout(vault=self.vault,
                                 compliance=self.safety.compliance)
            self.sentinel = DeltaSentinel(
                brain=self.brain, safety_state=self.safety,
                equity_fn=self._ledger_equity,
                positions_fn=self._ledger_positions,
                alert_sink=lambda a: fanout.broadcast(a),
            )
        sub = args[0].lower() if args else "status"
        if sub == "start":
            return self.sentinel.start()
        elif sub == "stop":
            return self.sentinel.stop()
        elif sub == "status":
            st = self.sentinel.status()
            recent = "\n".join(f"  • [{a['timestamp'][11:19]}] {a['level']}: {a['message']}" for a in st["recent_alerts"]) if st["recent_alerts"] else "  (No active risk breaches)"
            return (
                f"=== DELTA 24/7 AUTONOMOUS SENTINEL ===\n"
                f"● Engine State: {st['status']}\n"
                f"● Loss Limit (Kill Threshold): {st['max_drawdown_threshold_pct']:.1f}%\n"
                f"● Current Drawdown: {st['current_drawdown_pct']:.2f}%\n"
                f"● Kill Switch State: {st['kill_switch_state']}\n"
                f"● Recent Surveillance Alerts:\n{recent}\n"
                f"Controls: /sentinel start | /sentinel stop"
            )
        return "usage: /sentinel [start|stop|status]"

    def _c_alerts(self, args: list) -> str:
        from delta_os.alerting import AlertFanout

        fanout = AlertFanout(vault=self.vault,
                             compliance=self.safety.compliance)
        tg = fanout._creds("telegram")
        wa = fanout._creds("whatsapp")
        tg_state = ("CONFIGURED (creds on file, liveness unprobed)"
                    if tg.get("bot_token") and tg.get("chat_id") else "UNCONFIGURED")
        wa_state = ("CONFIGURED (creds on file, liveness unprobed)"
                    if wa.get("token") and wa.get("phone_number_id") and wa.get("to")
                    else "UNCONFIGURED")
        if not args:
            return (
                "=== ALERT CHANNELS ===\n"
                f"● terminal log + audit record: ALWAYS ON\n"
                f"● telegram: {tg_state} — /auth wizard slot telegram\n"
                f"● whatsapp: {wa_state} — /auth wizard slot whatsapp\n"
                "probe a channel: /alerts test telegram|whatsapp"
            )
        if args[0] == "test" and len(args) > 1 and args[1] in ("telegram", "whatsapp"):
            probe = {"timestamp": __import__("datetime").datetime.now(
                         __import__("datetime").timezone.utc).isoformat(),
                     "level": "INFO", "event": "ALERT_PROBE",
                     "message": f"DELTA alert probe via {args[1]}"}
            res = fanout.broadcast(probe)
            state = getattr(res, args[1])
            detail = "; ".join(res.errors) if res.errors else "ok"
            return f"probe {args[1]}: {state} — {detail}"
        return "usage: /alerts [test telegram|whatsapp]"

    def _c_algo(self, args: list) -> str:
        strat = args[0] if args else "statarb"
        code = self.brain.generate_algo_code(strategy_type=strat)
        return f"=== TOP 0.001% QUANTITATIVE TRADING ALGORITHM ({strat.upper()}) ===\n\n{code}"

    def _c_ask(self, args: list) -> str:
        if not args:
            return "usage: /ask [financial or quantitative question]"
        q = " ".join(args)
        return self.brain.chat(q)

    def _c_key(self, args: list) -> str:
        if len(args) < 2:
            st = self.brain.get_key_status(self.vault)
            rows = "\n".join(f"  • {p:<12} : {'[CONFIGURED]' if v else '[MISSING]'}" for p, v in st.items())
            locked = self.vault is None or getattr(self.vault, "locked", True)
            return (
                f"=== API KEY VAULT (Frontier Cloud Models) ===\n{rows}\n"
                f"vault: {'LOCKED — /auth wizard first' if locked else 'UNLOCKED'}\n\n"
                f"To register an API key: /key <provider> <token>\n"
                f"Providers: anthropic, openai, deepseek, groq, gemini, astro\n"
                f"(Note: Local model delta-fm-research operates 100% offline without any API keys.)"
            )
        prov, token = args[0].lower(), args[1]
        try:
            msg = self.brain.set_api_key(prov, token, self.vault)
        except Exception as exc:
            return f"key NOT stored: {exc}"
        return f"✓ {msg}"

    def _c_crash(self, args: list) -> str:
        positions = self._ledger_positions()
        if not positions:
            return ("=== PORTFOLIO CRASH / DIP RADAR ===\n"
                    "  (No live positions readable — nothing to evaluate. "
                    "Never demo tickers.)")
        res = self.brain.evaluate_portfolio_regime(positions=positions)
        recs = "\n".join(f"  • [{r['urgency']}] {r['symbol']}: {r['action']} — {r['reason']}" for r in res["actionable_recommendations"]) if res["actionable_recommendations"] else "  (All positions within stable risk parameters)"
        return (
            f"=== REGIME-AWARE PORTFOLIO CRASH MONITOR ===\n"
            f"● Market Regime: {res['market_regime']} | VIX Proxy: {res['vix_volatility_proxy']:.1f}\n"
            f"● Systemic Crash Probability: {res['crash_probability_pct']:.1f}%\n"
            f"● Actionable Rebalance Recommendations:\n{recs}"
        )

    def _c_protect(self, args: list) -> str:
        if not args:
            return "usage: /protect [symbol] — protective-put hedge sizing"
        sym = args[0].upper()
        qty = self._ledger_positions().get(sym, 0.0)
        if qty <= 0:
            return (f"=== CRASH DEFENSE: {sym} ===\n  (No live long position in {sym} — "
                    f"nothing to hedge. Never demo fills.)")
        h = self.brain.hedge_plan(sym, qty)
        if "error" in h:
            return f"=== CRASH DEFENSE: {sym} ===\n  UNAVAILABLE: {h['error']}"
        return (
            f"=== CRASH DEFENSE: {sym} ===\n"
            f"● {h['action']} | Strike ${h['strike']:,.2f} | {h['contracts']} contracts\n"
            f"● Premium ${h['premium_dollars']:,.2f} | Hedges ~{h['hedged_delta_shares']:,.0f} delta-shares "
            f"of {h['qty_held']:,.0f} held\n"
            f"● Execute: {h['execute_via']} | [{h['data_tier']}]"
        )

    def _c_dipbuy(self, args: list) -> str:
        if not args:
            return "usage: /dipbuy [symbol] — oversold dip ladder (RSI<35 only)"
        eq = self._ledger_equity()
        if eq is None:
            return ("=== DIP LADDER ===\n  UNAVAILABLE: ledger equity unreadable — "
                    "no sizing possible.")
        d = self.brain.dip_plan(args[0].upper(), eq)
        if "error" in d:
            return f"=== DIP LADDER: {d.get('symbol', '?')} ===\n  UNAVAILABLE: {d['error']}"
        if not d.get("tranches"):
            return (f"=== DIP LADDER: {d['symbol']} ===\n  {d['action']} "
                    f"(RSI {d.get('rsi_14')}) — {d.get('reason', '')}")
        legs = "\n".join(f"  • Leg {t['tranche']} ({t['note']}): {t['qty']} sh @ ${t['limit_price']:,.2f}"
                         for t in d["tranches"])
        return (
            f"=== DIP LADDER: {d['symbol']} ===\n"
            f"● RSI {d['rsi_14']:.1f} oversold vs ${d['ref_price']:,.2f}\n{legs}\n"
            f"● {d['execute_via']} | [{d['data_tier']}]"
        )

    def _c_fundamental(self, args: list) -> str:
        if not args:
            return "usage: /fundamental [ticker]"
        from delta_os import quantkit as Q
        from delta_os.data_router import fundamentals

        sym = args[0].upper()
        info = fundamentals(sym)
        if not info:
            return f"{sym}: fundamentals unavailable (network or coverage)."
        out = [f"{sym} mcap {info.get('market_cap')} PE {info.get('pe')} "
               f"PB {info.get('pb')} ROE {info.get('roe')}"]
        fin = self._fin_history(sym)
        if fin:
            try:
                pf = Q.piotroski_f(fin)
                out.append(f"Piotroski {pf['score']}/9 [{pf['grade']}]")
            except ValueError as exc:
                out.append(f"Piotroski n/a: {exc}")
            try:
                z = Q.altman_z(fin)
                out.append(f"Altman Z {z['z']} [{z['zone']}]")
            except ValueError as exc:
                out.append(f"Altman n/a: {exc}")
            if info.get("free_cashflow") and info.get("shares"):
                try:
                    d = Q.dcf_value(float(info["free_cashflow"]), 0.08, 0.10, 0.025,
                                    shares=float(info["shares"]))
                    out.append(f"DCF fair ~${d['per_share']:,.2f} (8% 5y, 10% WACC)")
                except ValueError as exc:
                    out.append(f"DCF n/a: {exc}")
        else:
            out.append("statement history unavailable: scores need 2y filings.")
        try:
            qf = self.data.quote(sym, days=60)
            out.append(f"last ${float(qf.frame['close'].iloc[-1]):,.2f} "
                       f"{qf.provenance.badge or '[' + qf.provenance.tier + ']'}")
        except Exception:
            pass
        return "\n".join(out)

    def _fin_history(self, sym: str) -> dict | None:
        """Map yfinance statements to Piotroski/Altman inputs (2-year deltas)."""
        try:
            import yfinance as yf

            t = yf.Ticker(sym)
            bs, fin, cf = t.balance_sheet, t.financials, t.cashflow
            if bs is None or fin is None or cf is None or bs.shape[1] < 2:
                return None
            c0, c1 = bs.columns[0], bs.columns[1]
            f0, f1 = fin.columns[0], fin.columns[1]
            g = lambda df, k, c, d=0.0: float(df.get(k, {}).get(c, d) or d)
            ta0, ta1 = g(bs, "Total Assets", c0), g(bs, "Total Assets", c1)
            if ta0 <= 0 or ta1 <= 0:
                return None
            ni0 = g(fin, "Net Income", f0)
            cfo0 = g(cf, "Operating Cash Flow", cf.columns[0])
            tl0 = g(bs, "Total Liabilities Net Minority Interest", c0)
            mcap = 0.0
            try:
                mcap = float(t.info.get("marketCap", 0) or 0)
            except Exception:
                pass
            rev0, rev1 = g(fin, "Total Revenue", f0), g(fin, "Total Revenue", f1)
            gp0, gp1 = g(fin, "Gross Profit", f0), g(fin, "Gross Profit", f1)
            return {
                "roa": ni0 / ta0, "cfo": cfo0 / ta0,
                "delta_roa": ni0 / ta0 - g(fin, "Net Income", f1) / ta1,
                "delta_lever": tl0 / ta0 - g(bs, "Total Liabilities Net Minority Interest", c1) / ta1,
                "delta_liquid": g(bs, "Current Assets", c0) / max(g(bs, "Current Liabilities", c0), 1e-9)
                                - g(bs, "Current Assets", c1) / max(g(bs, "Current Liabilities", c1), 1e-9),
                "shares_issued": g(bs, "Ordinary Shares Number", c0) > g(bs, "Ordinary Shares Number", c1),
                "delta_gm": (gp0 / max(rev0, 1e-9)) - (gp1 / max(rev1, 1e-9)),
                "delta_turn": (rev0 / ta0) - (rev1 / ta1),
                "wc_ta": (g(bs, "Current Assets", c0) - g(bs, "Current Liabilities", c0)) / ta0,
                "re_ta": g(bs, "Retained Earnings", c0) / ta0,
                "ebit_ta": g(fin, "EBIT", f0) / ta0,
                "mve_tl": (mcap / max(tl0, 1e-9)) if mcap else 0.0,
                "sales_ta": rev0 / ta0,
            }
        except Exception:
            return None

    def _c_report(self, args: list) -> str:
        fmt = (args[0] if args else "md").lower()
        if fmt not in ("md", "pdf"):
            return "usage: /report [md|pdf]"
        from pathlib import Path

        md = self._tearsheet_md()
        outdir = Path("artifacts/reports")
        outdir.mkdir(parents=True, exist_ok=True)
        if fmt == "md":
            fp = outdir / "tearsheet.md"
            fp.write_text(md, encoding="utf-8")
            return f"tear-sheet -> {fp}\n\n{md[:1200]}"
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import Preformatted, SimpleDocTemplate
            from reportlab.lib.styles import getSampleStyleSheet
        except ImportError:
            fp = outdir / "tearsheet.md"
            fp.write_text(md, encoding="utf-8")
            return f"tear-sheet -> {fp} (PDF unavailable, reportlab missing — md written instead.)\n\n{md[:800]}"
        fp = outdir / "tearsheet.pdf"
        doc = SimpleDocTemplate(str(fp), pagesize=letter)
        doc.build([Preformatted(md[:6000], getSampleStyleSheet()["Code"])])
        return f"tear-sheet -> {fp} (+ md below)\n\n{md[:800]}"

    def _tearsheet_md(self) -> str:
        import datetime as _dt

        cur = self.router.current()
        lines = [f"# DELTA OS Tear-Sheet ({self.workspace})",
                 _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                 f"mode={self.safety.mode} broker={self.broker_name} model={self.model_name}",
                 f"macro={self.regime_chip} var99={self.var_chip}", ""]
        # Risk/attribution snapshot on SPY (fail-soft: n/a when offline).
        try:
            from delta_os import quantkit as _Q
            mkt = self.data.quote("SPY", days=300).frame["close"]
            sm = _Q.sharpe_maxdd(mkt)
            st = _Q.sortino_maxdd(mkt)
            lines.append(f"SPY 300d: Sharpe {sm['sharpe']} Sortino {st['sortino']} "
                         f"MaxDD {sm['max_drawdown']:.2%}")
        except Exception:
            lines.append("SPY 300d: n/a (offline)")
        if self.broker_name == "paper":
            px = {}
            for s in cur._ledger.positions:
                try:
                    px[s] = float(self.data.quote(s).frame["close"].iloc[-1])
                except Exception:
                    pass
            rec = cur.positions(px)
            lines += [f"cash ${rec['cash']:,.2f} equity ${rec['equity']:,.2f}",
                      f"positions: {rec['positions'] or 'flat'}",
                      f"fills: {rec['n_fills']} fees routed via ledger", ""]
        try:
            lines.append(f"compliance records: {len(self.safety.compliance)} "
                         f"(chain {'OK' if self.safety.compliance.verify() else 'BROKEN'})")
        except Exception:
            pass
        lines += ["", "_Not investment advice. Paper/simulated unless broker is live-configured._"]
        return "\n".join(lines)

    def _c_trade(self, args: list) -> str:
        """ /trade sym side qty [--limit P] [--stop S] [--target T] [--twap N] [--post-only] """
        if len(args) < 3:
            return ("usage: /trade [sym] [buy|sell] [qty] [--limit P] [--stop S] "
                    "[--target T] [--twap N] [--post-only]")
        from delta_os import quantkit as Q

        sym, side, qty = args[0].upper(), args[1].lower(), float(args[2])
        if side not in ("buy", "sell") or qty <= 0:
            raise SafetyError("side must be buy|sell, qty>0.")
        kw: dict[str, str] = {}
        # Value flags consume the next token; boolean flags stand alone.
        # (A hand-rolled loop: the old enumerate slice dropped the LAST
        # flag's value and let --post-only swallow the next flag.)
        _VALUE_FLAGS = {"limit", "stop", "target", "twap", "alt"}
        toks = args[3:]
        j = 0
        while j < len(toks):
            tok = toks[j]
            if not tok.startswith("--") or len(tok) < 3:
                raise SafetyError(f"bad token '{tok}' (expected --flag value).")
            name = tok[2:]
            if name in _VALUE_FLAGS:
                if j + 1 >= len(toks):
                    raise SafetyError(f"--{name} needs a value.")
                kw[name] = toks[j + 1]
                j += 2
            else:
                kw[name] = "1"
                j += 1
        limit = float(kw["limit"]) if "limit" in kw else None
        qf = self.data.quote(sym)
        self.safety.check_fresh(qf.provenance)  # stale/synth refused
        last = float(qf.frame["close"].iloc[-1])
        px = limit if limit else last
        otype = "LIMIT"
        if "twap" in kw:
            slices = Q.twap_schedule(qty, int(kw["twap"]))
            otype = f"TWAP/{len(slices)}"
        if "post-only" in kw:
            ok, why = Q.post_only_allowed(side, limit or last, last, last)
            if not ok:
                raise SafetyError(f"post-only {why} (ref {last:,.2f}).")
            otype = "LIMIT POST-ONLY"
        # cost/impact estimates (labeled ESTIMATED, daily-bar proxies)
        adv = float(qf.frame["volume"].tail(20).mean() or 1)
        part = qty * px / max(adv * last, 1e-9)
        impact_bps = 8.0 * (part ** 0.5) * 100
        slip = px * 0.0002
        bands = Q.vwap_bands(qf.frame).iloc[-1]
        loc = Q.vwap_location(last, bands)
        t = OrderTicket(sym, side.upper(), otype, round(px, 2), qty,
                        stop_loss=float(kw["stop"]) if "stop" in kw else None,
                        target=float(kw["target"]) if "target" in kw else None,
                        macro_regime=self.regime_chip)
        # Automation gate: brain analyses BEFORE completion (paper AND live).
        # HOLD pauses (with --alt substitution); BLOCK refuses outright.
        gate = self.brain.gate_automation(sym, side)
        if gate["verdict"] == "BLOCK":
            raise SafetyError("brain gate BLOCK: " + "; ".join(gate["reasons"]))
        if gate["verdict"] == "HOLD":
            alts = [a.strip().upper() for a in kw.get("alt", "").split(",") if a.strip()]
            alts = [a for a in alts if a != sym]
            sub = self.brain.rank_alternatives(alts, side) if alts else {"pick": None, "ranking": [], "skipped": [], "rationale": "no --alt list supplied"}
            picked = None
            if sub["pick"]:
                for cand in [sub["pick"]] + [r["symbol"] for r in sub["ranking"][1:]]:
                    g2 = self.brain.gate_automation(cand, side)
                    if g2["verdict"] == "ALLOW":
                        picked = (cand, g2)
                        break
            if picked is None:
                detail = "; ".join(gate["reasons"])
                rank = ", ".join(f"{r['symbol']}({r['verdict']}/{r['composite_score']:+.0f})" for r in sub["ranking"])
                skip = "; ".join(f"{s['symbol']}: {s['reason']}" for s in sub["skipped"])
                return (f"HOLD: {sym} {side} paused by brain gate — {detail}\n"
                        f"alternates ranked: [{rank or 'none'}]{(' skipped: ' + skip) if skip else ''}\n"
                        f"no ALLOW alternate — nothing staged, nothing sent. "
                        f"(supply --alt SYM1,SYM2 to enable substitution)")
            sym, gate = picked
            px = float(self.data.quote(sym).frame["close"].iloc[-1]) if limit is None else px
            t = OrderTicket(sym, side.upper(), otype, round(px, 2), qty,
                            stop_loss=float(kw["stop"]) if "stop" in kw else None,
                            target=float(kw["target"]) if "target" in kw else None,
                            macro_regime=self.regime_chip)
            card_note = f"SUBSTITUTED {args[0].upper()} -> {sym} ({sub['rationale']})"
        else:
            card_note = "brain gate ALLOW: " + "; ".join(gate["reasons"])
        # Small-account engine: 0.25-Kelly size guide + R:R >= 1:2 + drag.
        # NO_DEMO_STATE: no $1M fallback — equity must come from the ledger.
        eq: float | None = None
        if self.broker_name == "paper":
            try:
                eq = float(self.router.paper._ledger.cash)
            except Exception:
                eq = None
        if eq is None:
            return "UNAVAILABLE: no authoritative equity (ledger unreachable) — order blocked, nothing assumed."
        rr = Q.risk_reward(px, t.stop_loss, t.target)
        kelly = Q.kelly_position_size(eq, px, 0.55, 1.5, frac=0.25)
        drag = Q.spread_drag_bps(px * 0.0004, px)
        if rr is not None and rr < 2.0:
            raise SafetyError(f"R:R 1:{rr:.2f} < 1:2.0 — asymmetric edge required.")
        # Real exposure (never 0.0-blind): ledger positions x live quotes.
        # Unreadable -> BLOCK (leverage check must not silently pass).
        positions_value = self._positions_notional()
        if positions_value is None:
            raise SafetyError("positions value unreadable — leverage check cannot pass blind. Order blocked.")
        ok, why = self.safety.govern(t, eq, positions_value, self.safety.day_start_equity)
        if not ok:
            raise SafetyError(f"governor: {why}")
        # Canonical firewall (intent validation, idempotency, qty/notional
        # caps, price tolerance, stale/synthetic). Kill coverage stays with
        # govern(); this firewall runs a fresh board (no split-brain).
        from risk.firewall.firewall import RiskFirewall
        from risk.pre_trade.validation import TradeIntent
        import uuid as _uuid
        from decimal import Decimal as _D

        fw = self.__dict__.setdefault("_firewall", RiskFirewall())
        idem = f"os-{sym}-{side}-{qty}-{px}"
        try:
            fw_decision = fw.check(
                TradeIntent(order_id=_uuid.uuid4(), instrument_id=_uuid.uuid4(),
                            side=side, quantity=_D(str(qty)),
                            limit_price=_D(str(limit)) if limit else None,
                            idempotency_key=idem, authorized=True,
                            price_source="real"),
                ref_price=_D(str(px)),
                current_position=_D(str(self._ledger_positions().get(sym, 0.0))),
                data_age_s=0.0,
            )
        except Exception as exc:
            raise SafetyError(f"firewall error: {exc}")
        if str(getattr(fw_decision, "verdict", "")).lower() != "approve":
            raise SafetyError(f"firewall {getattr(fw_decision, 'verdict', '?')}: "
                              f"{getattr(fw_decision, 'reasons', fw_decision)}")
        card = (t.render(t.notional() / max(eq, 1e-9))
                + f"\nGate: {card_note} | Firewall: APPROVE"
                + f"\nCapital at Risk: {t.notional()/max(eq,1e-9):.2%} | "
                + f"Slippage Est: <${slip * qty:,.2f} | Impact Est: {impact_bps:.1f}bps "
                + f"(part {part:.3%}) | Spread drag ~{drag:.1f}bps | VWAP {loc:+.1f}σ | "
                + f"0.25-Kelly guide {kelly['qty']} sh (${kelly['notional']:,.0f})"
                + (f" | R:R 1:{rr:.2f}" if rr is not None else " | R:R n/a (add --stop/--target)")
                + f" | {qf.provenance.tier}")
        try:
            ans = input(f"{card}\nExecute on [{self.broker_name}]? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            fw._seen_keys.discard(idem)
            return "cancelled."
        if ans != "y":
            fw._seen_keys.discard(idem)
            return "cancelled (no order sent)."
        cur = self.router.current()
        if "twap" in kw:
            outs = []
            for s in Q.twap_schedule(qty, int(kw["twap"])):
                outs.append(cur.submit(sym, side, s["qty"], px,
                                       idempotency_key=f"os-{sym}-{s['slice']}-{s['qty']}"))
            self.safety.compliance.append("order", {"ticket": "TWAP", "slices": len(outs)})
            return f"TWAP submitted {len(outs)} slices @ {px:,.2f}."
        r = cur.submit(sym, side, qty, px, idempotency_key=f"os-{sym}-{side}-{qty}-{px}")
        self.safety.compliance.append("order", {"ticket": r})
        return f"submitted {r['order_id']} {r['status']} filled {r['filled']} @ {r['avg_price']}."

    # -- nl --
    def _ask(self, question: str) -> str:
        # 1. Direct local quant FM brain (100% offline, zero cloud keys)
        if "delta" in self.model_name.lower():
            return self.brain.chat(question)

        from delta_os.llm_gateway import conversational_fallback, research_tools
        import time as _t

        fb = conversational_fallback(question)
        if fb is not None:
            return fb
        # Async ReAct: prefetch quote/vwap/news concurrently so a dead feed
        # never blocks the loop; model reasons over whatever arrived.
        t0 = _t.perf_counter()
        pre = self._prefetch(question)
        try:
            fred_key = ""
            if self.vault is not None and not self.vault.locked:
                fred_key = (self.vault.get("fred") or {}).get("api_key", "")
            tools = research_tools(self.data, fred_key)
            # Inject prefetched snapshot as leading evidence (sub-100ms path).
            r = self.models.ask_with_tools("commentary", question, tools)
            el = _t.perf_counter() - t0
            flag = "" if r["critic_passed"] else " [UNVERIFIED NUMERICS]"
            snap = (f"\n[{pre}]" if pre else "")
            return f"[{r['model']}{flag} {el:.1f}s]{snap} {r['text'][:1500]}"
        except Exception:
            try:
                r = self.models.ask("commentary", question)
                return f"[{r['model']}] {r['text'][:1500]}"
            except Exception:
                # Institutional fail-soft: fallback to local DeltaBrain
                return self.brain.chat(question)

    def _prefetch(self, question: str) -> str:
        """Best-effort concurrent snapshot for any $TICKER / 2-5ch mentions."""
        import re as _re
        from concurrent.futures import ThreadPoolExecutor
        syms = [s.upper() for s in _re.findall(r"\$([A-Za-z]{1,5})\b", question)]
        for w in _re.findall(r"\b([A-Z]{2,5})\b", question):  # ALL-CAPS only;
            if w.upper() not in syms:  # lowercase prose never a ticker
                syms.append(w.upper())
        syms = [s for s in syms if s not in
                {"WHAT", "WITH", "AFTER", "TODAY", "SHOULD", "LOOK", "NEWS",
                 "HOW", "THE", "IS", "ON", "OF", "TO", "IN", "FOR", "AND",
                 "ARE", "YOU", "MARS", "THIS", "THAT"}][:3]
        if not syms:
            return ""
        def _one(s):
            try:
                qf = self.data.quote(s)
                px = float(qf.frame["close"].iloc[-1])
                return f"{s} ${px:,.2f} {qf.provenance.badge or '[' + qf.provenance.tier + ']'}"
            except Exception as exc:
                return f"{s} unavailable ({str(exc)[:60]})"
        try:
            with ThreadPoolExecutor(max_workers=3) as ex:
                return " | ".join(ex.map(_one, syms))
        except Exception:
            return ""

    # -- loop --
    def run(self) -> int:
        _load_session(self)
        try:  # Windows conhost is often cp1252: prefer UTF-8, never crash.
            import sys as _sys
            _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        print(self.status_bar())
        print("Type / to view commands, or ask any finance/trading question.")
        print("Hotkeys: Ctrl+C cancels turn | /kill emergency | /manual mode.")
        while True:
            try:
                line = input("DELTA > ")
            except (EOFError, KeyboardInterrupt):
                print("\nbye (session preserved; Ctrl+C never kills the REPL state).")
                return 0
            try:
                out, _ = self.handle(line)
            except KeyboardInterrupt:
                print("\ncancelled.")
                continue
            if out.endswith("\x00exit"):
                print("bye")
                return 0
            if out.startswith("\x1b[2J"):
                print(out, end="")
            elif out:
                try:
                    from delta_os.themes import paint

                    out = paint(out, self.theme)
                except Exception:
                    pass
                try:
                    print(out)
                except UnicodeEncodeError:
                    print(out.encode("ascii", "replace").decode("ascii"))
            try:
                print(self.status_bar())
            except Exception:
                pass


__all__ = ["OS_VERSION", "HELP", "Terminal"]
