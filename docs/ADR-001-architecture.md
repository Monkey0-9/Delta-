# ADR-001: DELTA Domain Architecture (W001–W010)

Status: frozen for W101–W180 launch slice.

## Bounded contexts
research | simulation | execution | production — dependency flows one way:
research -> simulation -> execution -> production. No reverse imports.

## State owners
- market data: `market_data/` + `data/security_master/`
- world state: `world_model/` (versioned, hashed)
- decisions: `decision/` + `research/ledger/`
- orders/fills: `execution/oms/` + `execution/paper/`
- experiments: `research/experiments/` (single promotion authority)

## Event schemas
Canonical in `schemas/events/` (v2): Tick/Trade/Quote/NBBO/L1/L2/L3/VenueMeta,
all with PIT stamps. Deterministic serialization in `schemas/serialization.py`.

## Research/prod separation
`config/loader.py` envs: research/simulation/paper/shadow/prod(+copilot/supervised).
Most-restrictive risk wins. Secrets via indirection only (vault, never config).

## Simulation/live separation
`execution/routing.py` rejects non-paper modes. Live adapters require signed
promotion + governance override. Paper/shadow use `IntegratedMarketSimulator`
and deterministic `simulation/l2_engine.py`.
