"""EXECUTION / ORDERS / SCENARIOS / MODELS / SYSTEM / SESSION / AUTOMATION screens."""
from __future__ import annotations

from .base import BaseScreen
from ..state.store import TerminalStore
from ..viewmodels.models import ExecutionVM, SystemVM


class AutomationScreen(BaseScreen):
    name = "automation"

    def build_viewmodel(self, store: TerminalStore):
        # A3: no hardcoded automations. Real queue state from
        # store.viewmodels["automation_jobs"]; else empty (UNAVAILABLE).
        jobs = store.viewmodels.get("automation_jobs", None)
        items = tuple(jobs) if isinstance(jobs, (list, tuple)) and jobs else ()
        return {
            "mode": store.mode.value,
            "symbol": store.symbol,
            "items": items,
        }

    def render_text(self, vm) -> str:
        items = vm.get("items", ()) or ()
        if not items:
            return (f"AUTOMATIONS [{vm.get('mode', 'PAPER')}] UNAVAILABLE "
                    f"(no scheduled jobs) [SOURCE/no-scheduler]")
        lines = [f"AUTOMATIONS [{vm.get('mode', 'PAPER')}] [SOURCE/scheduler]", ""]
        for job in items:
            if isinstance(job, dict):
                name = job.get("name", "?")
                sched = job.get("schedule", "")
                status = job.get("status", "")
                dot = "●" if str(status).lower() == "active" else "○"
                lines += [f"{dot} {name}", f"  {sched} · {status}" if sched else f"  {status}", ""]
            else:
                lines += [f"● {job}", ""]
        lines += ["[Create] [Pause] [Resume] [History]"]
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
        # A3: models only from an attached source
        # (store.viewmodels["models_snapshot"]); else empty (UNAVAILABLE with
        # reason — never fake READY/NEEDS_KEY badges).
        snap = store.viewmodels.get("models_snapshot") or {}
        models = tuple(snap.get("models", ())) if isinstance(snap, dict) else ()
        return {"models": models,
                "current": store.model, "mode": store.mode.value,
                "source": str(snap.get("source", "unavailable")) if isinstance(snap, dict) and models else "unavailable"}

    def render_text(self, vm) -> str:
        if not vm["models"]:
            return (f"MODELS [{vm['mode']}] UNAVAILABLE [SOURCE/no-registry] — "
                    f"registry unreachable (no model source attached)")
        mods = " ".join(f"{m}:{s}" for m, s in vm["models"])
        src = vm.get("source", "registry") or "registry"
        return f"MODELS [{vm['mode']}] current={vm['current']} {mods} [SOURCE/{src}]"


class SystemScreen(BaseScreen):
    name = "system"

    def build_viewmodel(self, store: TerminalStore) -> SystemVM:
        # A3: telemetry only from an attached source
        # (store.viewmodels["system_snapshot"]); no-source renders UNAVAILABLE
        # (None), never 0 events/s as if measured.
        snap = store.viewmodels.get("system_snapshot") or {}
        if isinstance(snap, dict) and all(
                k in snap and snap[k] is not None
                for k in ("events_per_s", "p99_us", "modelled_p99_ms",
                          "compute_p99_ms")):
            return SystemVM(
                data=tuple(snap.get("data", ((store.broker, "UNKNOWN"),))),
                models=tuple(snap.get("models", ())),
                brokers=tuple(snap.get("brokers", ((store.broker, "UNKNOWN"),))),
                events_per_s=snap.get("events_per_s"),
                p99_us=snap.get("p99_us"),
                modelled_p99_ms=snap.get("modelled_p99_ms"),
                compute_p99_ms=snap.get("compute_p99_ms"),
                mode=store.mode.value,
                source=str(snap.get("source", "telemetry")))
        return SystemVM(
            data=((store.broker, "UNKNOWN"),),
            models=(),
            brokers=((store.broker, "UNKNOWN"),),
            events_per_s=None, p99_us=None,
            modelled_p99_ms=None, compute_p99_ms=None,
            mode=store.mode.value, source="unavailable")

    def render_text(self, vm: SystemVM) -> str:
        if any(v is None for v in (vm.events_per_s, vm.p99_us,
                                   vm.modelled_p99_ms, vm.compute_p99_ms)):
            return (f"SYSTEM [{vm.mode}] UNAVAILABLE [SOURCE/no-telemetry] — "
                    f"no instrumented engine (events/s p99 unknown)")
        return (f"SYSTEM [{vm.mode}] events/s {vm.events_per_s:,.0f} "
                f"p99 {vm.p99_us:.0f}us "
                f"(modelled p99 {vm.modelled_p99_ms:.2f}ms vs "
                f"compute p99 {vm.compute_p99_ms:.3f}ms) "
                f"[SOURCE/{vm.source}]")


class SessionScreen(BaseScreen):
    name = "session"

    def build_viewmodel(self, store: TerminalStore):
        return {"session": store.session_id, "workspace": store.workspace,
                "mode": store.mode.value}

    def render_text(self, vm) -> str:
        return f"SESSION {vm['session']} screen={vm['workspace']} [{vm['mode']}]"


class DataScreen(BaseScreen):
    """Audit-gap closure: DATA workspace (feeds/quality/freshness/PIT)."""
    name = "data"

    def build_viewmodel(self, store: TerminalStore):
        snap = store.viewmodels.get("data_snapshot", {}) or {}
        return {"mode": store.mode.value,
                "feeds": snap.get("feeds", ()),
                "quality": snap.get("quality", "UNKNOWN"),
                "freshness_s": snap.get("freshness_s"),
                "dataset_version": snap.get("dataset_version", "v1")}

    def render_text(self, vm) -> str:
        feeds = ", ".join(f"{n}:{s}" for n, s in vm["feeds"]) \
            if vm["feeds"] else "no feeds reporting (UNAVAILABLE)"
        fresh = (f"{vm['freshness_s']:.1f}s" if vm["freshness_s"] is not None
                 else "UNAVAILABLE [SOURCE/no-feed]")
        return (f"DATA [{vm['mode']}] feeds {feeds} | quality {vm['quality']} | "
                f"freshness {fresh} | dataset {vm['dataset_version']}")
