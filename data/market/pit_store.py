"""Point-in-Time Store - Avoid Look-Ahead Bias

Critical for realistic backtesting by ensuring data availability
matches what was actually known at each point in time.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
import hashlib
import json


class DataRevision(Enum):
    """Types of data revisions"""
    NONE = "none"  # No revisions
    RESTATED = "restated"  # Earnings restatements
    ADJUSTED = "adjusted"  # Price adjustments for splits/dividends
    CORRECTED = "corrected"  # Data errors corrected
    DELISTED = "delisted"  # Security delisted


@dataclass(frozen=True, slots=True)
class PITRecord:
    """Point-in-time data record"""
    symbol: str
    timestamp: datetime
    pit_timestamp: datetime  # When this data was first available
    data_type: str
    data: Dict[str, Any]
    revision: DataRevision = DataRevision.NONE
    data_hash: str = field(default="")
    source: str = "primary"
    
    def __post_init__(self):
        """Generate data hash for integrity"""
        if not self.data_hash:
            data_str = json.dumps(self.data, sort_keys=True, default=str)
            hash_obj = hashlib.sha256(data_str.encode())
            object.__setattr__(self, 'data_hash', hash_obj.hexdigest()[:16])


class PointInTimeStore:
    """Point-in-time data store for backtesting and research"""
    
    def __init__(self, db_path: str = "data/pit_store.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize SQLite database schema"""
        self._conn = sqlite3.connect(self.db_path)
        cursor = self._conn.cursor()
        
        # Main PIT table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pit_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                pit_timestamp DATETIME NOT NULL,
                data_type TEXT NOT NULL,
                data TEXT NOT NULL,
                revision TEXT NOT NULL,
                data_hash TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp, pit_timestamp, data_type, data_hash)
            )
        """)
        
        # Indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_timestamp 
            ON pit_records(symbol, timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pit_timestamp 
            ON pit_records(pit_timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_data_type 
            ON pit_records(data_type)
        """)
        
        # Metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pit_metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self._conn.commit()
    
    def store_record(self, record: PITRecord) -> bool:
        """Store a single PIT record"""
        cursor = self._conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO pit_records 
                (symbol, timestamp, pit_timestamp, data_type, data, revision, data_hash, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.symbol,
                record.timestamp.isoformat(),
                record.pit_timestamp.isoformat(),
                record.data_type,
                json.dumps(record.data),
                record.revision.value,
                record.data_hash,
                record.source,
            ))
            self._conn.commit()
            return True
        except Exception as e:
            print(f"Error storing PIT record: {e}")
            self._conn.rollback()
            return False
    
    def store_records_batch(self, records: List[PITRecord]) -> int:
        """Store multiple PIT records efficiently"""
        cursor = self._conn.cursor()
        
        try:
            data = [
                (
                    record.symbol,
                    record.timestamp.isoformat(),
                    record.pit_timestamp.isoformat(),
                    record.data_type,
                    json.dumps(record.data),
                    record.revision.value,
                    record.data_hash,
                    record.source,
                )
                for record in records
            ]
            
            cursor.executemany("""
                INSERT OR REPLACE INTO pit_records 
                (symbol, timestamp, pit_timestamp, data_type, data, revision, data_hash, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            
            self._conn.commit()
            return len(data)
        except Exception as e:
            print(f"Error storing PIT records batch: {e}")
            self._conn.rollback()
            return 0
    
    def get_data_at_pit(
        self,
        symbol: str,
        timestamp: datetime,
        data_type: str,
        max_lag_minutes: int = 15,
    ) -> Optional[PITRecord]:
        """Get data that was available at a specific point in time"""
        cursor = self._conn.cursor()
        
        # Find the most recent data available before or at the timestamp
        # accounting for data availability lag
        pit_cutoff = timestamp - timedelta(minutes=max_lag_minutes)
        
        cursor.execute("""
            SELECT symbol, timestamp, pit_timestamp, data_type, data, revision, data_hash, source
            FROM pit_records
            WHERE symbol = ? 
            AND data_type = ?
            AND pit_timestamp <= ?
            AND timestamp <= ?
            ORDER BY pit_timestamp DESC, timestamp DESC
            LIMIT 1
        """, (symbol, data_type, pit_cutoff.isoformat(), timestamp.isoformat()))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return PITRecord(
            symbol=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            pit_timestamp=datetime.fromisoformat(row[2]),
            data_type=row[3],
            data=json.loads(row[4]),
            revision=DataRevision(row[5]),
            data_hash=row[6],
            source=row[7],
        )
    
    def get_time_series(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        data_type: str,
        pit_lag_minutes: int = 15,
    ) -> pd.DataFrame:
        """Get time series data with point-in-time awareness"""
        cursor = self._conn.cursor()
        
        # Get data available at each point in time
        # This is a simplified version - real implementation would be more complex
        cursor.execute("""
            SELECT timestamp, pit_timestamp, data, revision, data_hash
            FROM pit_records
            WHERE symbol = ? 
            AND data_type = ?
            AND timestamp >= ? 
            AND timestamp <= ?
            AND pit_timestamp <= datetime(timestamp, '-' || ? || ' minutes')
            ORDER BY timestamp
        """, (symbol, data_type, start.isoformat(), end.isoformat(), pit_lag_minutes))
        
        rows = cursor.fetchall()
        if not rows:
            return pd.DataFrame()
        
        # Convert to DataFrame
        data_list = []
        for row in rows:
            data = json.loads(row[2])
            data['pit_timestamp'] = datetime.fromisoformat(row[1])
            data['revision'] = row[3]
            data['data_hash'] = row[4]
            data_list.append(data)
        
        df = pd.DataFrame(data_list)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        return df
    
    def get_symbols(self) -> List[str]:
        """Get all symbols in the store"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM pit_records")
        return [row[0] for row in cursor.fetchall()]
    
    def get_data_types(self, symbol: Optional[str] = None) -> List[str]:
        """Get available data types"""
        cursor = self._conn.cursor()
        if symbol:
            cursor.execute("SELECT DISTINCT data_type FROM pit_records WHERE symbol = ?", (symbol,))
        else:
            cursor.execute("SELECT DISTINCT data_type FROM pit_records")
        return [row[0] for row in cursor.fetchall()]
    
    def get_revisions(self, symbol: str, timestamp: datetime) -> List[PITRecord]:
        """Get all revisions of a data point"""
        cursor = self._conn.cursor()
        
        cursor.execute("""
            SELECT symbol, timestamp, pit_timestamp, data_type, data, revision, data_hash, source
            FROM pit_records
            WHERE symbol = ? 
            AND timestamp = ?
            ORDER BY pit_timestamp
        """, (symbol, timestamp.isoformat()))
        
        rows = cursor.fetchall()
        return [
            PITRecord(
                symbol=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                pit_timestamp=datetime.fromisoformat(row[2]),
                data_type=row[3],
                data=json.loads(row[4]),
                revision=DataRevision(row[5]),
                data_hash=row[6],
                source=row[7],
            )
            for row in rows
        ]
    
    def set_metadata(self, key: str, value: Any) -> bool:
        """Store metadata"""
        cursor = self._conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO pit_metadata (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, json.dumps(value)))
            self._conn.commit()
            return True
        except Exception as e:
            print(f"Error storing metadata: {e}")
            self._conn.rollback()
            return False
    
    def get_metadata(self, key: str) -> Optional[Any]:
        """Retrieve metadata"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT value FROM pit_metadata WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None
    
    def cleanup_old_data(self, days_to_keep: int = 365) -> int:
        """Remove old data to manage storage"""
        cursor = self._conn.cursor()
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        
        try:
            cursor.execute("""
                DELETE FROM pit_records 
                WHERE timestamp < ?
            """, (cutoff.isoformat(),))
            
            deleted = cursor.rowcount
            self._conn.commit()
            return deleted
        except Exception as e:
            print(f"Error cleaning up old data: {e}")
            self._conn.rollback()
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get store statistics"""
        cursor = self._conn.cursor()
        
        stats = {}
        
        # Total records
        cursor.execute("SELECT COUNT(*) FROM pit_records")
        stats['total_records'] = cursor.fetchone()[0]
        
        # Unique symbols
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM pit_records")
        stats['unique_symbols'] = cursor.fetchone()[0]
        
        # Data types
        cursor.execute("SELECT data_type, COUNT(*) FROM pit_records GROUP BY data_type")
        stats['data_types'] = dict(cursor.fetchall())
        
        # Date range
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM pit_records")
        min_date, max_date = cursor.fetchone()
        stats['date_range'] = {
            'min': min_date,
            'max': max_date,
        }
        
        # Database size
        stats['db_size_mb'] = self.db_path.stat().st_size / (1024 * 1024)
        
        return stats
    
    def close(self):
        """Close database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class UniverseManager:
    """Manage trading universe with point-in-time awareness"""
    
    def __init__(self, pit_store: PointInTimeStore):
        self.pit_store = pit_store
    
    def get_universe_at_date(
        self,
        date: datetime,
        universe_name: str = "default",
    ) -> List[str]:
        """Get the set of symbols that were in the universe at a specific date"""
        # Store universe composition as PIT data
        universe_data = self.pit_store.get_data_at_pit(
            symbol=f"UNIVERSE_{universe_name}",
            timestamp=date,
            data_type="universe_composition",
        )
        
        if universe_data:
            return universe_data.data.get('symbols', [])
        
        # Fallback to all symbols if no universe data
        return self.pit_store.get_symbols()
    
    def store_universe_composition(
        self,
        date: datetime,
        symbols: List[str],
        universe_name: str = "default",
    ) -> bool:
        """Store universe composition for a specific date"""
        record = PITRecord(
            symbol=f"UNIVERSE_{universe_name}",
            timestamp=date,
            pit_timestamp=date,  # Universe changes are known immediately
            data_type="universe_composition",
            data={'symbols': symbols, 'count': len(symbols)},
        )
        return self.pit_store.store_record(record)
    
    def get_delisted_symbols(
        self,
        start: datetime,
        end: datetime,
    ) -> List[Tuple[str, datetime]]:
        """Get symbols that were delisted during a period"""
        cursor = self.pit_store._conn.cursor()
        
        cursor.execute("""
            SELECT symbol, timestamp
            FROM pit_records
            WHERE data_type = 'corporate_action'
            AND data LIKE '%"action_type": "DELISTED"%'
            AND timestamp >= ? AND timestamp <= ?
        """, (start.isoformat(), end.isoformat()))
        
        return [(row[0], datetime.fromisoformat(row[1])) for row in cursor.fetchall()]
