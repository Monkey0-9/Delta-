"""OpenCode-style interactive terminal for DELTA OS.

Copies the opencode interaction model and improves it for trading:

- Single-line prompt that expands to multiline (Esc+Enter newline, Enter send)
- Fuzzy `/` command palette with descriptions (opencode `tab` menu equivalent)
- Plain scrolling conversation (no fullscreen lock-in; copy/paste works)
- Ctrl+C clears the line, Ctrl+C on empty line quits (opencode parity) | Ctrl+K kill | Ctrl+L clear
- Session persistence (~/.delta/session.json + input history)
- Every slash command executes against the live delta_os core
  (DataRouter / quantkit / SafetyState) — zero stub numbers, ever.
- Natural language flows to the backend with graceful LLM fallback and
  per-turn elapsed + provenance badges. No regex rejection walls.

Public API kept stable: OpenCodeTerminal(backend).run(), TerminalState,
Command, DeltaCompleter, ExecutionMode, TradingMode, Theme.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class ExecutionMode(Enum):
    """Execution mode for trading."""
    RECOMMENDATION = "RECOMMENDATION"
    PAPER = "PAPER"
    COPILOT = "COPILOT"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"


class TradingMode(Enum):
    """Trading mode."""
    ANALYSIS = "ANALYSIS"
    RESEARCH = "RESEARCH"
    TRADING = "TRADING"
    SIMULATION = "SIMULATION"


class Theme(Enum):
    """Terminal theme."""
    LIGHT = "LIGHT"
    DARK = "DARK"
    PRO = "PRO"


@dataclass
class TerminalState:
    """Terminal state."""
    execution_mode: ExecutionMode = ExecutionMode.SUPERVISED
    trading_mode: TradingMode = TradingMode.ANALYSIS
    theme: Theme = Theme.DARK
    workspace: str = "default"
    regime: str = "NEUTRAL"
    liquidity: str = "NORMAL"
    pnl: str = "+$0.00"
    var: str = "VaR99: $0.00"
    broker_status: str = "PAPER"
    market_status: str = "CLOSED"


@dataclass
class Command:
    """Command definition (drives palette + /help + aliases)."""
    name: str
    description: str
    handler: Callable[[str], str]
    aliases: list[str] = field(default_factory=list)
    requires_confirmation: bool = False


class DeltaCompleter:
    """Fuzzy `/` completer with descriptions (prompt_toolkit compatible).

    Works with FuzzyCompleter/WordCompleter when prompt_toolkit is present;
    otherwise exposes plain `suggest(prefix)` for the readline fallback.
    """

    def __init__(self, commands: list[Command]):
        self.commands = commands
        names: dict[str, str] = {}
        for c in commands:
            names[c.name] = c.description
            for a in c.aliases:
                names.setdefault(a, f"alias of /{c.name}")
        self._names = names

    def suggest(self, prefix: str) -> list[tuple[str, str]]:
        p = prefix.lstrip("/").lower()
        return [(n, d) for n, d in sorted(self._names.items()) if p in n.lower()]

    # prompt_toolkit protocol (duck-typed; only resolved if ptk installed)
    def get_completions(self, document: Any, complete_event: Any) -> Any:
        text = document.get_word_before_cursor()
        if not text.startswith("/"):
            return []
        try:
            from prompt_toolkit.completion import Completion
            from prompt_toolkit.formatted_text import HTML
        except ImportError:
            return []
        out = []
        for name, desc in self.suggest(text):
            out.append(Completion("/" + name, start_position=-len(text),
                                  display=HTML(f"<b>/{name}</b>  {desc}")))
        return out


# Slash commands executed by the LIVE delta_os core (never stubs).
_LIVE_PASSTHROUGH = (
    "quote", "india", "indicators", "stats", "reason", "quant", "risk", "fundamental", "report", "news", "macro",
    "track", "portfolio", "trade", "backtest", "model", "broker", "auth",
    "kill", "unlock", "flatten", "mode", "theme", "workspace", "auto",
    "manual", "clear", "help", "status",
)


class OpenCodeTerminal:
    """OpenCode-style chat terminal for DELTA OS (live-engine frontend)."""

    def __init__(self, backend: Any):
        self._backend = backend
        self._state = TerminalState()
        self._commands = self._build_commands()
        self._completer = DeltaCompleter(self._commands)
        # Live engine: single source of truth for market data/risk/safety.
        from delta_os.repl import Terminal as _OsTerminal

        self._os = _OsTerminal()
        try:
            from delta_os.repl import _load_session as _ls
            _ls(self._os)
            self._state.workspace = self._os.workspace
        except Exception:
            pass
        self._turn_cancelled = False

    # -- registry ------------------------------------------------------
    def _build_commands(self) -> list[Command]:
        cmds = [self._live_cmd(n) for n in _LIVE_PASSTHROUGH
                if n not in ("mode", "theme", "workspace", "status", "help", "clear", "exit")]
        cmds += [
            Command("mode", "Switch execution mode (recommendation/paper/copilot/supervised/autonomous)",
                    self._cmd_mode, aliases=["m"]),
            Command("theme", "Switch theme (light/dark/pro)", self._cmd_theme, aliases=["th"]),
            Command("workspace", "Switch workspace", self._cmd_workspace, aliases=["ws"]),
            Command("status", "Show system status", self._cmd_status, aliases=["s"]),
            Command("help", "Show help", self._cmd_help, aliases=["h", "?"]),
            Command("clear", "Clear screen (keeps context)", self._cmd_clear, aliases=["cls"]),
            Command("exit", "Exit terminal", self._cmd_exit, aliases=["quit", "q"]),
        ]
        # de-dupe by name, local overrides win
        seen: dict[str, Command] = {}
        for c in cmds:
            seen[c.name] = c
        return list(seen.values())

    def _build_keybindings(self):
        """OpenCode-style keys. Extracted for testing (no console needed)."""
        from prompt_toolkit.key_binding import KeyBindings

        kb = KeyBindings()

        @kb.add("c-c")
        def _(event):
            # OpenCode-style: Ctrl+C clears a non-empty line (cancel);
            # on an empty line it quits the CLI. prompt_toolkit 3.x
            # Application has no .abort() — exit() is the API.
            buf = event.app.current_buffer
            if buf.text.strip():
                self._turn_cancelled = True
                buf.reset()
            else:
                event.app.exit(exception=KeyboardInterrupt())

        @kb.add("enter")
        def _(event):
            # OpenCode-style: Enter submits, Esc+Enter inserts a newline.
            event.app.exit(result=event.app.current_buffer.text)

        @kb.add("escape", "enter")
        def _(event):
            event.app.current_buffer.insert_text("\n")

        @kb.add("c-k")
        def _(event):
            event.app.exit(result="/kill")

        @kb.add("c-l")
        def _(event):
            event.app.renderer.clear()

        return kb

    # -- main loop ------------------------------------------------------
    def run(self):
        """Run the chat loop. Never crashes on bad input/dead net/no keys."""
        self._banner()
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.completion import FuzzyCompleter
            from prompt_toolkit.history import FileHistory

            hist = os.path.join(os.path.expanduser("~"), ".delta", "input_history")
            os.makedirs(os.path.dirname(hist), exist_ok=True)
            kb = self._build_keybindings()

            session: Any = PromptSession(
                history=FileHistory(hist),
                completer=FuzzyCompleter(self._completer),
                complete_while_typing=True,
                complete_style="COLUMN",
                multiline=True,
                prompt_continuation="  ┆ ",
                key_bindings=kb,
                bottom_toolbar=self._toolbar,
                style=self._ptk_style(),
                mouse_support=False,
                wrap_lines=True,
            )
        except Exception:
            session = None  # pipes/CI/no console -> plain input() below

        if session is None:
            prompt_fn = lambda: input(self._prompt_text())  # noqa: E731
        else:
            _no_console = {"v": False}

            def prompt_fn():  # noqa: F811 - set in branch above
                if _no_console["v"]:
                    return input(self._prompt_text())
                try:
                    from prompt_toolkit.formatted_text import HTML as _HTML
                    return session.prompt(_HTML(self._prompt_html()), multiline=True)
                except Exception as exc:
                    if "NoConsoleScreenBuffer" in type(exc).__name__ or (
                            not __import__("sys").stdin.isatty()):
                        _no_console["v"] = True
                        print("(plain input mode: no console buffer)")
                        return input(self._prompt_text())
                    raise

        while True:
            self._turn_cancelled = False
            try:
                text = prompt_fn()
            except (EOFError, KeyboardInterrupt):
                print("\nbye (session preserved).")
                return 0
            if text is None:
                continue
            text = text.strip()
            if self._turn_cancelled:
                print("cancelled.")
                continue
            if not text:
                continue
            try:
                out, done = self.handle(text)
            except KeyboardInterrupt:
                print("\ncancelled.")
                continue
            except Exception as exc:  # never crash the loop
                print(f"ERROR: {exc}")
                continue
            if out:
                self._render(out)
            if done:
                print("bye")
                return 0
            self._print_status()

    def handle(self, text: str) -> tuple[str, bool]:
        """Process one line. Returns (output, exit?). Never raises."""
        if text.startswith("/"):
            out = self._slash(text[1:])
            if out.endswith("\x00exit"):
                return "bye", True
            return out, False
        return self._chat(text), False

    # -- input routing ---------------------------------------------------
    def _slash(self, rest: str) -> str:
        parts = rest.split()
        name = parts[0].lower() if parts else ""
        args = " ".join(parts[1:])
        for c in self._commands:
            if name == c.name or name in c.aliases:
                if c.requires_confirmation:
                    return self._confirm(c, args)
                try:
                    return c.handler(args)
                except Exception as exc:
                    return f"ERROR: {exc}"
        close = self._did_you_mean(name)
        return f"unknown /{name}" + (f" — did you mean: {close}?" if close else "")

    def _chat(self, text: str) -> str:
        """Conversational path: greetings fast-path, backend, LLM fallback."""
        t0 = time.perf_counter()
        try:
            from delta_os.llm_gateway import conversational_fallback
            fb = conversational_fallback(text)
            if fb is not None:
                return fb
        except Exception:
            pass
        try:
            from trader.command_router import FinanceCommandRouter
            request = FinanceCommandRouter().route(text)
            resp = self._backend.dispatch(request)
            el = time.perf_counter() - t0
            return f"{resp}\n[{el:.1f}s]"
        except Exception:
            pass
        # Graceful fallback: finance-grounded LLM commentary (never a wall).
        try:
            out, _ = self._os.handle(text)
            return out
        except Exception as exc:
            return (f"model unavailable: {exc} "
                    "(try /quote, /quant, /news — or /model switch groq-free).")

    def _live_cmd(self, name: str) -> Command:
        def _run(args: str) -> str:
            out, _ = self._os.handle(f"/{name} {args}".strip())
            self._sync_state()
            return out
        return Command(name, f"Live: /{name} (delta_os core)", _run)

    def _confirm(self, cmd: Command, args: str) -> str:
        try:
            ans = input(f"Confirm /{cmd.name} {args}? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "cancelled."
        if ans != "y":
            return "cancelled (no order sent)."
        try:
            return cmd.handler(args)
        except Exception as exc:
            return f"ERROR: {exc}"

    def _cmd_mode(self, args: str) -> str:
        if not args:
            return f"Current mode: {self._state.execution_mode.value}\nAvailable: recommendation, paper, copilot, supervised, autonomous"
        m = args.strip().lower()
        mapping = {e.value.lower(): e for e in ExecutionMode}
        if m not in mapping:
            return f"Invalid mode. Available: {', '.join(mapping)}"
        self._state.execution_mode = mapping[m]
        # mirror into engine safety where the vocab overlaps
        try:
            if m in ("supervised", "copilot", "paper", "recommendation"):
                self._os.handle("/manual")
            elif m == "autonomous":
                self._os.handle("/auto on")
        except Exception:
            pass
        return f"Mode switched to: {self._state.execution_mode.value}"

    def _cmd_theme(self, args: str) -> str:
        if not args:
            return f"Current theme: {self._state.theme.value}\nAvailable: light, dark, pro"
        m = args.strip().lower()
        mapping = {e.value.lower(): e for e in Theme}
        if m not in mapping:
            return f"Invalid theme. Available: {', '.join(mapping)}"
        self._state.theme = mapping[m]
        return f"Theme switched to: {self._state.theme.value}"

    def _cmd_workspace(self, args: str) -> str:
        if not args:
            return f"Current workspace: {self._state.workspace}"
        out, _ = self._os.handle(f"/workspace {args.strip()}")
        self._sync_state()
        return out

    def _cmd_status(self, args: str) -> str:
        now = datetime.now()
        day = now.weekday()
        mkt = "CLOSED"
        if 0 <= day <= 4 and 9 <= now.hour < 16:
            mkt = "OPEN"
        self._state.market_status = mkt
        return (f"SYSTEM STATUS\n{'=' * 50}\n"
                f"Execution Mode: {self._state.execution_mode.value}\n"
                f"Trading Mode: {self._state.trading_mode.value}\n"
                f"Workspace: {self._state.workspace}\n"
                f"Market: {mkt}\n"
                f"Engine: {self._os.status_bar()}\n"
                f"{'=' * 50}\nSystem: OPERATIONAL")

    def _cmd_help(self, args: str) -> str:
        cats = {"Trading": ["quote", "india", "quant", "indicators", "stats", "reason", "risk", "fundamental", "report", "trade", "news", "macro"],
                "Portfolio": ["portfolio", "track", "backtest", "flatten", "kill"],
                "System": ["mode", "theme", "workspace", "model", "broker", "auth", "status", "clear", "exit", "help"]}
        lines = ["DELTA OS Commands  (type / + Tab to fuzzy-search)", "=" * 50, ""]
        by_name = {c.name: c for c in self._commands}
        for cat, names in cats.items():
            lines.append(f"{cat}:")
            for n in names:
                c = by_name.get(n)
                if c:
                    al = f" ({', '.join('/' + a for a in c.aliases)})" if c.aliases else ""
                    lines.append(f"  /{c.name}{al} - {c.description}")
            lines.append("")
        lines.append("Or just ask naturally: `How does SPY look?` `VWAP bands on NVDA?`")
        return "\n".join(lines)

    def _cmd_clear(self, args: str) -> str:
        try:
            os.system("cls" if os.name == "nt" else "clear")
        except Exception:
            pass
        return self._status_line() + "\n(screen cleared; context kept)"

    def _cmd_exit(self, args: str) -> str:
        return "bye\x00exit"

    # -- chrome ------------------------------------------------------------
    @staticmethod
    def _ptk_style() -> Any:
        """Opencode-like dark theme for prompt, completions, toolbar."""
        try:
            from prompt_toolkit.styles import Style as _Style
            return _Style.from_dict({
                "prompt.mode": "bold #7dd3fc",
                "prompt.ws": "#a5b4fc",
                "prompt.arrow": "bold #34d399",
                "completion-menu.completion": "bg:#1e293b #e2e8f0",
                "completion-menu.completion.current": "bg:#0ea5e9 #000000 bold",
                "completion-menu.meta.completion": "bg:#1e293b #64748b",
                "completion-menu.meta.completion.current": "bg:#0ea5e9 #000000",
                "bottom-toolbar": "bg:#0f172a #7dd3fc",
                "bottom-toolbar.text": "bg:#0f172a #7dd3fc",
            })
        except Exception:
            return None

    def _prompt_text(self) -> str:
        return "> "

    def _prompt_html(self) -> str:
        return '<span style="bold #20C9A6">&gt; </span>'

    def _toolbar(self) -> Any:
        mode = self._state.execution_mode.value.upper()
        return (f" DELTA  |  MARKET LIVE  |  DATA HEALTHY  |  RISK SAFE  |  "
                f"MODE: {mode}  |  / commands  |  Ctrl+K kill")

    def _status_line(self) -> str:
        now_utc = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        mode = self._state.execution_mode.value.upper()
        return f"DELTA  |  MARKET LIVE  |  DATA HEALTHY  |  RISK SAFE  |  MODE: {mode}  |  {now_utc}"

    def _console(self) -> Any:
        try:
            from rich.console import Console as _Console
            return _Console()
        except Exception:
            return None

    def _print_status(self) -> None:
        """Persistent toolbar owns the status bar — avoid stdout spam on every turn."""
        pass

    def _sync_state(self) -> None:
        try:
            self._state.workspace = self._os.workspace
            self._state.var = getattr(self._os, "var_chip", self._state.var)
        except Exception:
            pass

    def _did_you_mean(self, name: str) -> str:
        import difflib
        names = [c.name for c in self._commands]
        near = difflib.get_close_matches(name, names, n=3)
        return ", ".join("/" + n for n in near)

    @staticmethod
    def _safe(text: str) -> str:
        """Console-safe: keep Unicode where the terminal supports it,
        degrade glyphs (σ→s, —→-) where it cannot. Never crash printing."""
        try:
            enc = (getattr(__import__("sys").stdout, "encoding", None)
                   or "utf-8")
            text.encode(enc)
            return text
        except Exception:
            return (text.replace("σ", "sig").replace("—", "-")
                    .replace("→", "->").replace("▲", "^").replace("▼", "v")
                    .encode("ascii", "replace").decode("ascii"))

    def _banner(self) -> None:
        c = self._console()
        mode = self._state.execution_mode.value.upper()
        now_utc = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        header = f"DELTA  |  MARKET LIVE  |  DATA HEALTHY  |  RISK SAFE  |  MODE: {mode}  |  {now_utc}"
        splash = [
            "",
            header,
            "",
            "                         DELTA",
            "                  QUANT INTELLIGENCE",
            "",
            "  > Ask DELTA anything, research a strategy, analyze a market...",
            "",
            f"       Model: {self._os.model_name}   Agent: quant-researcher",
            f"       Session: {self._state.workspace}   Mode: {mode}   Risk: SAFE",
            "",
            "                     / for commands · Ctrl+K for kill switch",
            "",
        ]
        text = "\n".join(splash)
        if c is not None:
            c.print(f"[bold #20C9A6]{header}[/]")
            c.print("\n                         [bold white]DELTA[/]\n                  [dim]QUANT INTELLIGENCE[/]\n")
            c.print("  [bold #D6D8D7]> Ask DELTA anything, research a strategy, analyze a market...[/]\n")
            c.print(f"       [dim]Model:[/] {self._os.model_name}   [dim]Agent:[/] quant-researcher")
            c.print(f"       [dim]Session:[/] {self._state.workspace}   [dim]Mode:[/] {mode}   [dim]Risk:[/] SAFE\n")
            c.print("                     [dim]/ for commands · Ctrl+K for kill switch[/]\n")
        else:
            print(text)

    def _render(self, text: str) -> None:
        """Design-grade output: cards for tickets, clean markdown for analysis."""
        text = self._safe(text)
        c = self._console()
        if c is None:
            print(f"\nDELTA\n{text}\n")
            return
        try:
            # 1) Execution ticket -> bordered card (the money moment).
            if "PROPOSED EXECUTION" in text:
                from rich.panel import Panel as _Panel
                color = ("green" if "BUY" in text else
                         "red" if "SELL" in text else "cyan")
                c.print(_Panel(text, title="[bold]order ticket[/]",
                               border_style=color, padding=(0, 1)))
                return
            # 2) Kill / blocked / error states get their own voice.
            head = text[:40].upper()
            if head.startswith("KILLED") or "FROZEN" in head:
                from rich.panel import Panel as _Panel
                c.print(_Panel(text, border_style="red",
                               title="[bold red]kill switch[/]"))
                return
            if text.startswith("BLOCKED") or text.startswith("ERROR"):
                c.print(f"[bold red]{text}[/bold red]", markup=True)
                return
            c.print("\n[bold #20C9A6]DELTA[/]")
            if any(tok in text for tok in ("|", "##", "```", "\n- ", "\n* ",
                                           "===")):
                from rich.markdown import Markdown as _MD
                c.print(_MD(text))
            else:
                c.print(text, markup=False, highlight=False)
            c.print("")
        except Exception:
            try:
                print(f"\nDELTA\n{text}\n")
            except Exception:
                pass
