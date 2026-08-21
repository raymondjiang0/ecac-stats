"""Migration v5: add data_source column to games and create InStat-shape tables.

Idempotent: safe to re-run. Uses raw sqlite3 to match project convention
(migrate_v4.py etc.).
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "ecac_stats.db")
con = sqlite3.connect(db_path)
cur = con.cursor()


def try_add_column(table: str, col: str, typ: str, default: str = None):
    ddl = f"ALTER TABLE {table} ADD COLUMN {col} {typ}"
    if default is not None:
        ddl += f" DEFAULT {default}"
    try:
        cur.execute(ddl)
        print(f"Added {col} to {table}.")
    except Exception as e:
        print(f"Skipped {col} ({e})")


# Phase 0: Game.data_source column
try_add_column("games", "data_source", "TEXT", "'49ing'")

# Backfill any NULL data_source values (defensive — the DEFAULT above handles inserts,
# but existing rows created before the column existed can be NULL).
cur.execute("UPDATE games SET data_source = '49ing' WHERE data_source IS NULL")
print(f"Backfilled {cur.rowcount} rows with data_source='49ing'.")

# Phase 0: PlayerGameStatsInStat table
cur.execute("""
    CREATE TABLE IF NOT EXISTS player_game_stats_instat (
        id INTEGER PRIMARY KEY,
        player_id INTEGER NOT NULL REFERENCES players(id),
        game_id INTEGER NOT NULL REFERENCES games(id),
        shots INTEGER, shots_on_goal INTEGER, blocked_shots INTEGER,
        pp_shots INTEGER, pp_shots_on_goal INTEGER,
        corsi_plus INTEGER, corsi_minus INTEGER,
        hits_delivered INTEGER, hits_received INTEGER,
        pb_won_dz INTEGER, pb_total_dz INTEGER,
        pb_won_oz INTEGER, pb_total_oz INTEGER,
        pb_won_nz INTEGER, pb_total_nz INTEGER,
        puck_losses INTEGER, puck_losses_dz INTEGER,
        puck_recoveries INTEGER, puck_recoveries_oz INTEGER,
        entries_pass INTEGER, entries_stick INTEGER, entries_dump INTEGER,
        UNIQUE(player_id, game_id)
    )
""")
print("Created player_game_stats_instat table (or already exists).")

# Phase 0: TeamGameStatsInStat table
cur.execute("""
    CREATE TABLE IF NOT EXISTS team_game_stats_instat (
        id INTEGER PRIMARY KEY,
        game_id INTEGER NOT NULL UNIQUE REFERENCES games(id),
        pp_shots INTEGER,
        pp_time_seconds_in_oz INTEGER,
        pp_time_seconds_total INTEGER,
        pk_opp_breakouts INTEGER,
        pp_opp_breakouts_allowed INTEGER,
        puck_possession_seconds_total INTEGER,
        oz_possession_seconds INTEGER,
        oz_possession_pct REAL,
        scoring_chance_shots INTEGER,
        scoring_chance_shots_on_goal INTEGER
    )
""")
print("Created team_game_stats_instat table (or already exists).")

con.commit()
con.close()
print("Migration v5 complete.")
