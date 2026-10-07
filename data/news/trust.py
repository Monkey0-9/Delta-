"""News as untrusted input (Stream D P0)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import re

_INJECTION = re.compile(
    r"(ignore\s+(all\s+)?prior\s+instructions|buy\s+\d+|sell\s+\d+|transfer\s+|wire\s+|system\s*:)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class NewsItem:
    news_id: str
    source: str
    published_at: datetime
    retrieved_at: datetime
    headline: str
    body: str
    entities: tuple[str, ...] = ()
    novelty: float = 0.0
    importance: float = 0.0
    confidence: float = 0.0
    hash: str = ""

    @staticmethod
    def create(source: str, published_at: datetime, headline: str, body: str,
               entities: tuple[str, ...] = ()) -> "NewsItem":
        now = datetime.now(timezone.utc)
        h = sha256(f"{source}|{published_at.isoformat()}|{headline}|{body}".encode()).hexdigest()[:16]
        nid = f"NEWS-{h[:8].upper()}"
        return NewsItem(news_id=nid, source=source, published_at=published_at,
                        retrieved_at=now, headline=headline, body=body,
                        entities=entities, hash=h)

    def quarantine_reason(self) -> str | None:
        if _INJECTION.search(self.headline + " " + self.body):
            return "prompt_injection_pattern"
        return None

    def is_trusted_for_tools(self) -> bool:
        return self.quarantine_reason() is None


# Stage-2 J-min: real novelty + materiality (replaces 0.0 pass-throughs).
# Novelty = 1 - max token-Jaccard vs recent headlines (dedup-aware).
# Materiality = catalyst-lexicon weight x entity centrality, calibrated 0..1.
_CATALYST_W = {
    "earnings": 0.9, "guidance": 0.85, "merger": 0.95, "acquisition": 0.95,
    "lawsuit": 0.7, "fda": 0.9, "rate": 0.6, "layoff": 0.65,
    "buyback": 0.6, "dividend": 0.55, "downgrade": 0.7, "upgrade": 0.6,
    "default": 0.95, "bankrupt": 1.0, "sec": 0.75, "restat": 0.9,
}


def _tokens(s: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Z]{3,}", s or "")} - {"the", "and", "for"}


def novelty_score(headline: str, recent: list[str]) -> float:
    cur = _tokens(headline)
    if not cur:
        return 0.0
    best = 0.0
    for r in recent:
        oth = _tokens(r)
        if not oth:
            continue
        jac = len(cur & oth) / max(1, len(cur | oth))
        best = max(best, jac)
    return round(1.0 - best, 4)


def materiality_score(headline: str, body: str, n_entities: int | tuple | list) -> float:
    if isinstance(n_entities, (tuple, list)):
        n_entities = len(n_entities)
    text = f"{headline} {body}".lower()
    w = max([v for k, v in _CATALYST_W.items() if k in text] + [0.15])
    ent = min(1.0, 0.4 + 0.2 * n_entities)
    return round(min(1.0, w * (0.6 + 0.4 * ent)), 4)


def score_news(headline: str, body: str, entities: tuple[str, ...],
               recent: list[str] | None = None) -> tuple[float, float]:
    return (novelty_score(headline, recent or []),
            materiality_score(headline, body, len(entities)))


__all__ = ["NewsItem", "novelty_score", "materiality_score", "score_news"]
