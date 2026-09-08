"""Migration v7: add player_game_shots_instat table.

Idempotent — matches migrate_v5.py/migrate_v6.py style. Safe to re-run.
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "ecac_stats.db")
con = sqlite3.connect(db_path)
cur = con.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS player_game_shots_instat (
        id INTEGER PRIMARY KEY,
        player_id INTEGER NOT NULL REFERENCES players(id),
        game_id INTEGER NOT NULL REFERENCES games(id),
        goals INTEGER,
        shots_total INTEGER, shots_on_goal INTEGER,
        shots_blocked_defensively INTEGER,
        pp_shots_total INTEGER, pp_shots_on_goal INTEGER,
        sh_shots_total INTEGER, sh_shots_on_goal INTEGER,
        positional_shots_total INTEGER, positional_shots_on_goal INTEGER,
        counter_shots_total INTEGER, counter_shots_on_goal INTEGER,
        slot_shots_total INTEGER, slot_shots_on_goal INTEGER,
        center_shots_total INTEGER, center_shots_on_goal INTEGER,
        right_flank_shots_total INTEGER, right_flank_shots_on_goal INTEGER,
        left_flank_shots_total INTEGER, left_flank_shots_on_goal INTEGER,
        blue_line_right_shots_total INTEGER, blue_line_right_shots_on_goal INTEGER,
        blue_line_center_shots_total INTEGER, blue_line_center_shots_on_goal INTEGER,
        blue_line_left_shots_total INTEGER, blue_line_left_shots_on_goal INTEGER,
        slapshot_total INTEGER, slapshot_on_goal INTEGER,
        wristshot_total INTEGER, wristshot_on_goal INTEGER,
        UNIQUE(player_id, game_id)
    )
""")
print("Created player_game_shots_instat table (or already exists).")

con.commit()
con.close()
print("Migration v7 complete.")
