"""L2: Tri-temporal PIT data fabric + security master. Fail-closed, no lookahead."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import math

INF = datetime.max.replace(tzinfo=timezone.utc)

@dataclass(frozen=True, slots=True)
class PITRecord:
    payload: float
    t_event: datetime
    t_available: datetime
    t_ingested: datetime
    t_superseded: datetime = INF
    def check(self) -> None:
        if self.t_available < self.t_event:
            raise ValueError("tri-temporal clock inversion: t_available < t_event")
        if self.t_ingested < self.t_available:
            raise ValueError("tri-temporal clock inversion: t_ingested < t_available")
        if not (self.t_event <= self.t_superseded or self.t_superseded == INF):
            raise ValueError("superseded precedes event")

class PITStore:
    """Columnar-ish in-memory PIT store keyed by (symbol, field)."""
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], list[PITRecord]] = {}
    def insert(self, symbol: str, field: str, rec: PITRecord) -> None:
        rec.check()
        key = (symbol, field)
        lst = self._rows.setdefault(key, [])
        for r in lst:  # supersede overlap: close prior active record
            if r.t_superseded == INF and r.t_event <= rec.t_event:
                pass
        lst.append(rec)
    def point_in_time(self, symbol: str, field: str, asof: datetime) -> float:
        """Return payload knowable at `asof` (t_available <= asof), latest t_event. Raises if none."""
        cands = [r for r in self._rows.get((symbol, field), [])
                 if r.t_available <= asof and r.t_event <= asof
                 and (r.t_superseded == INF or asof < r.t_superseded)]
        if not cands:
            raise LookupError(f"PIT miss: {symbol}.{field} @ {asof.isoformat()} (fail-closed)")
        cands.sort(key=lambda r: (r.t_event, r.t_available))
        return cands[-1].payload

@dataclass(frozen=True, slots=True)
class ListingRule:
    uid: str; listed: datetime; delisted: datetime = INF

class SecurityMaster:
    """Immutable symbology timeline: Identifier(t) -> AssetUID, survivorship-free."""
    def __init__(self) -> None:
        self._alias: dict[tuple[str, datetime], str] = {}  # (identifier, date)->uid resolved via intervals
        self._listings: dict[str, ListingRule] = {}
    def register(self, uid: str, identifiers: list[str], listed: datetime, delisted: datetime = INF) -> None:
        self._listings[uid] = ListingRule(uid, listed, delisted)
        for i in identifiers:
            self._alias[(i, listed)] = uid
            self._alias[(i, delisted)] = uid
    def resolve(self, identifier: str, asof: datetime) -> str:
        best: str | None = None; best_t: datetime | None = None
        for (ident, t), uid in self._alias.items():
            if ident == identifier and t <= asof and (best_t is None or t > best_t):
                rule = self._listings[uid]
                if rule.listed <= asof < rule.delisted:
                    best, best_t = uid, t
        if best is None:
            raise LookupError(f"unresolvable identifier {identifier} @ {asof} (fail-closed)")
        return best
    def universe(self, asof: datetime) -> list[str]:
        return [u for u, r in self._listings.items() if r.listed <= asof < r.delisted]

def adjust_price(price: float, action: str, ratio: float) -> float:
    """Corporate-action normalizer: split/dividend/rights/spinoff via ratio. ratio>0 else fail."""
    if not math.isfinite(price) or not math.isfinite(ratio) or ratio <= 0:
        raise ValueError("non-finite corporate action inputs")
    if action not in ("split", "reverse_split", "cash_dividend", "stock_dividend", "rights", "spinoff"):
        raise ValueError(f"unknown action {action}")
    return price / ratio
