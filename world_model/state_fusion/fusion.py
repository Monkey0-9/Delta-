from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256

from world_model.state.system_state import (
    MacroState,
    MarketState,
    RegimeState,
    UncertaintyState,
    WorldState,
)


@dataclass(frozen=True, slots=True)
class StateFusionInput:
    market: tuple[MarketState, ...] = ()
    macro: MacroState | None = None
    regime: RegimeState | None = None
    uncertainty: UncertaintyState | None = None
    portfolio_equity: Decimal = Decimal("0")
    portfolio_exposure: Decimal = Decimal("0")


class StateFusion:
    """
    Deterministically combines validated observations
    into a versioned WorldState.
    """

    @staticmethod
    def state_hash(canonical: str) -> str:
        return sha256(canonical.encode("utf-8")).hexdigest()

    def canonical(self, data: StateFusionInput) -> str:
        parts = [
            f"market={len(data.market)}",
            f"macro={data.macro}",
            f"regime={data.regime}",
            f"uncertainty={data.uncertainty}",
            f"equity={data.portfolio_equity}",
            f"exposure={data.portfolio_exposure}",
        ]
        return "|".join(parts)

    def build(
        self,
        data: StateFusionInput,
        *,
        previous: WorldState | None = None,
    ) -> WorldState:

        version = 1 if previous is None else previous.version + 1

        return WorldState(
            market=data.market,
            macro=data.macro,
            regime=data.regime,
            uncertainty=data.uncertainty,
            portfolio_equity=data.portfolio_equity,
            portfolio_exposure=data.portfolio_exposure,
            version=version,
        )