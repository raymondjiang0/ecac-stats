"""Migration v6: add ingest_runs, player_hit_matrix, player_pass_matrix tables.

Idempotent: safe to re-run. Uses raw sqlite3 to match project convention
(migrate_v4.py, migrate_v5.py).
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "ecac_stats.db")
con = sqlite3.connect(db_path)
cur = con.cursor()

# Phase 2: IngestRun table
cur.execute("""
    CREATE TABLE IF NOT EXISTS ingest_runs (
        id INTEGER PRIMARY KEY,
        game_id INTEGER NOT NULL REFERENCES games(id),
        filename TEXT NOT NULL,
        uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        parsed_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_review',
        committed_at DATETIME,
        error TEXT
    )
""")
print("Created ingest_runs table (or already exists).")

# Phase 2: PlayerHitMatrix table
cur.execute("""
    CREATE TABLE IF NOT EXISTS player_hit_matrix (
        id INTEGER PRIMARY KEY,
        game_id INTEGER NOT NULL REFERENCES games(id),
        from_player_id INTEGER NOT NULL REFERENCES players(id),
        to_player_id INTEGER NOT NULL REFERENCES players(id),
        delivered INTEGER NOT NULL DEFAULT 0,
        received INTEGER NOT NULL DEFAULT 0,
        UNIQUE(game_id, from_player_id, to_player_id)
    )
""")
print("Created player_hit_matrix table (or already exists).")

# Phase 2: PlayerPassMatrix table
cur.execute("""
    CREATE TABLE IF NOT EXISTS player_pass_matrix (
        id INTEGER PRIMARY KEY,
        game_id INTEGER NOT NULL REFERENCES games(id),
        from_player_id INTEGER NOT NULL REFERENCES players(id),
        to_player_id INTEGER NOT NULL REFERENCES players(id),
        count INTEGER NOT NULL DEFAULT 0,
        UNIQUE(game_id, from_player_id, to_player_id)
    )
""")
print("Created player_pass_matrix table (or already exists).")

con.commit()
con.close()
print("Migration v6 complete.")
