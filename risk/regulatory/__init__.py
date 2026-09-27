"""Pre-Trade Regulatory Risk Gateway (SEC Rule 15c3-5).

W102: Implements hardware/kernel-level checks for order price collars,
max dollar caps, short locate validation, and fat-finger traps.
"""

from .gateway import RegulatoryGateway, CheckResult, CheckType
from .checks import (
    PriceCollarCheck,
    MaxOrderSizeCheck,
    ShortLocateCheck,
    FatFingerCheck,
    CapitalThresholdCheck
)

__all__ = [
    "RegulatoryGateway",
    "CheckResult",
    "CheckType",
    "PriceCollarCheck",
    "MaxOrderSizeCheck",
    "ShortLocateCheck",
    "FatFingerCheck",
    "CapitalThresholdCheck",
]
