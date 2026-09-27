"""Tri-Temporal Security Master implementation.

Eliminates lookahead and survivorship bias through tri-temporal coordinates:
t_event, t_available, t_ingested, t_superseded
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class RecordStatus(StrEnum):
    """Status of a tri-temporal record."""
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class TriTemporalRecord:
    """
    Record with tri-temporal coordinates to eliminate lookahead bias.
    
    Coordinates:
    - t_event: Effective historical timestamp (e.g., fiscal quarter end)
    - t_available: Public dissemination time (e.g., SEC EDGAR timestamp)
    - t_ingested: System receipt timestamp (PTP-synchronized)
    - t_superseded: Timestamp when restatement replaced this value
    """
    record_id: UUID = field(default_factory=uuid4)
    asset_id: UUID = field(default_factory=uuid4)
    payload: dict[str, Any] = field(default_factory=dict)
    
    # Tri-temporal coordinates
    t_event: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    t_available: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    t_ingested: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    t_superseded: datetime | None = None
    
    status: RecordStatus = RecordStatus.ACTIVE
    source: str = "unknown"
    
    def __post_init__(self) -> None:
        """Validate tri-temporal coordinate consistency."""
        if self.t_available < self.t_event:
            raise ValueError(
                f"Invalid tri-temporal coordinates: t_available ({self.t_available}) "
                f"cannot be before t_event ({self.t_event})"
            )
        
        if self.t_ingested < self.t_available:
            raise ValueError(
                f"Invalid tri-temporal coordinates: t_ingested ({self.t_ingested}) "
                f"cannot be before t_available ({self.t_available})"
            )
    
    def is_active_at(self, query_time: datetime) -> bool:
        """Check if record is active at query time."""
        if self.status != RecordStatus.ACTIVE:
            return False
        
        if self.t_superseded is not None and query_time >= self.t_superseded:
            return False
        
        if query_time < self.t_available:
            return False  # Not yet publicly available
        
        return True
    
    def is_valid_for_backtest(self, backtest_date: datetime) -> bool:
        """
        Check if record is valid for backtest at given date.
        
        Eliminates lookahead bias by ensuring record was available
        at the backtest date.
        """
        return self.is_active_at(backtest_date) and self.t_available <= backtest_date


@dataclass(frozen=True, slots=True)
class AssetMetadata:
    """Metadata for a financial asset."""
    asset_id: UUID
    ticker: str
    cusip: str | None = None
    sedol: str | None = None
    isin: str | None = None
    figi: str | None = None
    asset_class: str = "equity"
    currency: str = "USD"
    exchange: str = "NYSE"
    
    # Lifecycle dates
    listed_date: datetime | None = None
    delisted_date: datetime | None = None
    
    # Corporate action flags
    has_splits: bool = False
    has_dividends: bool = False
    has_spinoffs: bool = False
    has_mergers: bool = False


class SecurityMaster:
    """
    Institutional-grade security master with tri-temporal coordinates.
    
    Eliminates survivorship bias by maintaining historical universe
    membership and asset lifecycles.
    """
    
    def __init__(self) -> None:
        self._records: dict[UUID, list[TriTemporalRecord]] = {}
        self._assets: dict[UUID, AssetMetadata] = {}
        self._symbol_map: dict[str, UUID] = {}  # ticker -> asset_id
        self._identifier_map: dict[str, UUID] = {}  # cusip/sedol/isin -> asset_id
    
    def add_asset(self, metadata: AssetMetadata) -> None:
        """Add asset metadata to master."""
        self._assets[metadata.asset_id] = metadata
        self._symbol_map[metadata.ticker.upper()] = metadata.asset_id
        
        if metadata.cusip:
            self._identifier_map[metadata.cusip] = metadata.asset_id
        if metadata.sedol:
            self._identifier_map[metadata.sedol] = metadata.asset_id
        if metadata.isin:
            self._identifier_map[metadata.isin] = metadata.asset_id
    
    def add_record(self, record: TriTemporalRecord) -> None:
        """Add tri-temporal record to master."""
        if record.asset_id not in self._records:
            self._records[record.asset_id] = []
        
        self._records[record.asset_id].append(record)
    
    def resolve_asset_id(
        self,
        identifier: str,
        identifier_type: str = "ticker"
    ) -> UUID | None:
        """
        Resolve asset ID from various identifier types.
        
        Supports: ticker, CUSIP, SEDOL, ISIN, FIGI
        """
        identifier = identifier.upper().strip()
        
        if identifier_type == "ticker":
            return self._symbol_map.get(identifier)
        else:
            return self._identifier_map.get(identifier)
    
    def get_universe_at_date(self, query_date: datetime) -> list[UUID]:
        """
        Get all assets that were listed and active at query date.
        
        Eliminates survivorship bias by excluding assets that
        were delisted before the query date or listed after.
        """
        universe: list[UUID] = []
        
        for asset_id, metadata in self._assets.items():
            # Check if asset was listed at query date
            if metadata.listed_date and query_date < metadata.listed_date:
                continue  # Not yet listed
            
            # Check if asset was delisted before query date
            if metadata.delisted_date and query_date >= metadata.delisted_date:
                continue  # Already delisted
            
            universe.append(asset_id)
        
        return universe
    
    def get_record_at_date(
        self,
        asset_id: UUID,
        query_date: datetime,
        record_type: str | None = None
    ) -> TriTemporalRecord | None:
        """
        Get the active record for an asset at a specific date.
        
        Returns the record that was publicly available at the query date,
        eliminating lookahead bias.
        """
        if asset_id not in self._records:
            return None
        
        candidates = [
            r for r in self._records[asset_id]
            if r.is_valid_for_backtest(query_date)
        ]
        
        if record_type:
            candidates = [r for r in candidates if r.payload.get("type") == record_type]
        
        if not candidates:
            return None
        
        # Return the most recent record by t_available
        return max(candidates, key=lambda r: r.t_available)
    
    def supersede_record(
        self,
        old_record_id: UUID,
        new_record: TriTemporalRecord,
        superseded_at: datetime
    ) -> None:
        """
        Mark a record as superseded by a new record.
        
        Used for restatements (e.g., 10-K/A replacing 10-K).
        """
        for asset_id, records in self._records.items():
            for i, record in enumerate(records):
                if record.record_id == old_record_id:
                    # Create superseded version
                    superseded = TriTemporalRecord(
                        record_id=record.record_id,
                        asset_id=record.asset_id,
                        payload=record.payload,
                        t_event=record.t_event,
                        t_available=record.t_available,
                        t_ingested=record.t_ingested,
                        t_superseded=superseded_at,
                        status=RecordStatus.SUPERSEDED,
                        source=record.source,
                    )
                    self._records[asset_id][i] = superseded
                    break
        
        # Add new record
        self.add_record(new_record)
    
    def validate_tri_temporal_consistency(self) -> list[str]:
        """
        Validate all tri-temporal coordinates for consistency.
        
        Returns list of validation errors.
        """
        errors: list[str] = []
        
        for asset_id, records in self._records.items():
            for record in records:
                try:
                    # Check coordinate ordering
                    if record.t_available < record.t_event:
                        errors.append(
                            f"Asset {asset_id}: t_available < t_event for record {record.record_id}"
                        )
                    
                    if record.t_ingested < record.t_available:
                        errors.append(
                            f"Asset {asset_id}: t_ingested < t_available for record {record.record_id}"
                        )
                    
                    # Check superseded timing
                    if record.t_superseded is not None:
                        if record.t_superseded < record.t_available:
                            errors.append(
                                f"Asset {asset_id}: t_superseded < t_available for record {record.record_id}"
                            )
                
                except Exception as e:
                    errors.append(f"Asset {asset_id}: Validation error for record {record.record_id}: {e}")
        
        return errors
