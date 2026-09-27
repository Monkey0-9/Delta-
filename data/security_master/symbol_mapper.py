"""Symbol Mapper for Historical Asset Resolution.

Resolves CUSIP, SEDOL, ISIN, Bloomberg Ticker, and FIGI across
30 years without survivorship leakage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class IdentifierType(StrEnum):
    """Types of asset identifiers."""
    TICKER = "ticker"
    CUSIP = "cusip"
    SEDOL = "sedol"
    ISIN = "isin"
    FIGI = "figi"
    PERMID = "permid"
    RIC = "ric"


@dataclass(frozen=True, slots=True)
class AssetIdentifier:
    """Asset identifier with validity period."""
    identifier: str
    identifier_type: IdentifierType
    asset_id: UUID = field(default_factory=uuid4)
    
    # Validity period
    effective_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expiry_date: datetime | None = None
    
    # Additional metadata
    exchange: str = ""
    currency: str = "USD"
    
    def is_valid_at(self, query_date: datetime) -> bool:
        """Check if identifier is valid at query date."""
        if query_date < self.effective_date:
            return False
        
        if self.expiry_date is not None and query_date >= self.expiry_date:
            return False
        
        return True


@dataclass(frozen=True, slots=True)
class SymbolMapping:
    """
    Historical symbol mapping timeline.
    
    Tracks ticker changes, mergers, and other identifier transformations
    over time to resolve historical assets without survivorship bias.
    """
    asset_id: UUID
    identifier_timeline: list[AssetIdentifier] = field(default_factory=list)
    
    def resolve_identifier_at_date(
        self,
        identifier_type: IdentifierType,
        query_date: datetime
    ) -> AssetIdentifier | None:
        """
        Resolve identifier of specific type at query date.
        """
        candidates = [
            id for id in self.identifier_timeline
            if id.identifier_type == identifier_type and id.is_valid_at(query_date)
        ]
        
        if not candidates:
            return None
        
        # Return the most recent effective identifier
        return max(candidates, key=lambda id: id.effective_date)
    
    def get_all_identifiers_at_date(self, query_date: datetime) -> list[AssetIdentifier]:
        """Get all valid identifiers at query date."""
        return [
            id for id in self.identifier_timeline
            if id.is_valid_at(query_date)
        ]


class SymbolMapper:
    """
    Multi-identifier symbol mapper supporting historical resolution.
    
    Eliminates survivorship bias by maintaining complete identifier
    timelines and validity periods.
    """
    
    def __init__(self) -> None:
        self._mappings: dict[UUID, SymbolMapping] = {}
        self._identifier_index: dict[str, list[tuple[UUID, IdentifierType]]] = {}
    
    def add_mapping(self, mapping: SymbolMapping) -> None:
        """Add symbol mapping to index."""
        self._mappings[mapping.asset_id] = mapping
        
        # Build identifier index
        for identifier in mapping.identifier_timeline:
            key = identifier.identifier.upper()
            if key not in self._identifier_index:
                self._identifier_index[key] = []
            
            self._identifier_index[key].append(
                (mapping.asset_id, identifier.identifier_type)
            )
    
    def add_identifier(self, asset_id: UUID, identifier: AssetIdentifier) -> None:
        """Add identifier to existing mapping."""
        if asset_id not in self._mappings:
            self._mappings[asset_id] = SymbolMapping(asset_id=asset_id)
        
        # Convert to mutable list
        existing = list(self._mappings[asset_id].identifier_timeline)
        existing.append(identifier)
        
        # Update mapping
        self._mappings[asset_id] = SymbolMapping(
            asset_id=asset_id,
            identifier_timeline=existing
        )
        
        # Update index
        key = identifier.identifier.upper()
        if key not in self._identifier_index:
            self._identifier_index[key] = []
        
        self._identifier_index[key].append(
            (asset_id, identifier.identifier_type)
        )
    
    def resolve_by_identifier(
        self,
        identifier: str,
        identifier_type: IdentifierType | None = None,
        query_date: datetime | None = None
    ) -> UUID | None:
        """
        Resolve asset ID by identifier.
        
        Args:
            identifier: The identifier string (ticker, CUSIP, etc.)
            identifier_type: Optional type hint for disambiguation
            query_date: Optional date for historical resolution
        
        Returns:
            Asset UUID if found, None otherwise
        """
        key = identifier.upper()
        
        if key not in self._identifier_index:
            return None
        
        candidates = self._identifier_index[key]
        
        if identifier_type:
            # Filter by type
            candidates = [
                (asset_id, id_type) for asset_id, id_type in candidates
                if id_type == identifier_type
            ]
        
        if not candidates:
            return None
        
        if query_date is None:
            # Return first match if no date specified
            return candidates[0][0]
        
        # Resolve historically
        for asset_id, _ in candidates:
            if asset_id not in self._mappings:
                continue
            
            mapping = self._mappings[asset_id]
            valid_ids = mapping.get_all_identifiers_at_date(query_date)
            
            # Check if our identifier is valid at this date
            for valid_id in valid_ids:
                if valid_id.identifier.upper() == key:
                    return asset_id
        
        return None
    
    def get_historical_tickers(
        self,
        asset_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> list[tuple[datetime, str]]:
        """
        Get historical ticker timeline for an asset.
        
        Returns list of (effective_date, ticker) tuples.
        """
        if asset_id not in self._mappings:
            return []
        
        mapping = self._mappings[asset_id]
        tickers = [
            (id.effective_date, id.identifier)
            for id in mapping.identifier_timeline
            if id.identifier_type == IdentifierType.TICKER
            and start_date <= id.effective_date <= end_date
        ]
        
        return sorted(tickers, key=lambda x: x[0])
    
    def track_ticker_change(
        self,
        asset_id: UUID,
        old_ticker: str,
        new_ticker: str,
        change_date: datetime
    ) -> None:
        """
        Record a ticker change event.
        
        Maintains historical continuity for backtesting.
        """
        # Mark old ticker as expired
        if asset_id in self._mappings:
            existing = list(self._mappings[asset_id].identifier_timeline)
            for i, identifier in enumerate(existing):
                if (
                    identifier.identifier.upper() == old_ticker.upper()
                    and identifier.identifier_type == IdentifierType.TICKER
                    and identifier.expiry_date is None
                ):
                    # Create expired version
                    expired = AssetIdentifier(
                        identifier=identifier.identifier,
                        identifier_type=identifier.identifier_type,
                        asset_id=identifier.asset_id,
                        effective_date=identifier.effective_date,
                        expiry_date=change_date,
                        exchange=identifier.exchange,
                        currency=identifier.currency,
                    )
                    existing[i] = expired
                    break
            
            self._mappings[asset_id] = SymbolMapping(
                asset_id=asset_id,
                identifier_timeline=existing
            )
        
        # Add new ticker
        new_identifier = AssetIdentifier(
            identifier=new_ticker,
            identifier_type=IdentifierType.TICKER,
            asset_id=asset_id,
            effective_date=change_date,
        )
        self.add_identifier(asset_id, new_identifier)
    
    def detect_identifier_collision(self) -> list[tuple[str, list[UUID]]]:
        """
        Detect identifiers that map to multiple assets.
        
        Returns list of (identifier, [asset_ids]) tuples for collisions.
        """
        collisions: list[tuple[str, list[UUID]]] = []
        
        for identifier, asset_list in self._identifier_index.items():
            unique_assets = set(asset_id for asset_id, _ in asset_list)
            
            if len(unique_assets) > 1:
                collisions.append((identifier, list(unique_assets)))
        
        return collisions
