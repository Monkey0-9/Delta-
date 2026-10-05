"""Security Master with Tri-Temporal Coordinates and Corporate Action Normalization.

W95: Implements institutional-grade security master eliminating survivorship bias
through tri-temporal coordinates and comprehensive corporate action handling.
"""

from .master import SecurityMaster, TriTemporalRecord
from .corporate_actions import CorporateAction, CorporateActionType, ActionNormalizer
from .symbol_mapper import SymbolMapper, AssetIdentifier
from .global_resolver import (GlobalInstrument, GlobalResolver,
                              BrokerSymbolMapper, AmbiguousInstrument,
                              UnknownInstrument)

__all__ = [
    "SecurityMaster",
    "TriTemporalRecord",
    "CorporateAction",
    "CorporateActionType",
    "ActionNormalizer",
    "SymbolMapper",
    "AssetIdentifier",
    "GlobalInstrument",
    "GlobalResolver",
    "BrokerSymbolMapper",
    "AmbiguousInstrument",
    "UnknownInstrument",
]
