"""
Point-in-Time (PIT) store for institutional data management.

This implements production-grade PIT storage:
- As-of queries with temporal guarantees
- PIT snapshots for exact reproducibility
- Data versioning and lineage
- Efficient temporal indexing
- Look-ahead bias prevention
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
import hashlib
import sqlite3
import json
from threading import Lock

from .tick_data import TickData, TickType
from .timestamps import DataTimestamps, TimestampType


class PITStorageType(Enum):
    """PIT storage type enumeration."""
    SQLITE = "SQLITE"
    MEMORY = "MEMORY"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True, slots=True)
class PITQuery:
    """
    PIT query specification.
    """
    symbol: str
    as_of: datetime
    data_types: Set[TickType] = field(default_factory=lambda: {TickType.QUOTE, TickType.TRADE})
    sources: Set[str] = field(default_factory=set)
    include_revisions: bool = False
    min_quality_score: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "data_types": [dt.value for dt in self.data_types],
            "sources": list(self.sources),
            "include_revisions": self.include_revisions,
            "min_quality_score": self.min_quality_score
        }


@dataclass(frozen=True, slots=True)
class PITSnapshot:
    """
    PIT snapshot of market data at a specific point in time.
    """
    snapshot_id: str
    query: PITQuery
    ticks: List[TickData]
    timestamps: DataTimestamps
    snapshot_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict = field(default_factory=dict)
    
    @property
    def snapshot_hash(self) -> str:
        """Compute hash of snapshot for versioning."""
        snapshot_str = "|".join([
            self.snapshot_id,
            self.query.to_dict().__str__(),
            str(len(self.ticks)),
            self.timestamps.compute_hash()
        ])
        return hashlib.sha256(snapshot_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "query": self.query.to_dict(),
            "num_ticks": len(self.ticks),
            "snapshot_timestamp": self.snapshot_timestamp.isoformat(),
            "timestamps": self.timestamps.to_dict(),
            "snapshot_hash": self.snapshot_hash,
            "metadata": self.metadata
        }


class PITStore:
    """
    Point-in-Time store for institutional data management.
    
    Features:
    - SQLite-based storage with temporal indexing
    - As-of queries with PIT guarantees
    - Snapshot management
    - Data versioning
    - Thread-safe operations
    """
    
    def __init__(self, 
                 db_path: str = ":memory:",
                 storage_type: PITStorageType = PITStorageType.SQLITE):
        """
        Initialize PIT store.
        
        Args:
            db_path: Database file path (":memory:" for in-memory)
            storage_type: Storage backend type
        """
        self.db_path = db_path
        self.storage_type = storage_type
        self.lock = Lock()
        
        # Initialize database
        self._init_database()
    
    # Current schema version. Bump when the schema changes and add a
    # migration function _migrate_<n>_to_<n+1> below.
    SCHEMA_VERSION = 1

    def _init_database(self) -> None:
        """Initialize database schema without destroying existing data.

        Non-destructive startup contract (P0-1):
        - Never DROP existing tables. Schema objects use IF NOT EXISTS.
        - A schema_version table tracks the applied version; pending
          migrations run inside explicit transactions.
        - A database with a NEWER unknown version is refused (never
          auto-migrated forward blindly).
        """
        if self.storage_type == PITStorageType.SQLITE:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            with self.lock:
                self._ensure_version_table()
                current = self._current_version()
                if current > self.SCHEMA_VERSION:
                    self.conn.close()
                    raise RuntimeError(
                        f"PIT store schema v{current} is newer than supported "
                        f"v{self.SCHEMA_VERSION}; refusing to open "
                        f"{self.db_path}")
                self._apply_migrations(current)
                self._create_schema()
    
    def _ensure_version_table(self) -> None:
        """Create the schema_version tracker if absent (version 0 = legacy)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                upgraded_at TEXT NOT NULL
            )
        """)
        cursor.execute("SELECT version FROM schema_version WHERE id = 1")
        if cursor.fetchone() is None:
            # Legacy databases created before versioning: the tables below
            # already exist at v1 shape, so record v1 without migrating.
            has_ticks = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='ticks'").fetchone() is not None
            version = 1 if has_ticks else 0
            cursor.execute(
                "INSERT INTO schema_version (id, version, upgraded_at) "
                "VALUES (1, ?, ?)",
                (version, datetime.now(timezone.utc).isoformat()))
        self.conn.commit()

    def _current_version(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM schema_version WHERE id = 1")
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def _apply_migrations(self, current: int) -> None:
        """Run pending migrations inside explicit transactions."""
        migrations = {
            # (from_version, to_version): migration_sql_or_callable
            (0, 1): None,  # v1 is the base schema created by _create_schema
        }
        version = current
        while version < self.SCHEMA_VERSION:
            nxt = version + 1
            step = migrations.get((version, nxt))
            if step is None and (version, nxt) not in migrations:
                raise RuntimeError(
                    f"No migration path from schema v{version} to v{nxt}")
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                if callable(step):
                    step(self.conn)
                self.conn.execute(
                    "UPDATE schema_version SET version = ?, upgraded_at = ? "
                    "WHERE id = 1",
                    (nxt, datetime.now(timezone.utc).isoformat()))
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
            version = nxt

    def _create_schema(self) -> None:
        """Create database schema."""
        cursor = self.conn.cursor()
        
        # Ticks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticks (
                tick_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                tick_type TEXT NOT NULL,
                data_json TEXT NOT NULL,
                event_time TEXT NOT NULL,
                source_timestamp TEXT NOT NULL,
                publication_timestamp TEXT NOT NULL,
                available_timestamp TEXT NOT NULL,
                ingestion_timestamp TEXT NOT NULL,
                revision_timestamp TEXT,
                decision_timestamp TEXT,
                processing_timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                sequence_number INTEGER NOT NULL,
                quality_score REAL DEFAULT 1.0,
                timestamp_hash TEXT NOT NULL,
                data_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Indexes for temporal queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_event_time 
            ON ticks(symbol, event_time)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_available_time 
            ON ticks(symbol, available_timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp_hash 
            ON ticks(timestamp_hash)
        """)
        
        # Snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                query_json TEXT NOT NULL,
                snapshot_timestamp TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL,
                tick_ids TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        self.conn.commit()
    
    def store_tick(self, 
                   tick: TickData,
                   timestamps: DataTimestamps,
                   source: str = "DEFAULT",
                   quality_score: float = 1.0) -> str:
        """
        Store tick with complete PIT metadata.
        
        Args:
            tick: Tick data to store
            timestamps: Complete timestamp set
            source: Data source identifier
            quality_score: Data quality score (0-1)
            
        Returns:
            Tick ID
        """
        with self.lock:
            cursor = self.conn.cursor()
            
            # Serialize tick data
            data_json = json.dumps(tick.to_dict())
            
            # Compute hashes
            timestamp_hash = timestamps.compute_hash()
            data_hash = hashlib.sha256(data_json.encode()).hexdigest()[:16]
            
            # Insert tick
            cursor.execute("""
                INSERT INTO ticks (
                    tick_id, symbol, tick_type, data_json,
                    event_time, source_timestamp, publication_timestamp,
                    available_timestamp, ingestion_timestamp, revision_timestamp,
                    decision_timestamp, processing_timestamp, source,
                    sequence_number, quality_score, timestamp_hash, data_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tick.tick_id,
                tick.symbol,
                tick.tick_type.value,
                data_json,
                timestamps.event_time.isoformat(),
                timestamps.source_timestamp.isoformat(),
                timestamps.publication_timestamp.isoformat(),
                timestamps.available_timestamp.isoformat(),
                timestamps.ingestion_timestamp.isoformat(),
                timestamps.revision_timestamp.isoformat() if timestamps.revision_timestamp else None,
                timestamps.decision_timestamp.isoformat() if timestamps.decision_timestamp else None,
                timestamps.processing_timestamp.isoformat(),
                source,
                tick.sequence_number,
                quality_score,
                timestamp_hash,
                data_hash,
                datetime.now(timezone.utc).isoformat()
            ))
            
            self.conn.commit()
            
            return tick.tick_id
    
    def query_as_of(self, query: PITQuery) -> PITSnapshot:
        """
        Query data as of specific point in time.
        
        Args:
            query: PIT query specification
            
        Returns:
            PIT snapshot
        """
        with self.lock:
            cursor = self.conn.cursor()
            
            # Build query
            sql = """
                SELECT tick_id, data_json, event_time, source_timestamp,
                       publication_timestamp, available_timestamp,
                       ingestion_timestamp, source, sequence_number,
                       quality_score, timestamp_hash, data_hash
                FROM ticks
                WHERE symbol = ?
                AND available_timestamp <= ?
            """
            
            params = [query.symbol, query.as_of.isoformat()]
            
            # Filter by data types
            if query.data_types:
                type_placeholders = ",".join(["?" for _ in query.data_types])
                sql += f" AND tick_type IN ({type_placeholders})"
                params.extend([dt.value for dt in query.data_types])
            
            # Filter by sources
            if query.sources:
                source_placeholders = ",".join(["?" for _ in query.sources])
                sql += f" AND source IN ({source_placeholders})"
                params.extend(list(query.sources))
            
            # Filter by quality
            if query.min_quality_score > 0:
                sql += " AND quality_score >= ?"
                params.append(query.min_quality_score)
            
            # Order by event time (most recent first)
            sql += " ORDER BY event_time DESC"
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            # Reconstruct ticks
            ticks = []
            timestamps_list = []
            
            for row in rows:
                (tick_id, data_json, event_time, source_time,
                 publication_time, available_time, ingestion_time,
                 source_name, seq_no, quality_score, ts_hash,
                 data_hash) = row
                
                # Parse tick data
                tick_dict = json.loads(data_json)
                
                # Reconstruct tick (simplified - would need full deserialization)
                tick = TickData(
                    tick_id=tick_dict.get("tick_id", tick_id),
                    tick_type=TickType(tick_dict.get("tick_type", "QUOTE")),
                    timestamp=datetime.fromisoformat(tick_dict["timestamp"]),
                    exchange=tick_dict.get("exchange", ""),
                    symbol=tick_dict.get("symbol", query.symbol),
                    sequence_number=tick_dict.get("sequence_number", 0)
                )
                
                ticks.append(tick)
                
                # Create timestamps from STORED values.
                # P-1.3: publication comes from the persisted record, never
                # reconstructed as event_time (which faked instant availability).
                timestamps = DataTimestamps(
                    event_time=datetime.fromisoformat(event_time),
                    source_timestamp=datetime.fromisoformat(source_time),
                    publication_timestamp=datetime.fromisoformat(publication_time),
                    available_timestamp=datetime.fromisoformat(available_time),
                    ingestion_timestamp=datetime.fromisoformat(ingestion_time)
                )
                
                timestamps_list.append(timestamps)
            
            # Create snapshot
            snapshot_id = hashlib.sha256(
                f"{query.symbol}_{query.as_of.isoformat()}_{len(ticks)}".encode()
            ).hexdigest()[:16]
            
            # Use most recent timestamps
            latest_timestamps = timestamps_list[0] if timestamps_list else DataTimestamps(
                event_time=query.as_of,
                source_timestamp=query.as_of,
                publication_timestamp=query.as_of,
                available_timestamp=query.as_of
            )
            
            snapshot = PITSnapshot(
                snapshot_id=snapshot_id,
                query=query,
                ticks=ticks,
                timestamps=latest_timestamps,
                metadata={
                    "quality_scores": [row[9] for row in rows],
                    "timestamp_hashes": [row[10] for row in rows],
                    "data_hashes": [row[11] for row in rows]
                }
            )
            
            return snapshot
    
    def create_snapshot(self, query: PITQuery) -> str:
        """
        Create and store a persistent snapshot.
        
        Args:
            query: PIT query specification
            
        Returns:
            Snapshot ID
        """
        # Query data
        snapshot = self.query_as_of(query)
        
        # Store snapshot
        with self.lock:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                INSERT INTO snapshots (
                    snapshot_id, query_json, snapshot_timestamp,
                    snapshot_hash, tick_ids, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.snapshot_id,
                json.dumps(query.to_dict()),
                snapshot.snapshot_timestamp.isoformat(),
                snapshot.snapshot_hash,
                json.dumps([tick.tick_id for tick in snapshot.ticks]),
                json.dumps(snapshot.metadata),
                datetime.now(timezone.utc).isoformat()
            ))
            
            self.conn.commit()
        
        return snapshot.snapshot_id
    
    def get_snapshot(self, snapshot_id: str) -> Optional[PITSnapshot]:
        """
        Retrieve stored snapshot.
        
        Args:
            snapshot_id: Snapshot identifier
            
        Returns:
            PITSnapshot if found, None otherwise
        """
        with self.lock:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                SELECT query_json, snapshot_timestamp, snapshot_hash, 
                       tick_ids, metadata_json
                FROM snapshots
                WHERE snapshot_id = ?
            """, (snapshot_id,))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            query_json, snapshot_time, snapshot_hash, tick_ids, metadata_json = row
            
            # Reconstruct query
            query_dict = json.loads(query_json)
            query = PITQuery(
                symbol=query_dict["symbol"],
                as_of=datetime.fromisoformat(query_dict["as_of"]),
                data_types=set(TickType(dt) for dt in query_dict["data_types"]),
                sources=set(query_dict["sources"]),
                include_revisions=query_dict["include_revisions"],
                min_quality_score=query_dict["min_quality_score"]
            )
            
            # Reconstruct snapshot
            # P-1.3: previously returned ticks=[] (a snapshot that hashes and
            # passes while containing nothing). Rebuild from stored tick_ids.
            tick_ids = json.loads(tick_ids) if isinstance(tick_ids, str) else (tick_ids or [])
            snap_ticks = []
            latest_evt: str | None = None
            latest_avail: str | None = None
            for tid in tick_ids:
                cursor.execute(
                    "SELECT tick_id, data_json, event_time, available_timestamp,"
                    " tick_type, symbol, sequence_number"
                    " FROM ticks WHERE tick_id = ?",
                    (tid,),
                )
                trow = cursor.fetchone()
                if not trow:
                    continue
                _, tdata, tevt, tavail, ttype, tsym, tseq = trow
                if latest_evt is None or tevt > latest_evt:
                    latest_evt = tevt
                if latest_avail is None or tavail > latest_avail:
                    latest_avail = tavail
                tdict = json.loads(tdata)
                snap_ticks.append(TickData(
                    tick_id=tdict.get("tick_id", tid),
                    tick_type=TickType(tdict.get("tick_type", ttype or "QUOTE")),
                    timestamp=datetime.fromisoformat(tdict.get("timestamp", tevt)),
                    exchange=tdict.get("exchange", ""),
                    symbol=tdict.get("symbol", tsym or ""),
                    sequence_number=int(tdict.get("sequence_number", tseq or 0)),
                ))
            # P2: snapshot lineage comes from the stored ticks (latest
            # event/available stamps), never fabricated as query.as_of.
            _evt = datetime.fromisoformat(latest_evt) if latest_evt else query.as_of
            _avl = datetime.fromisoformat(latest_avail) if latest_avail else query.as_of
            return PITSnapshot(
                snapshot_id=snapshot_id,
                query=query,
                ticks=snap_ticks,
                timestamps=DataTimestamps(
                    event_time=_evt,
                    source_timestamp=_evt,
                    publication_timestamp=_evt,
                    available_timestamp=_avl
                ),
                snapshot_timestamp=datetime.fromisoformat(snapshot_time),
                metadata=json.loads(metadata_json)
            )
    
    def get_data_versions(self, symbol: str, 
                         start_time: datetime,
                         end_time: datetime) -> List[Dict]:
        """
        Get data versions for a symbol in time range.
        
        Args:
            symbol: Symbol to query
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of version information
        """
        with self.lock:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                SELECT tick_id, event_time, available_timestamp, 
                       timestamp_hash, data_hash, quality_score
                FROM ticks
                WHERE symbol = ?
                AND event_time >= ? AND event_time <= ?
                ORDER BY event_time
            """, (symbol, start_time.isoformat(), end_time.isoformat()))
            
            rows = cursor.fetchall()
            
            return [
                {
                    "tick_id": row[0],
                    "event_time": row[1],
                    "available_timestamp": row[2],
                    "timestamp_hash": row[3],
                    "data_hash": row[4],
                    "quality_score": row[5]
                }
                for row in rows
            ]
    
    def close(self) -> None:
        """Close database connection."""
        if hasattr(self, 'conn'):
            self.conn.close()


__all__ = [
    "PITStorageType",
    "PITQuery",
    "PITSnapshot",
    "PITStore"
]