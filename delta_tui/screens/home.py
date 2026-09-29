"""HOME — command cockpit. Answers: what is happening / matters / needs attention."""
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
        lines = [
            f"HOME [{vm.mode}]  regime={vm.regime} liq={vm.liquidity}",
            f"NLV ${vm.net_liq:,.0f}  gross {vm.gross_pct:.1f}%  net {vm.net_pct:.1f}%",
            f"VaR99 {vm.var99:.2f}%  ES99 {vm.es99:.2f}%  DD {vm.drawdown:.2f}%",
        ]
        for o in vm.opportunities[:5]:
            lines.append(f"  - {o}")
        return "\n".join(lines)
