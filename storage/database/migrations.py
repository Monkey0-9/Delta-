from __future__ import annotations

SCHEMA_VERSION = 3

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS catalog_datasets (
            name TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            parquet_path TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            created_utc TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS bars (
            symbol TEXT NOT NULL,
            ts_utc TEXT NOT NULL,
            open TEXT NOT NULL,
            high TEXT NOT NULL,
            low TEXT NOT NULL,
            close TEXT NOT NULL,
            volume TEXT NOT NULL,
            dataset_hash TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (symbol, ts_utc)
        );
        """,
    ),
    (
        2,
        """
        CREATE TABLE IF NOT EXISTS pit_events (
            event_id TEXT PRIMARY KEY,
            event_time_utc TEXT NOT NULL,
            received_time_utc TEXT NOT NULL,
            effective_time_utc TEXT NOT NULL,
            source TEXT NOT NULL,
            payload TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pit_effective
            ON pit_events (effective_time_utc, event_id);
        """,
    ),
    (
        3,
        """
        CREATE TABLE IF NOT EXISTS corporate_actions (
            symbol TEXT NOT NULL,
            kind TEXT NOT NULL,
            factor TEXT NOT NULL,
            ex_date TEXT NOT NULL,
            PRIMARY KEY (symbol, kind, ex_date)
        );
        CREATE TABLE IF NOT EXISTS trading_sessions (
            exchange TEXT NOT NULL,
            day TEXT NOT NULL,
            open_utc TEXT NOT NULL,
            close_utc TEXT NOT NULL,
            is_half_day INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (exchange, day)
        );
        """,
    ),
)
