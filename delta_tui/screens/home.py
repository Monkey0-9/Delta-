"""HOME — new-session splash matching user specification frontpart. Disappears once conversation starts."""
from __future__ import annotations
import shutil

from .base import BaseScreen
from ..state.store import TerminalStore
from ..viewmodels.models import HomeVM
from ..widgets.chrome import render_frontpart


class HomeScreen(BaseScreen):
    name = "home"

    def build_viewmodel(self, store: TerminalStore) -> HomeVM:
        # P-1.2: the store carries no portfolio figures, so the viewmodel
        # reports UNAVAILABLE (None) instead of fabricated splash numbers.
        snap = store.viewmodels.get("home_snapshot", {}) or {}
        return HomeVM(
            regime=snap.get("regime", "UNKNOWN"),
            liquidity=snap.get("liquidity", "UNKNOWN"),
            net_liq=snap.get("net_liq"),
            gross_pct=snap.get("gross_pct"),
            net_pct=snap.get("net_pct"),
            var99=snap.get("var99"),
            es99=snap.get("es99"),
            drawdown=snap.get("drawdown"),
            opportunities=store.viewmodels.get("home_opps", ()),
            mode=store.mode.value,
        )

    def render_text(self, vm: HomeVM) -> str:
        width = shutil.get_terminal_size((100, 30)).columns
        return render_frontpart({"model": "delta", "agent": "delta", "session": "default"}, width=width)

    def render_for(self, store: TerminalStore) -> str:
        """Splash with live model/agent/session/context chips matching exact user frontpart."""
        width = shutil.get_terminal_size((100, 30)).columns
        return render_frontpart(store, width=width)
