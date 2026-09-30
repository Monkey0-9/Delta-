"""EXECUTION / ORDERS / SCENARIOS / MODELS / SYSTEM / SESSION / AUTOMATION screens."""
from __future__ import annotations

from .base import BaseScreen
from ..state.store import TerminalStore
from ..viewmodels.models import ExecutionVM, SystemVM


class AutomationScreen(BaseScreen):
    name = "automation"

    def build_viewmodel(self, store: TerminalStore):
        return {
            "mode": store.mode.value,
            "symbol": store.symbol,
            "items": [
                {"name": "Morning portfolio review", "schedule": "Every trading day · 07:30", "status": "Active"},
                {"name": "Risk regime watch", "schedule": "Active · event driven", "status": "Active"},
                {"name": f"{store.symbol} research monitor", "schedule": "Paused", "status": "Paused"},
            ]
        }

    def render_text(self, vm) -> str:
        symbol = vm.get("symbol", "NVDA")
        lines = [
            "AUTOMATIONS",
            "",
            "● Morning portfolio review",
            "  Every trading day · 07:30",
            "",
            "● Risk regime watch",
            "  Active · event driven",
            "",
            f"○ {symbol} research monitor",
            "  Paused",
            "",
            "[Create] [Pause] [Resume] [History]",
        ]
        return "\n".join(lines)


class ExecutionScreen(BaseScreen):
    name = "execution"

    def build_viewmodel(self, store: TerminalStore) -> ExecutionVM:
        return ExecutionVM(parent=f"{store.symbol} BUY 25,000", algo="VWAP",
                           filled=12400, total=25000,
                           venues=(("NASDAQ", 39), ("ARCA", 31)),
                           shortfall_bps=2.2, mode=store.mode.value)

    def render_text(self, vm: ExecutionVM) -> str:
        return (f"EXECUTION [{vm.mode}] {vm.parent} via {vm.algo} "
                f"{vm.filled}/{vm.total} shortfall {vm.shortfall_bps:+.1f}bps")


class OrdersScreen(BaseScreen):
    name = "orders"

    def build_viewmodel(self, store: TerminalStore):
        return {"orders": (), "mode": store.mode.value}

    def render_text(self, vm) -> str:
        return f"ORDERS [{vm['mode']}] no open orders (paper rail)"


class ScenariosScreen(BaseScreen):
    name = "scenarios"

    def build_viewmodel(self, store: TerminalStore):
        return {"library": ("2008", "2010-flash", "2020-covid", "2022-rates"),
                "mode": store.mode.value}

    def render_text(self, vm) -> str:
        return f"SCENARIOS [{vm['mode']}] " + ", ".join(vm["library"])


class ModelsScreen(BaseScreen):
    name = "models"

    def build_viewmodel(self, store: TerminalStore):
        return {"models": (("alpha-112", "HEALTHY"), ("regime-04", "HEALTHY")),
                "current": store.model, "mode": store.mode.value}

    def render_text(self, vm) -> str:
        return f"MODELS [{vm['mode']}] current={vm['current']} " + " ".join(
            f"{m}:{s}" for m, s in vm["models"])


class SystemScreen(BaseScreen):
    name = "system"

    def build_viewmodel(self, store: TerminalStore) -> SystemVM:
        return SystemVM(
            data=(("NASDAQ", "HEALTHY"), ("YAHOO", "DEGRADED")),
            models=(("alpha-112", "HEALTHY"),),
            brokers=((store.broker, "CONNECTED"),),
            events_per_s=812_440.0, p99_us=183.0,
            modelled_p99_ms=1.0, compute_p99_ms=0.02,
            mode=store.mode.value)

    def render_text(self, vm: SystemVM) -> str:
        return (f"SYSTEM [{vm.mode}] events/s {vm.events_per_s:,.0f} "
                f"p99 {vm.p99_us:.0f}us "
                f"(modelled p99 {vm.modelled_p99_ms:.2f}ms vs "
                f"compute p99 {vm.compute_p99_ms:.3f}ms)")


class SessionScreen(BaseScreen):
    name = "session"

    def build_viewmodel(self, store: TerminalStore):
        return {"session": store.session_id, "workspace": store.workspace,
                "mode": store.mode.value}

    def render_text(self, vm) -> str:
        return f"SESSION {vm['session']} screen={vm['workspace']} [{vm['mode']}]"
