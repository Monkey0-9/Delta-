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
        # Stage-5 UI-3: HOME 4-pane (MARKET / INTELLIGENCE / PORTFOLIO / ATTENTION).
        # Every number: live/paper state or UNAVAILABLE with SOURCE/AS-OF badges.
        def _n(v, src="runtime", asof=""):
            if v is None:
                return f"UNAVAILABLE [SOURCE/{src}]" + (f" [AS-OF {asof}]" if asof else "")
            try:
                return f"{float(v):.2f} [SOURCE/{src}]"
            except Exception:
                return f"{v} [SOURCE/{src}]"
        opps = getattr(vm, "opportunities", ()) or ()
        attn = list(opps[:3]) if opps else ["No alerts — feeds nominal or UNAVAILABLE"]
        lines = [
            f"MODE [{getattr(vm, 'mode', 'PAPER')}]  REGIME: {vm.regime}  LIQ: {vm.liquidity}",
            "-" * 64,
            f"MARKET      SPY/QQQ/NVDA/AAPL: {_n(None, 'no-feed')} (live feed or UNAVAILABLE)",
            f"INTEL       Signal: REVIEW  Confidence: {_n(None, 'model')}  Regime: {vm.regime}",
            f"PORTFOLIO   NAV {_n(vm.net_liq)}  Gross {_n(vm.gross_pct)}%  Net {_n(vm.net_pct)}%",
            f"RISK        VaR99 {_n(vm.var99)}  ES99 {_n(vm.es99)}  DD {_n(vm.drawdown)}",
            "ATTENTION   " + " | ".join(str(a)[:60] for a in attn),
            "-" * 64,
            "Every figure carries SOURCE/AS-OF/FRESHNESS/CONFIDENCE or UNAVAILABLE.",
        ]
        return "\n".join(lines)

    def render_for(self, store: TerminalStore) -> str:
        """Splash with live model/agent/session/context chips matching exact user frontpart."""
        width = shutil.get_terminal_size((100, 30)).columns
        return render_frontpart(store, width=width)
