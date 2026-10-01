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
        # P0: execution only from live OMS; else empty parent + zero fill.
        return ExecutionVM(parent=f"{store.symbol} — no active slice", algo="—",
                           filled=0, total=0,
                           venues=(),
                           shortfall_bps=0.0, mode=store.mode.value)

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
        # P0: scenario/model/system health only from registries; else UNKNOWN.
        return {"library": (),
                "mode": store.mode.value}

    def render_text(self, vm) -> str:
        lib = ", ".join(vm["library"]) if vm["library"] else "no certified scenarios loaded"
        return f"SCENARIOS [{vm['mode']}] " + lib


class ModelsScreen(BaseScreen):
    name = "models"

    def build_viewmodel(self, store: TerminalStore):
        return {"models": (),
                "current": store.model, "mode": store.mode.value}

    def render_text(self, vm) -> str:
        mods = " ".join(f"{m}:{s}" for m, s in vm["models"]) if vm["models"] else "registry unreachable"
        return f"MODELS [{vm['mode']}] current={vm['current']} " + mods


class SystemScreen(BaseScreen):
    name = "system"

    def build_viewmodel(self, store: TerminalStore) -> SystemVM:
        # P0: no illustrative 812k eps / 183us. Unknown until instrumented.
        return SystemVM(
            data=((store.broker, "UNKNOWN"),),
            models=(),
            brokers=((store.broker, "UNKNOWN"),),
            events_per_s=0.0, p99_us=0.0,
            modelled_p99_ms=0.0, compute_p99_ms=0.0,
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
