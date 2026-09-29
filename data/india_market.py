"""Legacy-path shim: `data.india_market` re-exports delta_os.india_market.

Keeps the `financial-data` router path (`data/`) connected to the same
canonical implementation used by the live terminal + OpenCode tools.
"""
from delta_os.india_market import *  # noqa: F401,F403
from delta_os.india_market import (  # noqa: F401
    INDIA_MARKET_VERSION,
    NIFTY50,
    SECTORS,
    INDEX_MAP,
    normalize_symbol,
    normalize_auto,
    market_status,
    quote,
    universe,
)
