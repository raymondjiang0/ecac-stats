import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "ecac_stats.db")
con = sqlite3.connect(db_path)
cur = con.cursor()

new_cols = [
    ("player_game_stats", "sf_for",      "REAL"),
    ("player_game_stats", "sf_against",  "REAL"),
    ("player_game_stats", "icf",         "REAL"),
    ("player_game_stats", "isf",         "REAL"),
]

for table, col, typ in new_cols:
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        print(f"Added {col} to {table}.")
    except Exception as e:
        print(f"Skipped {col} ({e})")

con.commit()
con.close()
print("Migration v4 complete.")
