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


__all__ = ["NewsItem"]
