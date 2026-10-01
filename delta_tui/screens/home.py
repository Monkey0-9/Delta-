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
        return HomeVM(
            regime="NEUTRAL", liquidity="NORMAL",
            net_liq=1_024_218.0, gross_pct=143.2, net_pct=37.6,
            var99=2.14, es99=3.31, drawdown=4.82,
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
