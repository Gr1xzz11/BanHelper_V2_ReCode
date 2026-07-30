from __future__ import annotations

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            protocol_version INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            player TEXT NOT NULL,
            moderator TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL,
            reason_raw TEXT NOT NULL DEFAULT '',
            server_mode TEXT NOT NULL CHECK(server_mode IN ('FT','RW')),
            source TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            received_at REAL NOT NULL,
            raw_message TEXT NOT NULL DEFAULT '',
            raw_hover TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','current','confirmed','skipped','deleted'))
        );
        CREATE TABLE IF NOT EXISTS pending_queue (
            event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('current','pending'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_single_current
            ON pending_queue(state) WHERE state = 'current';
        CREATE INDEX IF NOT EXISTS idx_pending_position ON pending_queue(position);
        CREATE TABLE IF NOT EXISTS confirmed_bans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE REFERENCES events(event_id),
            player TEXT NOT NULL,
            reason TEXT NOT NULL,
            server_mode TEXT NOT NULL CHECK(server_mode IN ('FT','RW')),
            report TEXT NOT NULL,
            source TEXT NOT NULL,
            confirmed_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_confirmed_at ON confirmed_bans(confirmed_at DESC);
        CREATE INDEX IF NOT EXISTS idx_confirmed_player ON confirmed_bans(player COLLATE NOCASE);
        CREATE INDEX IF NOT EXISTS idx_confirmed_mode_reason ON confirmed_bans(server_mode, reason);
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS layout_profiles (
            name TEXT PRIMARY KEY,
            geometry BLOB NOT NULL,
            state BLOB NOT NULL,
            locked INTEGER NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS import_sources (
            source_key TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            imported_at REAL NOT NULL,
            added INTEGER NOT NULL,
            skipped INTEGER NOT NULL,
            damaged INTEGER NOT NULL,
            backup_path TEXT NOT NULL DEFAULT ''
        );
        """,
    ),
)
