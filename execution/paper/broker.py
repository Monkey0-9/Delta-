from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time

from execution.ems.adapter import (
    ExecutionAck,
    ExecutionRequest,
)


@dataclass(frozen=True, slots=True)
class PaperFill:

    fill_id: str
    order_id: str
    asset: str
    quantity: float
    price: float
    timestamp_ns: int


EXECUTION_MODEL_VERSION = "exec-sim-v1"


class PaperBroker:

    def __init__(
        self,
        prices: dict[str, float],
        spreads_bps: dict[str, float] | None = None,
        adv: dict[str, float] | None = None,
        simulate: bool = False,
    ):
        self.prices = dict(prices)
        self.spreads_bps = dict(spreads_bps or {})
        self.adv = dict(adv or {})
        self.simulate = simulate
        self.orders: dict[
            str,
            ExecutionRequest,
        ] = {}

        self.fills: dict[
            str,
            PaperFill,
        ] = {}
        # per-asset microstructure simulators (lazy; W171-W180 wiring)
        self._sims: dict[str, object] = {}
        # P-1.6: simulator failures are recorded per asset, never swallowed.
        self._sim_degraded: dict[str, str] = {}
        self.exec_model_version = EXECUTION_MODEL_VERSION

    def _simulator_for(self, asset: str, price: float):
        """Lazy IntegratedMarketSimulator seeded per asset (deterministic)."""
        from simulation.market_simulator.integrated_simulator import (
            IntegratedMarketSimulator,
        )

        sim = self._sims.get(asset)
        if sim is None:
            sim = IntegratedMarketSimulator(symbol=asset)
            sim.seed_order_book(base_price=price,
                                spread_bps=self.spreads_bps.get(asset, 5.0))
            self._sims[asset] = sim
        return sim

    def execution_report(self, order_id: str) -> dict:
        """W171-W180: spread + impact + latency + fee attribution per fill."""
        for fill in self.fills.values():
            if fill.order_id == order_id:
                price = self.prices.get(fill.asset, fill.price)
                spread_bps = self.spreads_bps.get(fill.asset, 5.0)
                # P-1.6: unknown ADV is reported as unknown (None), never as a
                # fake 1M that would understate participation and impact.
                adv_known = fill.asset in self.adv and self.adv[fill.asset] > 0
                qty = abs(fill.quantity)
                if adv_known:
                    adv: float = self.adv[fill.asset]
                    part: float | None = qty / adv
                    from execution.impact.model import (
                        AlmgrenChrissModel,
                        ImpactParameters,
                    )

                    model = AlmgrenChrissModel(ImpactParameters(adv=adv))
                    impact = model.calculate_impact(qty, price)
                else:
                    part = None
                    impact = None
                return {
                    "order_id": order_id,
                    "fill_price": fill.price,
                    "mid_price": price,
                    "spread_bps": spread_bps,
                    "participation_rate": part,
                    "adv_known": adv_known,
                    "impact_bps": impact,
                    "exec_model_version": self.exec_model_version,
                    "sim_status": self._sim_degraded.get(fill.asset, "ok"),
                }
        return {"order_id": order_id, "status": "no-fill"}

    def submit(
        self,
        request: ExecutionRequest,
    ) -> ExecutionAck:

        if request.order_id in self.orders:

            return ExecutionAck(
                request.order_id,
                True,
                "PAPER-"
                + request.order_id,
                "idempotent replay",
            )

        price = self.prices.get(
            request.asset
        )

        if price is None:
            return ExecutionAck(
                request.order_id,
                False,
                None,
                "unknown asset",
            )

        self.orders[
            request.order_id
        ] = request

        fill_price = price
        if self.simulate:
            try:
                sim = self._simulator_for(request.asset, price)
                side = "BUY" if request.quantity > 0 else "SELL"
                res = sim.submit_market_order(side, abs(request.quantity))
                if res.execution_result.fills:
                    fill_price = res.execution_result.average_price
            except Exception as exc:
                # P-1.6: fill at quoted price but mark the degradation so no
                # downstream consumer mistakes this for a microstructure fill.
                fill_price = price
                self._sim_degraded[request.asset] = f"simulator failed: {exc}"

        timestamp_ns = time.time_ns()

        fill_id = hashlib.sha256(
            (
                request.order_id
                + str(timestamp_ns)
            ).encode()
        ).hexdigest()

        self.fills[
            fill_id
        ] = PaperFill(
            fill_id,
            request.order_id,
            request.asset,
            request.quantity,
            fill_price,
            timestamp_ns,
        )

        return ExecutionAck(
            request.order_id,
            True,
            "PAPER-"
            + request.order_id,
            "filled",
        )