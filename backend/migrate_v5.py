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

# (Tables added by Tasks 3 and 4 will extend this file — see those tasks.)

con.commit()
con.close()
print("Migration v5 (Task 2 portion) complete.")
