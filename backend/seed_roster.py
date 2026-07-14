"""
Run from the backend/ directory after the DB has been initialized at least once:
    venv/bin/python seed_roster.py

Safe to re-run — skips players that already exist by name.
Centers are not flagged here since the roster page doesn't specify C/W.
Update is_center manually in the app for whichever forwards take faceoffs.
"""
import sys
sys.path.insert(0, ".")

from app.database import engine, Base, SessionLocal
from app.models import Player

Base.metadata.create_all(bind=engine)

ROSTER = [
    # (name, number, position)
    ("Ainsley Tuffy",     "1",  "G"),
    ("Kaley MacDonald",   "3",  "D"),
    ("Morgan McGathey",   "4",  "F"),
    ("Emi Biotti",        "5",  "D"),
    ("Alex Paulsen",      "7",  "D"),
    ("Bella Finnegan",    "8",  "D"),
    ("Gwyn Lapp",         "9",  "F"),
    ("Angelica Megdanis", "10", "F"),
    ("Emily Hamann",      "11", "F"),
    ("Zoe Boosamra",      "12", "F"),
    ("Carla McSweeney",   "14", "F"),
    ("Keira Ley",         "16", "D"),
    ("Elle Sproule",      "17", "F"),
    ("Brooke Manning",    "19", "F"),
    ("Annie Sun",         "20", "D"),
    ("Scout Oudemool",    "22", "F"),
    ("Maria Pape",        "23", "D"),
    ("Antonina Dinges",   "24", "F"),
    ("Ella Lucia",        "28", "F"),
    ("Izzy Whynot",       "30", "G"),
    ("Hilda Pakarinen",   None, "F"),
    ("Lindsay Stepnowski",None, "F"),
    ("Kate Stuart",       None, "F"),
    ("Serra Yildir",      None, "G"),
]

db = SessionLocal()
existing_names = {p.name for p in db.query(Player).all()}
added = 0

for name, number, position in ROSTER:
    if name in existing_names:
        print(f"  skip (exists): {name}")
        continue
    player = Player(name=name, number=number, position=position, is_center=False, active=True)
    db.add(player)
    added += 1
    print(f"  added: {name} #{number or '—'} ({position})")

db.commit()
db.close()
print(f"\nDone — {added} players added, {len(existing_names)} already existed.")
print("Tip: mark centers manually in the Roster page (is_center flag enables FO% fields).")
