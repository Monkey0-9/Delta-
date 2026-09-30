"""HOME — new-session splash matching Section 22 specification. Disappears once conversation starts."""
from __future__ import annotations

from .base import BaseScreen
from ..state.store import TerminalStore
from ..viewmodels.models import HomeVM


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
        # Minimal landing screen — strictly no giant cards or implementation noise
        return "\n".join([
            "",
            "                         DELTA",
            "                  QUANT INTELLIGENCE",
            "",
            "",
            "  > Ask DELTA anything, research a strategy, analyze a market...",
            "",
            "",
            "       Model  delta-fm-research   Agent  quant-researcher",
            "       Session  default            Context  none",
            "",
            "",
            "                     / for commands · @ for context",
            "",
        ])

    def render_for(self, store: TerminalStore) -> str:
        """Splash with live model/agent/session/context chips."""
        ctx = store.context_str if hasattr(store, "context_str") else (store.symbol or "none")
        return "\n".join([
            "",
            "                         DELTA",
            "                  QUANT INTELLIGENCE",
            "",
            "",
            "  > Ask DELTA anything, research a strategy, analyze a market...",
            "",
            "",
            f"       Model  {store.model:<18} Agent  {store.agent}",
            f"       Session  {store.session_id:<16} Context  {ctx}",
            "",
            "",
            "                     / for commands · @ for context",
            "",
        ])
