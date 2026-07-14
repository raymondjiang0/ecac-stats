"""
Migration v2: add TOI-computation columns and xG-based attack scenario columns.
Run once from backend/ directory:
    venv/bin/python migrate_v2.py
Safe to re-run — skips columns that already exist.
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "ecac_stats.db")

if not os.path.exists(DB_PATH):
    print("Database not found — start the server once first to create it, then re-run.")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Get existing columns in team_game_stats
cur.execute("PRAGMA table_info(team_game_stats)")
existing = {row[1] for row in cur.fetchall()}

new_cols = [
    # TOI decomposition
    ("total_game_time", "REAL DEFAULT 60"),   # total game minutes (60 reg, 65 OT, …)
    ("toi_pp",          "REAL"),              # 5v4 power-play TOI (from DC Team tab)
    ("toi_pk",          "REAL"),              # 4v5 penalty-kill TOI
    ("other_toi",       "REAL DEFAULT 0"),    # other rare strength states
    # Attack scenario xG (replaces old count-based rush_for / rush_against etc.)
    ("rush_xgf",        "REAL"),
    ("oz_fc_xgf",       "REAL"),
    ("oz_fo_xgf",       "REAL"),
    ("sust_pos_xgf",    "REAL"),
]

for col, typedef in new_cols:
    if col in existing:
        print(f"  skip (exists): {col}")
        continue
    cur.execute(f"ALTER TABLE team_game_stats ADD COLUMN {col} {typedef}")
    print(f"  added: {col}")

conn.commit()
conn.close()
print("Done.")
