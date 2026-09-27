from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from market_data.quote import Quote


class MarketDataAdapter(ABC):

    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def quotes(self) -> Iterable[Quote]:
        raise NotImplementedError

    @abstractmethod
    def is_connected(self) -> bool:
        raise NotImplementedError