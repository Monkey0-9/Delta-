"""HOME — new-session splash matching Image 1. Disappears once conversation starts."""
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
        # Splash only — no portfolio numbers here (minimal philosophy).
        # Conversation screens own numbers once the session is active.
        return "\n".join([
            "",
            "                         DELTA",
            "               QUANT INTELLIGENCE CLI",
            "",
            "     RESEARCH  |  SIMULATE  |  ANALYZE  |  EXECUTE  |  LEARN",
            "",
            "  >  Ask DELTA anything, run a strategy, analyze a market, or type / for commands...   [Ctrl+K]",
            "",
            "       Model: delta-fm-research  |  Agent: quant-researcher  |  Session: default",
            "                    / for commands  |  Ctrl+O open browser  |  Ctrl+X K risk",
            "",
        ])

    def render_for(self, store: TerminalStore) -> str:
        """Splash with live model/agent/session chips."""
        return "\n".join([
            "",
            "                         DELTA",
            "               QUANT INTELLIGENCE CLI",
            "",
            "     RESEARCH  |  SIMULATE  |  ANALYZE  |  EXECUTE  |  LEARN",
            "",
            "  >  Ask DELTA anything, run a strategy, analyze a market, or type / for commands...   [Ctrl+K]",
            "",
            f"       Model: {store.model}  |  Agent: {store.agent}  |  Session: {store.session_id}",
            "                    / for commands  |  Ctrl+O open browser  |  Ctrl+X K risk",
            "",
        ])
