"""Stage-2 K: authority gate — LLM order attempts refused by deterministic layer."""
from __future__ import annotations

import re

_ORDER_RE = re.compile(
    r"\b(buy|sell|short|cover|flatten|cancel)\b[^.\n]{0,60}\b(\d+|all|everything|positions?|portfolio)\b|\b(order|place order)\b",
    re.IGNORECASE,
)


class AuthorityRefused(RuntimeError):
    pass


def refuse_llm_order(text: str) -> None:
    """Raise AuthorityRefused if text contains an order intent. Pure function, tested."""
    if _ORDER_RE.search(text or ""):
        raise AuthorityRefused(
            "AUTHORITY_REFUSED: Finance AI has no order authority — "
            "intent routed to deterministic Decision/Risk/OMS path only.")


__all__ = ["AuthorityRefused", "refuse_llm_order"]
