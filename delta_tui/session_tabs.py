"""Phase 16/41-42 — Session tabs. Each tab: focus/conversation/context/analysis.

Tabs share one authenticated runtime; each has own mode/broker/account/model
snapshot pointers. Session recovery restores exact pointers (tested).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionTab:
    tab_id: str
    title: str
    focus: str = ""
    conversation: list = field(default_factory=list)
    mode: str = "PAPER"
    broker: str = ""
    account: str = ""
    model: str = ""
    effort: str = "MEDIUM"
    watchlist: list = field(default_factory=list)


class SessionTabs:
    def __init__(self):
        self._tabs: dict[str, SessionTab] = {}
        self.active: str = ""
        self._n = 0

    def new(self, title: str) -> SessionTab:
        self._n += 1
        t = SessionTab(f"tab-{self._n}", title)
        self._tabs[t.tab_id] = t
        self.active = t.tab_id
        return t

    def switch(self, tab_id: str) -> SessionTab:
        try:
            self.active = tab_id
            return self._tabs[tab_id]
        except KeyError:
            raise ValueError(f"unknown tab {tab_id!r}")

    def snapshot(self) -> dict:
        return {"active": self.active,
                "tabs": {k: {"title": v.title, "focus": v.focus,
                             "mode": v.mode, "broker": v.broker,
                             "account": v.account, "model": v.model}
                         for k, v in self._tabs.items()}}

    def restore(self, snap: dict) -> None:
        self._tabs = {k: SessionTab(k, v["title"], v.get("focus", ""),
                                    [], v.get("mode", "PAPER"),
                                    v.get("broker", ""), v.get("account", ""),
                                    v.get("model", ""))
                      for k, v in snap.get("tabs", {}).items()}
        self.active = snap.get("active", "")


__all__ = ["SessionTab", "SessionTabs"]
