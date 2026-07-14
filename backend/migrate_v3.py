import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "ecac_stats.db")
con = sqlite3.connect(db_path)
cur = con.cursor()

try:
    cur.execute("ALTER TABLE win_prob_segments ADD COLUMN xgf_pct REAL")
    print("Added xgf_pct column to win_prob_segments.")
except Exception as e:
    print(f"Skipped (already exists?): {e}")

con.commit()
con.close()
print("Migration v3 complete.")
