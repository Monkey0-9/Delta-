from __future__ import annotations

from collections.abc import Iterable, Iterator

from market_data.quote import Quote


class ReplayMarketFeed:
    """
    Deterministic historical feed.

    The same input sequence must produce the same output sequence.
    """

    def __init__(
        self,
        quotes: Iterable[Quote],
    ) -> None:
        self._quotes = tuple(quotes)

    def __iter__(self) -> Iterator[Quote]:
        yield from self._quotes