"""DELTA workstation app — ONE interactive frontend.

Textual full-screen when installed; Rich scrolling fallback otherwise.
Backend returns typed viewmodels; this layer only renders them.
Kill path bypasses the LLM and requires typed confirmation.
"""
from __future__ import annotations

import shutil

from config.mode import DeltaMode, mode_banner
from .commands import parser as cmd_parser
from .state import store as store_mod
from .state.selectors import header_model, status_model
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


class DeltaApp:
    """Workstation controller (UI-framework agnostic)."""

    def __init__(self, mode: DeltaMode = DeltaMode.PAPER) -> None:
        self.store = store_mod.reset_store(mode)
        self.pending_kill = False

    # -- command dispatch (slash + NL converge) -------------------------
    def dispatch(self, text: str) -> str:
        parsed = cmd_parser.parse(text)
        action = parsed.get("action")
        args = parsed.get("args", [])

        if action is not None and action.name == "kill":
            return self._kill_step(text)

        if action is not None:
            screen = SCREENS.get(action.screen)
            if args:
                maybe_sym = args[0].upper()
                if maybe_sym.isalpha() and len(maybe_sym) <= 6:
                    self.store.symbol = maybe_sym
            if screen is None:
                return f"unknown screen {action.screen}"
            self.store.set_screen(screen.name)
            vm = screen.build_viewmodel(self.store)
            self.store.publish(screen.name, vm)
            return screen.render_text(vm)

        # chat fallback: lightweight, never blocks kill path
        if parsed["kind"] == "chat":
            return ("I can route that to a workspace: try /market, /book NVDA, "
                    "/research, /portfolio, /risk, /execution, /system.")
        return f"unknown command: {text!r} — Ctrl+P for palette"

    def _kill_step(self, text: str) -> str:
        if "CONFIRM" in text.upper():
            self.store.kill_armed = True
            self.pending_kill = False
            return "KILL SWITCH ENGAGED — all orders cancelled, positions flagged flat (paper rail)."
        self.pending_kill = True
        return ("KILL SWITCH ARMED — type `/kill CONFIRM` to engage. "
                "This bypasses the LLM and hits the risk governor directly.")

    def header(self) -> str:
        from .widgets.chrome import header_text
        return header_text(header_model(self.store))

    # -- runners ---------------------------------------------------------
    def run_textual(self):  # pragma: no cover
        from textual.app import App, ComposeResult
        from textual.widgets import Header, Footer, Input, Static

        screens = SCREENS
        controller = self

        class _TUI(App):
            CSS = "Screen { layout: vertical; }"

            def compose(self) -> ComposeResult:
                yield Header()
                self.body = Static(controller.render_current())
                yield self.body
                self.cmd = Input(placeholder="› command (/ + Tab) or question")
                yield self.cmd
                yield Footer()

            def on_input_submitted(self, ev) -> None:
                out = controller.dispatch(ev.value)
                self.body.update(out)
                self.cmd.value = ""

        _TUI().run()

    def render_current(self) -> str:
        name = self.store.workspace
        screen = SCREENS.get(name, SCREENS["home"])
        vm = screen.build_viewmodel(self.store)
        return f"{self.header()}\n{mode_banner(self.store.mode)}\n\n{screen.render_text(vm)}"

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
        while True:
            try:
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
                print(self.dispatch(text))
            except Exception as exc:  # never crash the loop
                print(f"ERROR: {exc}")


def main(mode: str = "PAPER") -> int:
    return DeltaApp(DeltaMode.parse(mode)).run()


if __name__ == "__main__":
    raise SystemExit(main())
