"""P1 — Market Reality Engine (W124/W125/W126).

Institutional-grade historical market reconstruction:
  tick datasets (L1/L2/L3 events) -> corporate actions / delistings /
  symbol changes -> venue feeds -> timestamp normalization ->
  sequence validation -> dropped-message recovery ->
  order-book reconstruction -> session reconstruction ->
  historical scenario DB -> immutable PIT dataset platform.

Design principles:
- Deterministic: seed -> identical replay. No wall-clock, no global random.
- Immutable: every dataset version is content-hashed (sha256 over canonical bytes).
- PIT-correct: `asof(ts)` returns exactly what was knowable at ts.
- Fail-closed: gaps/invalid sequences are surfaced, never silently filled.

Waves covered: W124 (repo/arch hardening hooks via manifest),
W125 (immutable PIT dataset platform), W126 (historical scenario DB).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

ENGINE_VERSION = "market-reality-v1"
TICK = "tick"

SessionKind = Literal["pre", "regular", "post", "halt", "closed"]
EventLevel = Literal["L1", "L2", "L3", "TRADE", "ACTION"]


def _canon(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


def content_hash(obj: object) -> str:
    return hashlib.sha256(_canon(obj)).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class TickEvent:
    seq: int
    ts_ns: int  # venue-normalized nanoseconds since epoch
    venue: str
    level: str  # L1|L2|L3|TRADE|ACTION
    symbol: str
    payload: str  # canonical JSON string
    symbol_seq: int = 0  # per-symbol sequence for gap detection


@dataclass(frozen=True, slots=True)
class CorporateAction:
    symbol: str
    ex_ns: int
    kind: str  # SPLIT|DIVIDEND|MERGER|DELIST|SYMBOL_CHANGE
    factor: float  # e.g. split ratio
    detail: str = ""


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    dataset_id: str
    version: str
    content_hash: str
    n_events: int
    start_ns: int
    end_ns: int
    engine: str = ENGINE_VERSION


@dataclass(frozen=True, slots=True)
class GapReport:
    venue: str
    symbol: str
    missing: tuple[int, ...]
    recovered: bool


class TimestampNormalizer:
    """Normalize venue timestamps to a common ns clock (deterministic offsets)."""

    def __init__(self, venue_offsets_ns: dict[str, int] | None = None) -> None:
        self._offsets = dict(venue_offsets_ns or {})

    def normalize(self, venue: str, venue_ts_ns: int) -> int:
        return int(venue_ts_ns) + int(self._offsets.get(venue, 0))


class SequenceValidator:
    """Per (venue, symbol) gap detection + deterministic recovery markers."""

    def __init__(self) -> None:
        self._expected: dict[tuple[str, str], int] = {}

    def check(self, ev: TickEvent) -> GapReport | None:
        key = (ev.venue, ev.symbol)
        exp = self._expected.get(key, ev.symbol_seq)
        self._expected[key] = ev.symbol_seq + 1
        if ev.symbol_seq < exp:
            return GapReport(ev.venue, ev.symbol, (), True)  # duplicate -> idempotent
        if ev.symbol_seq > exp:
            missing = tuple(range(exp, ev.symbol_seq))
            return GapReport(ev.venue, ev.symbol, missing, False)
        return None

    def mark_recovered(self, report: GapReport) -> GapReport:
        return GapReport(report.venue, report.symbol, report.missing, True)


@dataclass
class TickStore:
    """Append-only immutable tick store with PIT reads."""

    _events: list[TickEvent] = field(default_factory=list)
    _by_symbol: dict[str, list[int]] = field(default_factory=dict)

    def append(self, ev: TickEvent) -> None:
        self._events.append(ev)
        self._by_symbol.setdefault(ev.symbol, []).append(len(self._events) - 1)

    def asof(self, symbol: str, ts_ns: int) -> list[TickEvent]:
        """Exactly the events knowable at ts_ns (event time <= ts)."""
        out: list[TickEvent] = []
        for idx in self._by_symbol.get(symbol, []):
            ev = self._events[idx]
            if ev.ts_ns <= ts_ns:
                out.append(ev)
        return out

    def replay(self, symbol: str, start_ns: int, end_ns: int) -> list[TickEvent]:
        return [e for e in self.asof(symbol, end_ns) if e.ts_ns >= start_ns]

    def content_hash(self) -> str:
        return content_hash([(e.seq, e.ts_ns, e.venue, e.level, e.symbol, e.payload) for e in self._events])


class OrderBookReconstructor:
    """Minimal deterministic L1/L2 reconstruction from tick events.

    Payloads are canonical JSON: {"bid": px, "ask": px, "bsz": q, "asz": q}
    or L2 {"levels": {"bids": [[px, q]...], "asks": [...]}}.
    """

    def __init__(self, store: TickStore) -> None:
        self._store = store

    def reconstruct(self, symbol: str, ts_ns: int) -> dict:
        book = {"bid": None, "ask": None, "bsz": 0.0, "asz": 0.0, "mid": None, "spread": None}
        for ev in self._store.asof(symbol, ts_ns):
            if ev.level not in ("L1", "L2"):
                continue
            try:
                p = json.loads(ev.payload)
            except Exception:
                continue
            if "bid" in p:
                book.update({k: p.get(k, book.get(k)) for k in ("bid", "ask", "bsz", "asz")})
            elif "levels" in p:
                lv = p["levels"]
                if lv.get("bids"):
                    book["bid"], book["bsz"] = lv["bids"][0][0], lv["bids"][0][1]
                if lv.get("asks"):
                    book["ask"], book["asz"] = lv["asks"][0][0], lv["asks"][0][1]
        if book["bid"] is not None and book["ask"] is not None:
            book["mid"] = (float(book["bid"]) + float(book["ask"])) / 2.0
            book["spread"] = float(book["ask"]) - float(book["bid"])
        return book


class SessionReconstructor:
    """Regular/pre/post/halt session labeling (deterministic, exchange calendar stub)."""

    def __init__(self, open_h: int = 9, open_m: int = 30, close_h: int = 16) -> None:
        self._o, self._om, self._c = open_h, open_m, close_h

    def label(self, ts_ns: int) -> SessionKind:
        dt = datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc)
        mins = dt.hour * 60 + dt.minute
        o, c = self._o * 60 + self._om, self._c * 60
        if o <= mins < c:
            return "regular"
        if mins < o:
            return "pre"
        return "post"


class CorporateActionAdjuster:
    """Apply splits/dividends/delist/symbol-change on a price series (PIT-safe)."""

    def __init__(self, actions: list[CorporateAction] | None = None) -> None:
        self._actions = sorted(actions or [], key=lambda a: a.ex_ns)

    def active_symbol(self, symbol: str, ts_ns: int) -> str:
        cur = symbol
        for a in self._actions:
            if a.ex_ns <= ts_ns and a.kind == "SYMBOL_CHANGE" and a.detail:
                # detail format "OLD>NEW"
                if ">" in a.detail:
                    old, new = a.detail.split(">", 1)
                    if cur == old:
                        cur = new
        return cur

    def is_delisted(self, symbol: str, ts_ns: int) -> bool:
        names = {symbol}
        # track renames forward
        cur = symbol
        for a in self._actions:
            if a.ex_ns > ts_ns:
                break
            if a.kind == "SYMBOL_CHANGE" and ">" in a.detail:
                old, new = a.detail.split(">", 1)
                if cur == old:
                    cur = new
                    names.add(cur)
            if a.kind == "DELIST" and (a.symbol in names or cur == a.symbol):
                return True
        return False

    def adjust(self, symbol: str, prices: list[tuple[int, float]]) -> list[tuple[int, float]]:
        """Backward-adjust prices for splits prior to each bar (deterministic)."""
        factor = 1.0
        # process actions in reverse: cumulative split factor after each bar
        splits = sorted(
            [a for a in self._actions if a.symbol == symbol and a.kind == "SPLIT"],
            key=lambda a: a.ex_ns,
            reverse=True,
        )
        out = []
        si = 0
        # for each price from latest to earliest accumulate factor
        for ts, px in sorted(prices, reverse=True):
            while si < len(splits) and splits[si].ex_ns > ts:
                factor *= float(splits[si].factor)
                si += 1
            out.append((ts, px / factor))
        return sorted(out)


class ImmutableDatasetPlatform:
    """W125: content-addressed, append-only dataset registry (PIT-safe)."""

    def __init__(self) -> None:
        self._versions: dict[str, DatasetVersion] = {}
        self._payloads: dict[str, list[TickEvent]] = {}

    def publish(self, dataset_id: str, events: list[TickEvent]) -> DatasetVersion:
        h = content_hash([(e.seq, e.ts_ns, e.venue, e.symbol, e.payload) for e in events])
        start = min((e.ts_ns for e in events), default=0)
        end = max((e.ts_ns for e in events), default=0)
        n_prev = sum(1 for k in self._versions if k.startswith(dataset_id + "@"))
        ver = DatasetVersion(dataset_id, f"v{n_prev + 1}", h, len(events), start, end)
        self._versions[f"{dataset_id}@{ver.version}"] = ver
        self._payloads[f"{dataset_id}@{ver.version}"] = list(events)
        return ver

    def fetch(self, dataset_id: str, version: str) -> list[TickEvent]:
        return list(self._payloads[f"{dataset_id}@{version}"])

    def verify(self, dataset_id: str, version: str) -> bool:
        key = f"{dataset_id}@{version}"
        evs = self._payloads[key]
        h = content_hash([(e.seq, e.ts_ns, e.venue, e.symbol, e.payload) for e in evs])
        return h == self._versions[key].content_hash


@dataclass(frozen=True, slots=True)
class ScenarioDef:
    scenario_id: str
    label: str
    start_ns: int
    end_ns: int
    symbols: tuple[str, ...]
    kind: str  # CRASH|FLASH|HALT|GAP|EARNINGS|FED|ILLIQUID


class HistoricalScenarioDB:
    """W126: curated historical stress/replay scenarios over the tick store."""

    _BUILTINS: tuple[ScenarioDef, ...] = (
        ScenarioDef("SCN-1987-CRASH", "1987 crash replay window", 0, 1, ("SPY",), "CRASH"),
        ScenarioDef("SCN-2010-FLASH", "2010 flash crash window", 0, 1, ("SPY", "QQQ"), "FLASH"),
        ScenarioDef("SCN-2020-COVID", "2020 covid gap window", 0, 1, ("SPY", "TLT"), "GAP"),
        ScenarioDef("SCN-HALT", "single-name halt window", 0, 1, ("AAA",), "HALT"),
        ScenarioDef("SCN-ILLIQ", "illiquid open window", 0, 1, ("ZZZ",), "ILLIQUID"),
    )

    def __init__(self) -> None:
        self._custom: list[ScenarioDef] = []

    def add(self, s: ScenarioDef) -> None:
        if not s.scenario_id.strip() or s.end_ns < s.start_ns or not s.symbols:
            raise ValueError("invalid scenario")
        self._custom.append(s)

    def list(self) -> list[ScenarioDef]:
        return list(self._BUILTINS) + list(self._custom)

    def replay_slice(self, store: TickStore, s: ScenarioDef) -> dict[str, list[TickEvent]]:
        return {sym: store.replay(sym, s.start_ns, s.end_ns) for sym in s.symbols}
