# Phase 4: Tier 3 Stats (Shot Threat + DDI) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two Tier 3 coach-visible stats — Shot Threat by Scenario (per-player shot breakdowns across strength/location/context/type) and Defensive Disruption Index (composite off-puck defensive proxy) — plus the new InStat shots-page parser + `PlayerGameShotsInStat` table that stores per-player shot data. Also fixes Phase 3's `danger_zone_shot_share` proxy by replacing `r.shots` with true SCA counts (slot + center shots from the new table).

**Architecture:** New pure compute module `app/tier3_stats.py` mirrors Phase 3's `tier2_stats.py` pattern — functions take pre-loaded rows, no DB access. New table `PlayerGameShotsInStat` (~30 columns) holds the InStat shots page (P6/14) data; a new `instat_shots` parser follows Phase 2's parser conventions. `enrich_player_agg` extended with a `shots_rows` kwarg; router loads shots rows and passes them through. Frontend gets one new `ShotThreatBlock` component (static compact view — no filter chips per §9.11 ruling) plus a DDI StatCard pair. Goalie stats (§9.10) explicitly deferred to Phase 4b.

**Tech Stack:** Python 3.9 · SQLAlchemy · SQLite · FastAPI · Pydantic v2 · `pdfplumber` · React + TypeScript + Vite. All Phase 0/1/2/3 infrastructure is prerequisite.

**Spec:** `docs/superpowers/specs/2026-08-18-ecac-stats-expansion-design.md` (§4 templates table, §9.9 DDI, §9.11 Shot Threat, §10 roadmap; 2026-09-06 amendment note).

## Global Constraints

- **Goalie stats explicitly out of scope** — Phase 4b handles §9.10 once per-goalie InStat data is confirmed. Do not add goalie-specific columns, endpoints, or UI in this phase.
- **DDI formula (spec §9.9 ruling):** `DDI/60 = (puck_recoveries + shots_blocked_defensively + DZ puck battles won) × 60 ÷ TOI`. Uses `puck_recoveries` as takeaways proxy (InStat has no takeaways field). Uses new `shots_blocked_defensively` column (NOT the pre-existing `PlayerGameStatsInStat.blocked_shots` which is unpopulated and semantically ambiguous). DZ PB wins from Phase 2's `pb_won_dz`.
- **DDI is all-InStat**: returns None when any component's InStat source is missing. Not partial; UI shows N/A.
- **Shot Threat UI (spec §9.11 ruling):** static compact view — one block per player displaying key breakdowns (Slot, Center, Flank totals, Rush, PP, SH, Slap/Wrist). No filter chips. Filter chips deferred; don't build interaction state.
- **7 location zones** per InStat's PDF classification: `slot`, `center`, `right_flank`, `left_flank`, `blue_line_right`, `blue_line_center`, `blue_line_left`. Not 4.
- **New table `PlayerGameShotsInStat`** — separate from `PlayerGameStatsInStat` (matches Phase 0's pattern of splitting InStat data by page/responsibility). ~30 columns. Unique on `(player_id, game_id)`.
- **Danger-share fix:** update `danger_zone_shot_share` to compute player SCA as `slot_shots_total + center_shots_total` from the new table (per spec §9.6 "shots from scoring chance area" = InStat's slot/center zones). Removes the Phase 3 `r.shots` proxy.
- **Migration script style:** raw `sqlite3`, `CREATE TABLE IF NOT EXISTS`, matches `migrate_v5.py` / `migrate_v6.py`. File name: `backend/migrate_v7.py`.
- **Pydantic v2** (`model_config = {"from_attributes": True}`).
- **Test runner:** `backend/venv/bin/python -m pytest ...` from worktree root. No `pytest` binary — always use `python -m pytest`.
- **Frontend typecheck:** `cd frontend && npx tsc --noEmit` must pass with zero errors after every frontend-touching task.
- **Commit style:** conventional-commits (`feat:`, `test:`, `fix:`, `chore:`).
- **Fixture PDF** — same one Phase 2 uses at `backend/tests/fixtures/instat_sample.pdf`. Harvard's shots page is P14 (0-indexed 13).
- **Existing manual entry preserved** — none of this affects Phase 0/1's flows.
- **No changes to existing computed stats** (except `danger_zone_shot_share` proxy replacement, which is a documented correctness fix, not a formula change).

---

### Task 1: Schema — `PlayerGameShotsInStat` + `migrate_v7`

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/migrate_v7.py`
- Create: `backend/tests/test_shots_schema.py`

**Interfaces:**
- Consumes: existing `Player`, `Game`, `Base` from `app.models`.
- Produces:
  - `PlayerGameShotsInStat` SQLAlchemy model with fields:
    - `id`, `player_id` (FK), `game_id` (FK), unique on `(player_id, game_id)`
    - `goals` (int, nullable)
    - `shots_total`, `shots_on_goal` (int, nullable)
    - `shots_blocked_defensively` (int, nullable) — opponent shots this player blocked
    - `pp_shots_total`, `pp_shots_on_goal` (int, nullable)
    - `sh_shots_total`, `sh_shots_on_goal` (int, nullable)
    - `positional_shots_total`, `positional_shots_on_goal` (int, nullable)
    - `counter_shots_total`, `counter_shots_on_goal` (int, nullable)
    - 7 location pairs (int, nullable): `slot_shots_total`/`_on_goal`, `center_shots_total`/`_on_goal`, `right_flank_shots_total`/`_on_goal`, `left_flank_shots_total`/`_on_goal`, `blue_line_right_shots_total`/`_on_goal`, `blue_line_center_shots_total`/`_on_goal`, `blue_line_left_shots_total`/`_on_goal`
    - 2 type pairs (int, nullable): `slapshot_total`/`_on_goal`, `wristshot_total`/`_on_goal`
  - `PlayerGameShotsInStatOut` Pydantic v2 schema mirroring the model.
  - `migrate_v7.py` — idempotent raw sqlite3 script that creates the table.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_shots_schema.py`:
```python
import pytest
from datetime import date
from app.models import Player, Game, PlayerGameShotsInStat


@pytest.fixture
def player_and_game(db_session):
    p = Player(name="Ten", number="10", position="F", is_center=True, active=True)
    g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True,
             season="2025-26", data_source="instat")
    db_session.add(p)
    db_session.add(g)
    db_session.commit()
    return p, g


class TestPlayerGameShotsInStat:
    def test_can_create_row_with_all_fields(self, db_session, player_and_game):
        p, g = player_and_game
        row = PlayerGameShotsInStat(
            player_id=p.id, game_id=g.id,
            goals=1,
            shots_total=5, shots_on_goal=3,
            shots_blocked_defensively=2,
            pp_shots_total=1, pp_shots_on_goal=1,
            sh_shots_total=0, sh_shots_on_goal=0,
            positional_shots_total=4, positional_shots_on_goal=2,
            counter_shots_total=1, counter_shots_on_goal=1,
            slot_shots_total=2, slot_shots_on_goal=2,
            center_shots_total=1, center_shots_on_goal=1,
            right_flank_shots_total=1, right_flank_shots_on_goal=0,
            left_flank_shots_total=0, left_flank_shots_on_goal=0,
            blue_line_right_shots_total=1, blue_line_right_shots_on_goal=0,
            blue_line_center_shots_total=0, blue_line_center_shots_on_goal=0,
            blue_line_left_shots_total=0, blue_line_left_shots_on_goal=0,
            slapshot_total=1, slapshot_on_goal=1,
            wristshot_total=4, wristshot_on_goal=2,
        )
        db_session.add(row)
        db_session.commit()
        assert row.id is not None

    def test_all_fields_default_none(self, db_session, player_and_game):
        p, g = player_and_game
        row = PlayerGameShotsInStat(player_id=p.id, game_id=g.id)
        db_session.add(row)
        db_session.commit()
        assert row.goals is None
        assert row.shots_total is None
        assert row.slot_shots_total is None
        assert row.slapshot_total is None

    def test_unique_player_game(self, db_session, player_and_game):
        from sqlalchemy.exc import IntegrityError
        p, g = player_and_game
        db_session.add(PlayerGameShotsInStat(player_id=p.id, game_id=g.id, goals=1))
        db_session.commit()
        db_session.add(PlayerGameShotsInStat(player_id=p.id, game_id=g.id, goals=2))
        with pytest.raises(IntegrityError):
            db_session.commit()
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_shots_schema.py -v`
Expected: `ImportError: cannot import name 'PlayerGameShotsInStat'`.

- [ ] **Step 3: Add the model**

Append to `backend/app/models.py`:

```python
class PlayerGameShotsInStat(Base):
    __tablename__ = "player_game_shots_instat"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)

    __table_args__ = (UniqueConstraint("player_id", "game_id"),)

    # Basic
    goals = Column(Integer, nullable=True)
    shots_total = Column(Integer, nullable=True)
    shots_on_goal = Column(Integer, nullable=True)

    # Defensive — opponent shots this player blocked. Distinct from
    # PlayerGameStatsInStat.blocked_shots (which is unpopulated and
    # semantically means "shots this player took that got blocked").
    shots_blocked_defensively = Column(Integer, nullable=True)

    # Strength-state
    pp_shots_total = Column(Integer, nullable=True)
    pp_shots_on_goal = Column(Integer, nullable=True)
    sh_shots_total = Column(Integer, nullable=True)
    sh_shots_on_goal = Column(Integer, nullable=True)

    # Context
    positional_shots_total = Column(Integer, nullable=True)
    positional_shots_on_goal = Column(Integer, nullable=True)
    counter_shots_total = Column(Integer, nullable=True)
    counter_shots_on_goal = Column(Integer, nullable=True)

    # Location — 7 zones per InStat's PDF classification
    slot_shots_total = Column(Integer, nullable=True)
    slot_shots_on_goal = Column(Integer, nullable=True)
    center_shots_total = Column(Integer, nullable=True)
    center_shots_on_goal = Column(Integer, nullable=True)
    right_flank_shots_total = Column(Integer, nullable=True)
    right_flank_shots_on_goal = Column(Integer, nullable=True)
    left_flank_shots_total = Column(Integer, nullable=True)
    left_flank_shots_on_goal = Column(Integer, nullable=True)
    blue_line_right_shots_total = Column(Integer, nullable=True)
    blue_line_right_shots_on_goal = Column(Integer, nullable=True)
    blue_line_center_shots_total = Column(Integer, nullable=True)
    blue_line_center_shots_on_goal = Column(Integer, nullable=True)
    blue_line_left_shots_total = Column(Integer, nullable=True)
    blue_line_left_shots_on_goal = Column(Integer, nullable=True)

    # Shot type
    slapshot_total = Column(Integer, nullable=True)
    slapshot_on_goal = Column(Integer, nullable=True)
    wristshot_total = Column(Integer, nullable=True)
    wristshot_on_goal = Column(Integer, nullable=True)

    player = relationship("Player")
    game = relationship("Game")
```

- [ ] **Step 4: Add Pydantic schema**

Append to `backend/app/schemas.py`:

```python
class PlayerGameShotsInStatOut(BaseModel):
    id: Optional[int] = None
    player_id: int
    game_id: int
    goals: Optional[int] = None
    shots_total: Optional[int] = None
    shots_on_goal: Optional[int] = None
    shots_blocked_defensively: Optional[int] = None
    pp_shots_total: Optional[int] = None
    pp_shots_on_goal: Optional[int] = None
    sh_shots_total: Optional[int] = None
    sh_shots_on_goal: Optional[int] = None
    positional_shots_total: Optional[int] = None
    positional_shots_on_goal: Optional[int] = None
    counter_shots_total: Optional[int] = None
    counter_shots_on_goal: Optional[int] = None
    slot_shots_total: Optional[int] = None
    slot_shots_on_goal: Optional[int] = None
    center_shots_total: Optional[int] = None
    center_shots_on_goal: Optional[int] = None
    right_flank_shots_total: Optional[int] = None
    right_flank_shots_on_goal: Optional[int] = None
    left_flank_shots_total: Optional[int] = None
    left_flank_shots_on_goal: Optional[int] = None
    blue_line_right_shots_total: Optional[int] = None
    blue_line_right_shots_on_goal: Optional[int] = None
    blue_line_center_shots_total: Optional[int] = None
    blue_line_center_shots_on_goal: Optional[int] = None
    blue_line_left_shots_total: Optional[int] = None
    blue_line_left_shots_on_goal: Optional[int] = None
    slapshot_total: Optional[int] = None
    slapshot_on_goal: Optional[int] = None
    wristshot_total: Optional[int] = None
    wristshot_on_goal: Optional[int] = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_shots_schema.py -v`
Expected: 3 tests pass.

- [ ] **Step 6: Write migration**

Create `backend/migrate_v7.py`:
```python
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
```

- [ ] **Step 7: Verify migration idempotency**

Run twice against a scratch copy of the DB — second run should not error.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/migrate_v7.py backend/tests/test_shots_schema.py
git commit -m "feat: add PlayerGameShotsInStat table (migration v7)"
```

---

### Task 2: Parser — `instat_shots` (P6/14)

**Files:**
- Create: `backend/app/ingest/parsers/shots.py`
- Create: `backend/tests/test_parse_shots.py`

**Interfaces:**
- Consumes: `find_section_page` from `..pdf_nav`; also needs a new `SHOTS_SECTION` string constant added to `pdf_nav.py`.
- Produces:
  - `parse_shots(pdf: pdfplumber.PDF, our_team: str) -> list[dict]` — one dict per player row. Each dict has: `jersey_number: str`, `player_name: str`, plus optional int fields matching all 29 `PlayerGameShotsInStat` data columns (goals, shots_total, shots_on_goal, shots_blocked_defensively, pp_/sh_/positional_/counter_ pairs, 7 location pairs, 2 type pairs).
  - Constant `SHOTS_SECTION = "SHOTS"` added to `backend/app/ingest/pdf_nav.py`.

**Discovery guidance:** P14 header is:
```
Goals Shots / on goal Shots blocking Power play Short-handed In positional attacks In counter-attacks Slot Center Right flank Left flank Blue line right Blue line center Blue line left Slapshot Wrist shot
```

Data row example (Finnegan, #8):
```
8 Finnegan — 5/3 60% 4 — — 4/3 75% — — 1/1 100% — — 2/1 50% — 2/1 50% 4/3 75% —
```

Column layout per row (after jersey + name):
1. Goals — single int or `—` (None)
2. Shots (total) / on-goal % — `x/y z%` triplet (percentage optional — parse into shots_total, shots_on_goal, discard %)
3. Shots blocking — single int or `—`
4-15. Twelve `x/y z%` pairs for: Power play, Short-handed, positional, counter, slot, center, right flank, left flank, BL right, BL center, BL left
16. Slapshot — `x/y z%`
17. Wrist shot — `x/y z%`

Total 13 `x/y%` pairs + goals + shots_blocking + jersey/name.

Reuse the `_parse_won_total`-style helper pattern from `challenges.py` for `x/y` extraction — but adapt to handle trailing `%` (throw away the %).

- [ ] **Step 1: Add section constant to pdf_nav.py**

Modify `backend/app/ingest/pdf_nav.py` — add near the other section constants:
```python
SHOTS_SECTION = "SHOTS"           # team-scoped
```

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_parse_shots.py`:
```python
import os
import pytest
import pdfplumber
from app.ingest.parsers.shots import parse_shots

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseShots:
    def test_returns_list_of_dicts(self, pdf):
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_reasonable_row_count(self, pdf):
        # Harvard fixture has ~16 skaters
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        assert 10 <= len(rows) <= 25, f"got {len(rows)} rows"

    def test_each_row_has_jersey_and_name(self, pdf):
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        for r in rows:
            assert "jersey_number" in r and isinstance(r["jersey_number"], str)
            assert "player_name" in r and isinstance(r["player_name"], str)

    def test_expected_fields_present_or_none(self, pdf):
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        expected_keys = {
            "goals", "shots_total", "shots_on_goal", "shots_blocked_defensively",
            "pp_shots_total", "pp_shots_on_goal",
            "sh_shots_total", "sh_shots_on_goal",
            "positional_shots_total", "positional_shots_on_goal",
            "counter_shots_total", "counter_shots_on_goal",
            "slot_shots_total", "slot_shots_on_goal",
            "center_shots_total", "center_shots_on_goal",
            "right_flank_shots_total", "right_flank_shots_on_goal",
            "left_flank_shots_total", "left_flank_shots_on_goal",
            "blue_line_right_shots_total", "blue_line_right_shots_on_goal",
            "blue_line_center_shots_total", "blue_line_center_shots_on_goal",
            "blue_line_left_shots_total", "blue_line_left_shots_on_goal",
            "slapshot_total", "slapshot_on_goal",
            "wristshot_total", "wristshot_on_goal",
        }
        for r in rows:
            for k in expected_keys:
                assert k in r, f"missing key {k} in row {r['player_name']}"
                assert r[k] is None or isinstance(r[k], int), (
                    f"{r['player_name']} {k}={r[k]!r} not int/None"
                )

    def test_shots_on_goal_never_exceeds_shots_total(self, pdf):
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        pair_prefixes = [
            "shots", "pp_shots", "sh_shots",
            "positional_shots", "counter_shots",
            "slot_shots", "center_shots",
            "right_flank_shots", "left_flank_shots",
            "blue_line_right_shots", "blue_line_center_shots", "blue_line_left_shots",
            "slapshot", "wristshot",
        ]
        for r in rows:
            for prefix in pair_prefixes:
                # shots_total maps to shots + _total, but shots itself is special
                total_key = f"{prefix}_total" if prefix != "shots" else "shots_total"
                on_goal_key = f"{prefix}_on_goal"
                t, og = r.get(total_key), r.get(on_goal_key)
                if t is not None and og is not None:
                    assert og <= t, f"{r['player_name']} {on_goal_key}={og} > {total_key}={t}"

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_shots(pdf, our_team="NONEXISTENT TEAM") == []

    def test_at_least_one_populated_field(self, pdf):
        # Guard against silent all-None parse
        rows = parse_shots(pdf, our_team="HARVARD CRIMSON")
        populated_counts = [
            sum(1 for k, v in r.items() if v is not None and k not in ("jersey_number", "player_name"))
            for r in rows
        ]
        assert max(populated_counts) >= 3, "no row has >=3 populated numeric fields"
```

- [ ] **Step 3: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_shots.py -v`
Expected: `ImportError`.

- [ ] **Step 4: Implement the parser**

Create `backend/app/ingest/parsers/shots.py`:
```python
"""Parser for InStat's SHOTS page (P6 for visitor, P14 for home).

Layout: per-player row with:
- jersey + name
- Goals (single int)
- Shots (total) / on-goal (with %)
- Shots blocking (single int — defensive blocks)
- 13 x/y% pairs for: PP, SH, positional attacks, counter attacks,
  slot, center, right flank, left flank, blue line right/center/left,
  slapshot, wrist shot

Returns a list of dicts, one per player. Missing values are None
(rendered as em-dash in the PDF).
"""
from __future__ import annotations
import re
import pdfplumber
from ..pdf_nav import find_section_page, SHOTS_SECTION


# Order of x/y% pair columns after "Shots blocking":
# Power play, Short-handed, In positional attacks, In counter-attacks,
# Slot, Center, Right flank, Left flank,
# Blue line right, Blue line center, Blue line left,
# Slapshot, Wrist shot
_PAIR_COLUMNS = [
    ("pp_shots_total", "pp_shots_on_goal"),
    ("sh_shots_total", "sh_shots_on_goal"),
    ("positional_shots_total", "positional_shots_on_goal"),
    ("counter_shots_total", "counter_shots_on_goal"),
    ("slot_shots_total", "slot_shots_on_goal"),
    ("center_shots_total", "center_shots_on_goal"),
    ("right_flank_shots_total", "right_flank_shots_on_goal"),
    ("left_flank_shots_total", "left_flank_shots_on_goal"),
    ("blue_line_right_shots_total", "blue_line_right_shots_on_goal"),
    ("blue_line_center_shots_total", "blue_line_center_shots_on_goal"),
    ("blue_line_left_shots_total", "blue_line_left_shots_on_goal"),
    ("slapshot_total", "slapshot_on_goal"),
    ("wristshot_total", "wristshot_on_goal"),
]


def parse_shots(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    page_idx = find_section_page(pdf, SHOTS_SECTION, our_team)
    if page_idx is None:
        return []
    text = pdf.pages[page_idx].extract_text() or ""
    return _extract_shot_rows(text)


def _extract_shot_rows(text: str) -> list[dict]:
    """Parse per-player rows from the text-extracted SHOTS page.

    Implementer: walk the lines after the header. A player row starts
    with `<jersey> <name>` and has the tokens documented above. Use
    _empty_row() as a template and populate what parses cleanly.

    Tests require: 10-25 rows, jersey/name as strings, all 30 expected
    keys present (int-or-None), shots_on_goal <= shots_total invariant
    per pair, at least one row with >=3 populated numeric fields, and
    [] for unknown team.
    """
    # ... implementer fills in extraction here ...
    return []


def _empty_row() -> dict:
    row = {"jersey_number": "", "player_name": ""}
    for k in ("goals", "shots_total", "shots_on_goal", "shots_blocked_defensively"):
        row[k] = None
    for total_key, on_goal_key in _PAIR_COLUMNS:
        row[total_key] = None
        row[on_goal_key] = None
    return row


def _parse_x_y_pair(tokens: list[str], idx: int) -> tuple[int | None, int | None, int]:
    """Parse one 'x/y' or 'x/y z%' pair starting at tokens[idx].

    Returns (x, y, new_idx). Handles bare em-dash (returns None, None, idx+1).
    Advances past the optional '%' token.
    """
    if idx >= len(tokens):
        return None, None, idx
    tok = tokens[idx]
    if tok in ("—", "-"):
        return None, None, idx + 1
    m = re.match(r"^(\d+)/(\d+)$", tok)
    if not m:
        return None, None, idx + 1
    x, y = int(m.group(1)), int(m.group(2))
    new_idx = idx + 1
    # Consume optional '%' token
    if new_idx < len(tokens) and tokens[new_idx].endswith("%"):
        new_idx += 1
    return x, y, new_idx


def _parse_int_or_none(tok: str) -> int | None:
    if tok in ("—", "-"):
        return None
    try:
        return int(tok)
    except ValueError:
        return None
```

Note: the `_extract_shot_rows` body is left as a discovery-guided implementation. The tests dictate acceptance. Implementer should REPL-inspect page 14 of the fixture, walk each line's tokens, and populate rows using `_empty_row()` + `_parse_x_y_pair()` + `_parse_int_or_none()`.

- [ ] **Step 5: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_shots.py -v`
Expected: 7 tests pass. If any fail with "no row has ≥3 populated fields," return to Step 4 and expand `_extract_shot_rows`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ingest/pdf_nav.py backend/app/ingest/parsers/shots.py backend/tests/test_parse_shots.py
git commit -m "feat: add InStat shots-page PDF parser (P6/14)"
```

---

### Task 3: Template registry + commit-layer wiring

**Files:**
- Modify: `backend/app/ingest/templates.py`
- Modify: `backend/app/ingest/commit.py`
- Modify: `backend/tests/test_orchestrator.py` (add test asserting new template present)
- Modify: `backend/tests/test_ingest_commit.py` (add test for shots commit)

**Interfaces:**
- Consumes: `parse_shots` from Task 2; `PlayerGameShotsInStat` from Task 1.
- Produces:
  - `TEMPLATES` dict in `templates.py` gains `"instat_shots": parse_shots` entry.
  - `commit_parsed` in `commit.py` gains a per-player upsert block that writes `PlayerGameShotsInStat` rows keyed by `(game_id, player_id)`. Unknown-jersey rows are skipped with warnings, matching Phase 2's pattern.
  - `wrote` return dict gains `"instat_shots": row_count` key.

- [ ] **Step 1: Extend TEMPLATES registry**

Modify `backend/app/ingest/templates.py`:
```python
from .parsers.shots import parse_shots
# ...
TEMPLATES = {
    "instat_team_stats": parse_team_stats,
    "instat_players_main": parse_players_main,
    "instat_time_distribution": parse_time_distribution,
    "instat_challenges": parse_challenges,
    "instat_hit_matrix": parse_hit_matrix,
    "instat_pass_matrix": parse_pass_matrix,
    "instat_shots": parse_shots,
}
```

- [ ] **Step 2: Update the orchestrator test**

Modify `backend/tests/test_orchestrator.py` — locate `TestTemplates.test_has_all_six_templates` and rename to `test_has_all_seven_templates`; update the expected set:
```python
def test_has_all_seven_templates(self):
    expected = {
        "instat_team_stats", "instat_players_main", "instat_time_distribution",
        "instat_challenges", "instat_hit_matrix", "instat_pass_matrix",
        "instat_shots",
    }
    assert set(TEMPLATES.keys()) == expected
```

Also update `TestParseAll.test_returns_dict_with_all_templates` — same set expansion.

Run: `backend/venv/bin/python -m pytest backend/tests/test_orchestrator.py -v`
Expected: tests pass with the new template.

- [ ] **Step 3: Extend commit_parsed**

Modify `backend/app/ingest/commit.py`:

Add `PlayerGameShotsInStat` to the top-level model import:
```python
from ..models import (
    Player, TeamGameStatsInStat, PlayerGameStatsInStat,
    PlayerGameStats, PlayerHitMatrix, PlayerPassMatrix,
    PlayerGameShotsInStat,
)
```

Add a new block inside `commit_parsed`, after the `instat_hit_matrix` and `instat_pass_matrix` blocks:

```python
# instat_shots: upsert per player row into PlayerGameShotsInStat
for row in templates.get("instat_shots") or []:
    player = roster.get(str(row.get("jersey_number", "")).strip())
    if player is None:
        skipped.append(
            f"shots: jersey {row.get('jersey_number')!r} not in roster"
        )
        continue
    existing = db_session.query(PlayerGameShotsInStat).filter_by(
        game_id=game_id, player_id=player.id
    ).one_or_none()
    if existing is None:
        existing = PlayerGameShotsInStat(game_id=game_id, player_id=player.id)
        db_session.add(existing)
    for k in ("goals", "shots_total", "shots_on_goal",
              "shots_blocked_defensively",
              "pp_shots_total", "pp_shots_on_goal",
              "sh_shots_total", "sh_shots_on_goal",
              "positional_shots_total", "positional_shots_on_goal",
              "counter_shots_total", "counter_shots_on_goal",
              "slot_shots_total", "slot_shots_on_goal",
              "center_shots_total", "center_shots_on_goal",
              "right_flank_shots_total", "right_flank_shots_on_goal",
              "left_flank_shots_total", "left_flank_shots_on_goal",
              "blue_line_right_shots_total", "blue_line_right_shots_on_goal",
              "blue_line_center_shots_total", "blue_line_center_shots_on_goal",
              "blue_line_left_shots_total", "blue_line_left_shots_on_goal",
              "slapshot_total", "slapshot_on_goal",
              "wristshot_total", "wristshot_on_goal"):
        if k in row:
            setattr(existing, k, row[k])
    wrote["instat_shots"] += 1
```

Ensure `wrote` initialization stays `{name: 0 for name in templates}` — the new template auto-appears in the wrote dict since it comes from `templates.keys()`.

- [ ] **Step 4: Add commit test for shots**

Modify `backend/tests/test_ingest_commit.py` — add a new test method to the `TestCommitParsed` class:

```python
def test_writes_shots(self, db_session, game_and_players):
    from app.models import PlayerGameShotsInStat
    g, p10, p7 = game_and_players
    parsed = {
        "templates": {
            "instat_team_stats": _empty_team(),
            "instat_players_main": [], "instat_time_distribution": [],
            "instat_challenges": [], "instat_hit_matrix": [], "instat_pass_matrix": [],
            "instat_shots": [
                {"jersey_number": "10", "player_name": "Ten",
                 "goals": 1, "shots_total": 5, "shots_on_goal": 3,
                 "shots_blocked_defensively": 2,
                 "slot_shots_total": 2, "slot_shots_on_goal": 2,
                 "wristshot_total": 4, "wristshot_on_goal": 2},
            ],
        },
        "warnings": [],
    }
    report = commit_parsed(parsed, g.id, db_session)
    assert report["wrote"]["instat_shots"] == 1
    row = db_session.query(PlayerGameShotsInStat).filter_by(game_id=g.id).one()
    assert row.player_id == p10.id
    assert row.goals == 1
    assert row.shots_total == 5
    assert row.slot_shots_total == 2
```

- [ ] **Step 5: Run all affected tests**

Run: `backend/venv/bin/python -m pytest backend/tests/test_orchestrator.py backend/tests/test_ingest_commit.py -v`
Expected: all pass, including 1 new commit test.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ingest/templates.py backend/app/ingest/commit.py backend/tests/test_orchestrator.py backend/tests/test_ingest_commit.py
git commit -m "feat: wire instat_shots template into registry + commit layer"
```

---

### Task 4: `shot_threat_by_scenario` compute function

**Files:**
- Create: `backend/app/tier3_stats.py`
- Create: `backend/tests/test_shot_threat.py`

**Interfaces:**
- Consumes: `PlayerGameShotsInStat` rows (per-player-per-game); `PlayerGameStats` rows (for TOI).
- Produces:
  - `shot_threat_by_scenario(shots_rows: list, pgs_rows: list) -> dict` — returns:
    ```python
    {
      "totals": {
        "goals": int, "shots": int, "shots_on_goal": int,
        "toi_5v5_minutes": float,
      },
      "by_strength": {
        "5v5": {"shots": int, "on_goal": int, "shots_per_60": float | None, "on_goal_pct": float | None},
        "pp":  {"shots": int, "on_goal": int, "shots_per_60": float | None, "on_goal_pct": float | None},
        "sh":  {"shots": int, "on_goal": int, "shots_per_60": float | None, "on_goal_pct": float | None},
      },
      "by_context": {
        "positional": {"shots": int, "on_goal": int, "on_goal_pct": float | None},
        "counter":    {"shots": int, "on_goal": int, "on_goal_pct": float | None},
      },
      "by_location": {
        "slot":              {"shots": int, "on_goal": int, "on_goal_pct": float | None},
        "center":            {...}, "right_flank": {...}, "left_flank": {...},
        "blue_line_right":   {...}, "blue_line_center": {...}, "blue_line_left": {...},
      },
      "by_type": {
        "slapshot":  {"shots": int, "on_goal": int, "on_goal_pct": float | None},
        "wristshot": {...},
      },
      "games": int,
    }
    ```
  - `shots_per_60` computed against total 5v5 TOI from pgs_rows for the 5v5 breakdown; PP/SH TOI comes from pgs_rows.toi_pp/toi_sh (in minutes, so × 60/60 = ratio to per-hour is `shots × 60 / TOI_minutes` — TOI is already in minutes per the model).
  - Empty inputs return the shape with zeros / None / `games: 0`.

**Note:** `PlayerGameStats.toi_5v5`, `toi_pp`, `toi_sh` are stored as **minutes** (per commit-layer conversion). `shots_per_60 = shots × 60 / total_minutes`.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_shot_threat.py`:
```python
import pytest
from app.tier3_stats import shot_threat_by_scenario
from app.models import PlayerGameShotsInStat, PlayerGameStats


def _shots(game_id=1, **kwargs):
    r = PlayerGameShotsInStat(player_id=1, game_id=game_id)
    for k, v in kwargs.items():
        setattr(r, k, v)
    return r


def _pgs(game_id=1, toi_5v5=15.0, toi_pp=2.0, toi_sh=1.0):
    r = PlayerGameStats(player_id=1, game_id=game_id)
    r.toi_5v5 = toi_5v5
    r.toi_pp = toi_pp
    r.toi_sh = toi_sh
    return r


class TestShotThreatByScenario:
    def test_empty_returns_zero_shape(self):
        r = shot_threat_by_scenario([], [])
        assert r["games"] == 0
        assert r["totals"]["shots"] == 0
        assert r["by_strength"]["5v5"]["shots"] == 0
        assert r["by_strength"]["5v5"]["shots_per_60"] is None

    def test_single_game_totals(self):
        shots = [_shots(goals=1, shots_total=5, shots_on_goal=3,
                        pp_shots_total=1, pp_shots_on_goal=1,
                        slot_shots_total=2, slot_shots_on_goal=2,
                        wristshot_total=4, wristshot_on_goal=2)]
        pgs = [_pgs()]
        r = shot_threat_by_scenario(shots, pgs)
        assert r["totals"]["goals"] == 1
        assert r["totals"]["shots"] == 5
        assert r["totals"]["shots_on_goal"] == 3
        assert r["totals"]["toi_5v5_minutes"] == pytest.approx(15.0)
        assert r["games"] == 1

    def test_by_strength_split(self):
        shots = [_shots(shots_total=5, shots_on_goal=3,
                        pp_shots_total=1, pp_shots_on_goal=1,
                        sh_shots_total=0, sh_shots_on_goal=0)]
        pgs = [_pgs(toi_5v5=10.0, toi_pp=2.0, toi_sh=1.0)]
        r = shot_threat_by_scenario(shots, pgs)
        # 5v5 shots = total - pp - sh = 5 - 1 - 0 = 4
        assert r["by_strength"]["5v5"]["shots"] == 4
        assert r["by_strength"]["5v5"]["on_goal"] == 2  # 3 - 1 - 0
        # shots_per_60 at 5v5 = 4 * 60 / 10.0 = 24.0
        assert r["by_strength"]["5v5"]["shots_per_60"] == pytest.approx(24.0)
        assert r["by_strength"]["pp"]["shots_per_60"] == pytest.approx(30.0)  # 1*60/2
        assert r["by_strength"]["sh"]["shots"] == 0
        assert r["by_strength"]["sh"]["shots_per_60"] is None  # zero shots

    def test_by_location(self):
        shots = [_shots(slot_shots_total=3, slot_shots_on_goal=2,
                        center_shots_total=1, center_shots_on_goal=1,
                        right_flank_shots_total=2, right_flank_shots_on_goal=1)]
        pgs = [_pgs()]
        r = shot_threat_by_scenario(shots, pgs)
        assert r["by_location"]["slot"]["shots"] == 3
        assert r["by_location"]["slot"]["on_goal"] == 2
        assert r["by_location"]["slot"]["on_goal_pct"] == pytest.approx(2/3)
        assert r["by_location"]["center"]["shots"] == 1
        assert r["by_location"]["right_flank"]["on_goal_pct"] == pytest.approx(0.5)
        # Unpopulated location returns 0 shots + None pct
        assert r["by_location"]["left_flank"]["shots"] == 0
        assert r["by_location"]["left_flank"]["on_goal_pct"] is None

    def test_by_context(self):
        shots = [_shots(positional_shots_total=3, positional_shots_on_goal=2,
                        counter_shots_total=1, counter_shots_on_goal=1)]
        r = shot_threat_by_scenario(shots, [_pgs()])
        assert r["by_context"]["positional"]["shots"] == 3
        assert r["by_context"]["counter"]["shots"] == 1

    def test_by_type(self):
        shots = [_shots(slapshot_total=1, slapshot_on_goal=1,
                        wristshot_total=4, wristshot_on_goal=2)]
        r = shot_threat_by_scenario(shots, [_pgs()])
        assert r["by_type"]["slapshot"]["shots"] == 1
        assert r["by_type"]["wristshot"]["on_goal_pct"] == pytest.approx(0.5)

    def test_multi_game_aggregates(self):
        shots = [_shots(game_id=1, shots_total=3, shots_on_goal=2, slot_shots_total=2, slot_shots_on_goal=2),
                 _shots(game_id=2, shots_total=4, shots_on_goal=3, slot_shots_total=1, slot_shots_on_goal=1)]
        pgs = [_pgs(game_id=1, toi_5v5=15.0), _pgs(game_id=2, toi_5v5=20.0)]
        r = shot_threat_by_scenario(shots, pgs)
        assert r["totals"]["shots"] == 7
        assert r["totals"]["toi_5v5_minutes"] == pytest.approx(35.0)
        assert r["by_location"]["slot"]["shots"] == 3
        assert r["games"] == 2

    def test_no_toi_returns_none_rates(self):
        shots = [_shots(shots_total=5, shots_on_goal=3)]
        pgs = [_pgs(toi_5v5=0.0, toi_pp=0.0, toi_sh=0.0)]
        r = shot_threat_by_scenario(shots, pgs)
        assert r["by_strength"]["5v5"]["shots_per_60"] is None
        assert r["by_strength"]["pp"]["shots_per_60"] is None
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_shot_threat.py -v`
Expected: `ImportError: No module named 'app.tier3_stats'`.

- [ ] **Step 3: Implement**

Create `backend/app/tier3_stats.py`:
```python
"""Tier 3 stat computations — Shot Threat by Scenario, Defensive Disruption Index.

All functions are PURE — take pre-loaded rows, return dicts. See spec §9.9
and §9.11 for formulas.

Goalie stats (§9.10) are deferred to Phase 4b.
"""
from typing import Optional


_LOCATIONS = [
    "slot", "center", "right_flank", "left_flank",
    "blue_line_right", "blue_line_center", "blue_line_left",
]
_TYPES = ["slapshot", "wristshot"]


def _pct(numer: int, denom: int) -> Optional[float]:
    return (numer / denom) if denom > 0 else None


def _per60(count: int, toi_minutes: float) -> Optional[float]:
    if toi_minutes <= 0 or count == 0:
        return None
    return count * 60.0 / toi_minutes


def shot_threat_by_scenario(shots_rows: list, pgs_rows: list) -> dict:
    """Aggregate a player's shots across strength / context / location / type (§9.11).

    Returns nested dict keyed by axis; each cell has shots/on_goal counts,
    on_goal_pct, and (for strength) shots_per_60 vs the corresponding TOI.

    Games with any PlayerGameShotsInStat data count; TOI is summed from
    PlayerGameStats rows (matching game_ids).
    """
    total_shots = 0
    total_on_goal = 0
    total_goals = 0
    pp_shots = pp_on = 0
    sh_shots = sh_on = 0
    positional_shots = positional_on = 0
    counter_shots = counter_on = 0
    loc_shots = {loc: 0 for loc in _LOCATIONS}
    loc_on = {loc: 0 for loc in _LOCATIONS}
    type_shots = {t: 0 for t in _TYPES}
    type_on = {t: 0 for t in _TYPES}
    games = 0

    for r in shots_rows:
        has_data = any(
            getattr(r, k, None) not in (None, 0)
            for k in ("goals", "shots_total", "shots_on_goal",
                      "pp_shots_total", "sh_shots_total")
        )
        if has_data:
            games += 1
        total_goals += r.goals or 0
        total_shots += r.shots_total or 0
        total_on_goal += r.shots_on_goal or 0
        pp_shots += r.pp_shots_total or 0
        pp_on += r.pp_shots_on_goal or 0
        sh_shots += r.sh_shots_total or 0
        sh_on += r.sh_shots_on_goal or 0
        positional_shots += r.positional_shots_total or 0
        positional_on += r.positional_shots_on_goal or 0
        counter_shots += r.counter_shots_total or 0
        counter_on += r.counter_shots_on_goal or 0
        for loc in _LOCATIONS:
            loc_shots[loc] += getattr(r, f"{loc}_shots_total", None) or 0
            loc_on[loc] += getattr(r, f"{loc}_shots_on_goal", None) or 0
        for t in _TYPES:
            type_shots[t] += getattr(r, f"{t}_total", None) or 0
            type_on[t] += getattr(r, f"{t}_on_goal", None) or 0

    # 5v5 = total - pp - sh (assumption: total is all-strength)
    fv_shots = max(0, total_shots - pp_shots - sh_shots)
    fv_on = max(0, total_on_goal - pp_on - sh_on)

    toi_5v5 = sum((p.toi_5v5 or 0) for p in pgs_rows)
    toi_pp = sum((p.toi_pp or 0) for p in pgs_rows)
    toi_sh = sum((p.toi_sh or 0) for p in pgs_rows)

    return {
        "totals": {
            "goals": total_goals,
            "shots": total_shots,
            "shots_on_goal": total_on_goal,
            "toi_5v5_minutes": toi_5v5,
        },
        "by_strength": {
            "5v5": {"shots": fv_shots, "on_goal": fv_on,
                    "shots_per_60": _per60(fv_shots, toi_5v5),
                    "on_goal_pct": _pct(fv_on, fv_shots)},
            "pp": {"shots": pp_shots, "on_goal": pp_on,
                   "shots_per_60": _per60(pp_shots, toi_pp),
                   "on_goal_pct": _pct(pp_on, pp_shots)},
            "sh": {"shots": sh_shots, "on_goal": sh_on,
                   "shots_per_60": _per60(sh_shots, toi_sh),
                   "on_goal_pct": _pct(sh_on, sh_shots)},
        },
        "by_context": {
            "positional": {"shots": positional_shots, "on_goal": positional_on,
                           "on_goal_pct": _pct(positional_on, positional_shots)},
            "counter": {"shots": counter_shots, "on_goal": counter_on,
                        "on_goal_pct": _pct(counter_on, counter_shots)},
        },
        "by_location": {
            loc: {"shots": loc_shots[loc], "on_goal": loc_on[loc],
                  "on_goal_pct": _pct(loc_on[loc], loc_shots[loc])}
            for loc in _LOCATIONS
        },
        "by_type": {
            t: {"shots": type_shots[t], "on_goal": type_on[t],
                "on_goal_pct": _pct(type_on[t], type_shots[t])}
            for t in _TYPES
        },
        "games": games,
    }
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_shot_threat.py -v`
Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tier3_stats.py backend/tests/test_shot_threat.py
git commit -m "feat: add shot_threat_by_scenario tier3 stat function"
```

---

### Task 5: `defensive_disruption_index` compute function

**Files:**
- Modify: `backend/app/tier3_stats.py`
- Create: `backend/tests/test_ddi.py`

**Interfaces:**
- Consumes: `PlayerGameStats` rows (for TOI); `PlayerGameStatsInStat` rows (for `puck_recoveries` and `pb_won_dz`); `PlayerGameShotsInStat` rows (for `shots_blocked_defensively`).
- Produces:
  - `defensive_disruption_index(pgs_rows, instat_rows, shots_rows) -> dict` — returns:
    ```python
    {
      "ddi_per_60": float | None,  # (recoveries + blocks + dz_pb_wins) × 60 / total_toi_minutes
      "components": {
        "puck_recoveries": int,
        "shots_blocked_defensively": int,
        "dz_pb_wins": int,
      },
      "total_toi_minutes": float,
      "games": int,
    }
    ```
  - `ddi_per_60` returns None when total_toi is 0 or when ANY of the three InStat components has no data (all rows None for that field across the window). This enforces the "all-InStat, returns None if incomplete" rule.

**Detection of "any component's InStat source is missing":** For each component, track whether at least one row provided a value (int, not None). If for any component no row had data, return None.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_ddi.py`:
```python
import pytest
from app.tier3_stats import defensive_disruption_index
from app.models import PlayerGameStats, PlayerGameStatsInStat, PlayerGameShotsInStat


def _pgs(game_id=1, toi_5v5=15.0):
    r = PlayerGameStats(player_id=1, game_id=game_id)
    r.toi_5v5 = toi_5v5
    return r


def _instat(game_id=1, puck_recoveries=None, pb_won_dz=None):
    r = PlayerGameStatsInStat(player_id=1, game_id=game_id)
    r.puck_recoveries = puck_recoveries
    r.pb_won_dz = pb_won_dz
    return r


def _shots(game_id=1, shots_blocked_defensively=None):
    r = PlayerGameShotsInStat(player_id=1, game_id=game_id)
    r.shots_blocked_defensively = shots_blocked_defensively
    return r


class TestDefensiveDisruptionIndex:
    def test_empty_returns_none(self):
        r = defensive_disruption_index([], [], [])
        assert r["ddi_per_60"] is None
        assert r["components"] == {"puck_recoveries": 0,
                                    "shots_blocked_defensively": 0,
                                    "dz_pb_wins": 0}
        assert r["total_toi_minutes"] == 0.0
        assert r["games"] == 0

    def test_single_game_all_components(self):
        pgs = [_pgs(toi_5v5=15.0)]
        instat = [_instat(puck_recoveries=8, pb_won_dz=3)]
        shots = [_shots(shots_blocked_defensively=4)]
        r = defensive_disruption_index(pgs, instat, shots)
        # (8 + 4 + 3) × 60 / 15 = 60
        assert r["ddi_per_60"] == pytest.approx(60.0)
        assert r["components"] == {"puck_recoveries": 8,
                                    "shots_blocked_defensively": 4,
                                    "dz_pb_wins": 3}
        assert r["total_toi_minutes"] == pytest.approx(15.0)
        assert r["games"] == 1

    def test_multi_game_aggregate(self):
        pgs = [_pgs(game_id=1, toi_5v5=15.0), _pgs(game_id=2, toi_5v5=20.0)]
        instat = [_instat(game_id=1, puck_recoveries=6, pb_won_dz=2),
                  _instat(game_id=2, puck_recoveries=4, pb_won_dz=1)]
        shots = [_shots(game_id=1, shots_blocked_defensively=3),
                 _shots(game_id=2, shots_blocked_defensively=1)]
        r = defensive_disruption_index(pgs, instat, shots)
        # (10 + 4 + 3) × 60 / 35 = 29.14...
        assert r["ddi_per_60"] == pytest.approx(17 * 60 / 35)
        assert r["games"] == 2

    def test_missing_component_returns_none(self):
        # Recoveries and DZ PB wins present, but zero shots blocking data
        pgs = [_pgs(toi_5v5=15.0)]
        instat = [_instat(puck_recoveries=8, pb_won_dz=3)]
        shots = [_shots(shots_blocked_defensively=None)]  # no data
        r = defensive_disruption_index(pgs, instat, shots)
        assert r["ddi_per_60"] is None
        # Components still show the counts we did aggregate
        assert r["components"]["puck_recoveries"] == 8

    def test_zero_toi_returns_none(self):
        pgs = [_pgs(toi_5v5=0.0)]
        instat = [_instat(puck_recoveries=8, pb_won_dz=3)]
        shots = [_shots(shots_blocked_defensively=4)]
        r = defensive_disruption_index(pgs, instat, shots)
        assert r["ddi_per_60"] is None

    def test_none_values_treated_as_zero_when_at_least_one_row_has_data(self):
        # One game with data, one game with None fields for a component
        pgs = [_pgs(game_id=1, toi_5v5=15.0), _pgs(game_id=2, toi_5v5=15.0)]
        instat = [_instat(game_id=1, puck_recoveries=5, pb_won_dz=2),
                  _instat(game_id=2, puck_recoveries=None, pb_won_dz=None)]
        shots = [_shots(game_id=1, shots_blocked_defensively=3),
                 _shots(game_id=2, shots_blocked_defensively=2)]
        r = defensive_disruption_index(pgs, instat, shots)
        # recoveries: 5 + 0 = 5 (has_data=True from game 1)
        # blocks: 3 + 2 = 5 (has_data=True)
        # dz_pb: 2 + 0 = 2 (has_data=True)
        assert r["components"]["puck_recoveries"] == 5
        assert r["components"]["shots_blocked_defensively"] == 5
        assert r["components"]["dz_pb_wins"] == 2
        # 12 × 60 / 30 = 24
        assert r["ddi_per_60"] == pytest.approx(24.0)
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_ddi.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement**

Append to `backend/app/tier3_stats.py`:

```python
def defensive_disruption_index(
    pgs_rows: list, instat_rows: list, shots_rows: list
) -> dict:
    """Composite off-puck defensive proxy (§9.9 with 2026-09-06 ruling).

    DDI/60 = (puck_recoveries + shots_blocked_defensively + DZ PB wins) × 60 ÷ TOI

    All three components require InStat. Returns ddi_per_60 = None when
    any component has NO data (no row provided a value) OR when total
    TOI is zero. Zero-value components with at least one populated row
    are treated as zero, not as missing data.
    """
    recoveries = 0
    blocks = 0
    dz_pb = 0
    recoveries_has_data = False
    blocks_has_data = False
    dz_pb_has_data = False
    games = 0
    total_toi = 0.0

    for r in instat_rows:
        if r.puck_recoveries is not None:
            recoveries += r.puck_recoveries
            recoveries_has_data = True
        if r.pb_won_dz is not None:
            dz_pb += r.pb_won_dz
            dz_pb_has_data = True
        if r.puck_recoveries or r.pb_won_dz:
            games += 1

    for r in shots_rows:
        if r.shots_blocked_defensively is not None:
            blocks += r.shots_blocked_defensively
            blocks_has_data = True

    for p in pgs_rows:
        total_toi += p.toi_5v5 or 0

    total_events = recoveries + blocks + dz_pb
    if total_toi <= 0 or not (recoveries_has_data and blocks_has_data and dz_pb_has_data):
        ddi_per_60 = None
    else:
        ddi_per_60 = total_events * 60.0 / total_toi

    return {
        "ddi_per_60": ddi_per_60,
        "components": {
            "puck_recoveries": recoveries,
            "shots_blocked_defensively": blocks,
            "dz_pb_wins": dz_pb,
        },
        "total_toi_minutes": total_toi,
        "games": games,
    }
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_ddi.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tier3_stats.py backend/tests/test_ddi.py
git commit -m "feat: add defensive_disruption_index tier3 stat function"
```

---

### Task 6: Update `danger_zone_shot_share` to use true SCA counts

**Files:**
- Modify: `backend/app/tier2_stats.py`
- Modify: `backend/tests/test_danger_zone_share.py`

**Interfaces:**
- Consumes: existing signature `danger_zone_shot_share(instat_rows, team_instat_rows, pgs_rows)`. Adds one new optional parameter `shots_rows: list = None`.
- Produces:
  - Behavior change: when `shots_rows` is provided, numerator becomes `sum(r.slot_shots_total + r.center_shots_total for r in shots_rows)` — the true SCA proxy per spec §9.6 (InStat's slot + center zones are the scoring-chance area). When `shots_rows` is None or empty, fall back to the Phase 3 `r.shots` proxy on `instat_rows` for backward compat.
  - Existing return shape unchanged (5 keys: `share_pct`, `shots_per_60`, `player_sca_shots`, `team_sca_shots`, `games`).

- [ ] **Step 1: Write failing tests**

Modify `backend/tests/test_danger_zone_share.py` — add new test class at the bottom:

```python
class TestDangerZoneWithShotsRows:
    def _shots_row(self, game_id=1, slot=0, center=0):
        from app.models import PlayerGameShotsInStat
        r = PlayerGameShotsInStat(player_id=1, game_id=game_id)
        r.slot_shots_total = slot
        r.center_shots_total = center
        return r

    def test_uses_slot_plus_center_when_shots_rows_provided(self):
        instat = [_instat(shots=99)]  # r.shots proxy would give 99
        team = [_team(scoring_chance_shots=20)]
        pgs = [_pgs(toi_5v5=15.0)]
        shots = [self._shots_row(slot=3, center=2)]  # true SCA = 5
        r = danger_zone_shot_share(instat, team, pgs, shots_rows=shots)
        # Numerator now 3+2=5, not 99
        assert r["player_sca_shots"] == 5
        assert r["share_pct"] == pytest.approx(5 / 20)
        assert r["shots_per_60"] == pytest.approx(5 * 60 / 15.0)

    def test_falls_back_to_shots_proxy_when_shots_rows_empty(self):
        instat = [_instat(shots=4)]
        team = [_team(scoring_chance_shots=10)]
        pgs = [_pgs(toi_5v5=10.0)]
        r = danger_zone_shot_share(instat, team, pgs, shots_rows=[])
        # Falls back to Phase 3 proxy: r.shots
        assert r["player_sca_shots"] == 4

    def test_falls_back_when_shots_rows_none(self):
        instat = [_instat(shots=4)]
        team = [_team(scoring_chance_shots=10)]
        pgs = [_pgs(toi_5v5=10.0)]
        r = danger_zone_shot_share(instat, team, pgs)  # no shots_rows
        assert r["player_sca_shots"] == 4

    def test_multi_game_shots_rows_aggregate(self):
        instat = [_instat(shots=99), _instat(shots=99)]
        team = [_team(scoring_chance_shots=30)]
        pgs = [_pgs(toi_5v5=20.0)]
        shots = [self._shots_row(game_id=1, slot=2, center=1),
                 self._shots_row(game_id=2, slot=3, center=2)]
        r = danger_zone_shot_share(instat, team, pgs, shots_rows=shots)
        assert r["player_sca_shots"] == 8  # 2+1+3+2
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_danger_zone_share.py::TestDangerZoneWithShotsRows -v`
Expected: `TypeError: danger_zone_shot_share() got an unexpected keyword argument 'shots_rows'`.

- [ ] **Step 3: Update the function**

Modify `backend/app/tier2_stats.py` — extend `danger_zone_shot_share`:

```python
def danger_zone_shot_share(
    instat_rows: list,
    team_instat_rows: list,
    pgs_rows: list,
    shots_rows: list | None = None,
) -> dict:
    """Player's share of team's high-danger shots + per-60 rate (§9.6).

    Numerator: when `shots_rows` (PlayerGameShotsInStat) is provided, uses
    slot_shots_total + center_shots_total as the SCA proxy (spec §9.6:
    "shots from scoring chance area" = InStat's slot + center zones).
    When shots_rows is None or empty, falls back to Phase 3's `r.shots`
    proxy on instat_rows for backward compat with callers that haven't
    loaded shots data yet.

    Denominator: sum of team's scoring_chance_shots across ALL InStat
    games in the window.

    Note the asymmetry: a player who missed games where the team recorded
    SCA shots will have their share_pct understated. This matches spec §9.6
    (share is player contribution to team output, not per-game percentage)
    but consumers should be aware."""
    if shots_rows:
        player_sca = sum((r.slot_shots_total or 0) + (r.center_shots_total or 0)
                         for r in shots_rows)
        games_with_data = sum(1 for r in shots_rows
                              if (r.slot_shots_total or 0) + (r.center_shots_total or 0) > 0)
    else:
        # Phase 3 fallback proxy
        player_sca = 0
        games_with_data = 0
        for r in instat_rows:
            val = r.shots or 0
            if val > 0:
                games_with_data += 1
            player_sca += val

    team_sca = sum((t.scoring_chance_shots or 0) for t in team_instat_rows)
    total_toi = sum((p.toi_5v5 or 0) for p in pgs_rows)

    return {
        "share_pct": (player_sca / team_sca) if team_sca > 0 else None,
        "shots_per_60": (player_sca * 60.0 / total_toi) if (total_toi > 0 and player_sca > 0) else None,
        "player_sca_shots": player_sca,
        "team_sca_shots": team_sca,
        "games": games_with_data,
    }
```

- [ ] **Step 4: Verify all danger-share tests pass (new + existing)**

Run: `backend/venv/bin/python -m pytest backend/tests/test_danger_zone_share.py -v`
Expected: all pass (Phase 3 tests + 4 new).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tier2_stats.py backend/tests/test_danger_zone_share.py
git commit -m "feat: danger_zone_shot_share uses true SCA (slot+center) when shots_rows provided"
```

---

### Task 7: Extend `enrich_player_agg` + router wiring

**Files:**
- Modify: `backend/app/enrichment.py`
- Modify: `backend/app/routers/stats.py`
- Modify: `backend/app/routers/reports.py`
- Create: `backend/tests/test_enrich_tier3.py`

**Interfaces:**
- Consumes: `shot_threat_by_scenario`, `defensive_disruption_index` from `app.tier3_stats`; updated `danger_zone_shot_share` from `app.tier2_stats` (accepts `shots_rows`).
- Produces:
  - `enrich_player_agg` gains a `shots_rows: list = None` keyword-only arg.
  - When `shots_rows` is provided (in addition to `instat_rows`), agg gains: `shot_threat`, `ddi` keys.
  - `danger_share` computation inside enrich now passes `shots_rows` through to `danger_zone_shot_share`.
  - `load_player_shots_rows(db, player_id, date_from=None, date_to=None) -> list[PlayerGameShotsInStat]` added to `enrichment.py`.
  - Both routers load shots_rows via new helper and pass through.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_enrich_tier3.py`:
```python
import pytest
from datetime import date
from app.models import (
    Player, Game, PlayerGameStats, PlayerGameStatsInStat, TeamGameStatsInStat,
    PlayerGameShotsInStat,
)
from app.enrichment import enrich_player_agg, load_player_shots_rows


@pytest.fixture
def enriched_setup(db_session):
    p = Player(name="Ten", number="10", position="F", is_center=True, active=True)
    g1 = Game(date=date(2025, 10, 1), opponent="A", is_home=True,
              season="2025-26", data_source="instat")
    g2 = Game(date=date(2025, 10, 8), opponent="B", is_home=False,
              season="2025-26", data_source="instat")
    db_session.add_all([p, g1, g2])
    db_session.commit()

    pgs_rows = []
    instat_rows = []
    team_rows = []
    shots_rows = []
    for g in [g1, g2]:
        pgs = PlayerGameStats(player_id=p.id, game_id=g.id,
                              toi_5v5=15.0, cf60=50, ca60=40,
                              xgf60=2.5, xga60=2.0,
                              ff60=40, fa60=35, sf60=30, sa60=25)
        db_session.add(pgs); pgs_rows.append(pgs)
        ir = PlayerGameStatsInStat(player_id=p.id, game_id=g.id,
                                    puck_recoveries=8, pb_won_dz=3,
                                    entries_pass=2, entries_stick=3, entries_dump=1)
        db_session.add(ir); instat_rows.append(ir)
        tr = TeamGameStatsInStat(game_id=g.id,
                                  scoring_chance_shots=25,
                                  pp_shots=12, pp_time_seconds_total=600,
                                  pp_time_seconds_in_oz=360, pk_opp_breakouts=2)
        db_session.add(tr); team_rows.append(tr)
        sr = PlayerGameShotsInStat(player_id=p.id, game_id=g.id,
                                    goals=1, shots_total=5, shots_on_goal=3,
                                    shots_blocked_defensively=4,
                                    slot_shots_total=2, slot_shots_on_goal=2,
                                    center_shots_total=1, center_shots_on_goal=1)
        db_session.add(sr); shots_rows.append(sr)
    db_session.commit()

    agg = {
        "player_id": p.id, "player_name": p.name,
        "games_played": 2, "small_sample": False,
        "toi_5v5": 15.0, "trend": [],
    }
    return p, agg, pgs_rows, instat_rows, team_rows, shots_rows


class TestLoadPlayerShotsRows:
    def test_loads_rows_for_player(self, db_session, enriched_setup):
        p, *_ = enriched_setup
        rows = load_player_shots_rows(db_session, p.id)
        assert len(rows) == 2


class TestEnrichTier3:
    def test_no_shots_rows_preserves_tier2_behavior(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows, _ = enriched_setup
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts={},
        )
        # Tier 2 keys present, Tier 3 absent
        for k in ("contested_puck", "impact_score", "danger_share"):
            assert k in result
        assert "shot_threat" not in result
        assert "ddi" not in result

    def test_with_shots_rows_attaches_tier3(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows, shots_rows = enriched_setup
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts={},
            shots_rows=shots_rows,
        )
        assert "shot_threat" in result
        assert "ddi" in result
        assert result["shot_threat"]["totals"]["goals"] == 2
        assert result["ddi"]["components"]["shots_blocked_defensively"] == 8

    def test_danger_share_uses_true_sca_when_shots_provided(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows, shots_rows = enriched_setup
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts={},
            shots_rows=shots_rows,
        )
        # Numerator: 2 games × (slot=2 + center=1) = 6
        assert result["danger_share"]["player_sca_shots"] == 6
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_enrich_tier3.py -v`
Expected: `ImportError` (load_player_shots_rows) or unexpected kwarg (shots_rows).

- [ ] **Step 3: Add loader helper**

Modify `backend/app/enrichment.py` — add near the other loader helpers:

```python
def load_player_shots_rows(
    db: Session,
    player_id: int,
    date_from: _Optional[_date] = None,
    date_to: _Optional[_date] = None,
) -> list[PlayerGameShotsInStat]:
    """Load PlayerGameShotsInStat rows for a player, optionally by date range."""
    q = db.query(PlayerGameShotsInStat).join(Game).filter(
        PlayerGameShotsInStat.player_id == player_id
    )
    if date_from is not None:
        q = q.filter(Game.date >= date_from)
    if date_to is not None:
        q = q.filter(Game.date <= date_to)
    return q.all()
```

Also add `PlayerGameShotsInStat` to the model import at the bottom:
```python
from .models import PlayerGameStatsInStat, TeamGameStatsInStat, Game, PlayerGameShotsInStat
```

- [ ] **Step 4: Extend enrich_player_agg**

Modify `enrich_player_agg` — add the `shots_rows` kwarg and wire it:

```python
def enrich_player_agg(
    player: Player,
    agg: dict,
    all_aggs: list,
    *,
    instat_rows: list | None = None,
    team_instat_rows: list | None = None,
    pgs_rows: list | None = None,
    position_cohorts: dict | None = None,
    shots_rows: list | None = None,
) -> dict:
    """Attach Phase 1 (comparisons/flags) + Phase 3 (Tier 2) + Phase 4 (Tier 3)
    layers to a player aggregate. Layers activate based on which kwargs are
    provided; omitting kwargs preserves the earlier phase's behavior."""
    # ... existing Phase 1 code unchanged ...

    # Phase 3: Tier 2 stats (existing code)
    if instat_rows is not None:
        from .tier2_stats import (
            contested_puck_win_pct, zone_entry_composition,
            turnover_location_ratio, danger_zone_shot_share, impact_score,
        )
        agg["contested_puck"] = contested_puck_win_pct(instat_rows)
        agg["zone_entry"] = zone_entry_composition(instat_rows)
        agg["turnover_ratio"] = turnover_location_ratio(instat_rows)
        agg["danger_share"] = danger_zone_shot_share(
            instat_rows, team_instat_rows or [], pgs_rows or [],
            shots_rows=shots_rows,  # NEW — pass through
        )
        instat_by_game = {r.game_id: r for r in instat_rows}
        agg["impact_score"] = impact_score(
            player, pgs_rows or [], instat_by_game, position_cohorts or {},
        )

    # Phase 4: Tier 3 stats
    if shots_rows is not None:
        from .tier3_stats import shot_threat_by_scenario, defensive_disruption_index
        agg["shot_threat"] = shot_threat_by_scenario(shots_rows, pgs_rows or [])
        agg["ddi"] = defensive_disruption_index(
            pgs_rows or [], instat_rows or [], shots_rows,
        )

    return agg
```

- [ ] **Step 5: Wire stats.py router**

Modify `backend/app/routers/stats.py` — in the player-agg endpoint, add:

```python
from .enrichment import load_player_shots_rows  # add to existing import line

# ...inside the player-agg endpoint, after loading instat_rows and team_rows:
shots_rows = load_player_shots_rows(db, player.id, date_from, date_to)

# Update the enrich_player_agg call:
enriched = enrich_player_agg(
    player, agg, all_aggs,
    instat_rows=instat_rows,
    team_instat_rows=team_rows,
    pgs_rows=pgs_rows,
    position_cohorts=position_cohorts,
    shots_rows=shots_rows,  # NEW
)
```

- [ ] **Step 6: Wire reports.py router**

Modify `backend/app/routers/reports.py` — apply the same pattern (load `shots_rows`, pass to `enrich_player_agg`).

- [ ] **Step 7: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_enrich_tier3.py backend/tests/test_enrich_tier2.py -v`
Expected: all pass (new + existing Tier 2 behavior preserved).

Also run the fast slice: `backend/venv/bin/python -m pytest backend/tests/ --ignore=backend/tests/test_ingest_router.py --ignore=backend/tests/test_ingest_end_to_end.py --ignore=backend/tests/test_orchestrator.py -q`
Expected: all pass, no regressions.

- [ ] **Step 8: Commit**

```bash
git add backend/app/enrichment.py backend/app/routers/stats.py backend/app/routers/reports.py backend/tests/test_enrich_tier3.py
git commit -m "feat: enrich player agg with tier3 stats + wire shots_rows through routers"
```

---

### Task 8: Frontend Tier 3 types

**Files:**
- Modify: `frontend/src/types.ts`

**Interfaces:**
- Produces: TypeScript interfaces `ScenarioCell`, `ShotThreatStats`, `DDIStats`, `DDIComponents`. Extends `PlayerAggStats` with optional `shot_threat?` and `ddi?` fields.

- [ ] **Step 1: Add interfaces**

Append to `frontend/src/types.ts`:
```typescript
export interface ScenarioCell {
  shots: number
  on_goal: number
  shots_per_60?: number | null   // only on strength cells
  on_goal_pct: number | null
}

export interface ShotThreatStats {
  totals: {
    goals: number
    shots: number
    shots_on_goal: number
    toi_5v5_minutes: number
  }
  by_strength: {
    '5v5': ScenarioCell
    pp: ScenarioCell
    sh: ScenarioCell
  }
  by_context: {
    positional: ScenarioCell
    counter: ScenarioCell
  }
  by_location: {
    slot: ScenarioCell
    center: ScenarioCell
    right_flank: ScenarioCell
    left_flank: ScenarioCell
    blue_line_right: ScenarioCell
    blue_line_center: ScenarioCell
    blue_line_left: ScenarioCell
  }
  by_type: {
    slapshot: ScenarioCell
    wristshot: ScenarioCell
  }
  games: number
}

export interface DDIComponents {
  puck_recoveries: number
  shots_blocked_defensively: number
  dz_pb_wins: number
}

export interface DDIStats {
  ddi_per_60: number | null
  components: DDIComponents
  total_toi_minutes: number
  games: number
}
```

- [ ] **Step 2: Extend `PlayerAggStats`**

Find the `PlayerAggStats` interface. Append:
```typescript
  shot_threat?: ShotThreatStats
  ddi?: DDIStats
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat: add tier3 stat type interfaces"
```

---

### Task 9: `ShotThreatBlock` component

**Files:**
- Create: `frontend/src/components/ShotThreatBlock.tsx`

**Interfaces:**
- Consumes: `ShotThreatStats` type.
- Produces: `ShotThreatBlock({ data }: { data?: ShotThreatStats })` — static compact view. Renders four sub-sections (Strength, Location, Context, Type) each as a compact row of "label: shots/on_goal" cells. Returns null when data missing or `games === 0`.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ShotThreatBlock.tsx`:
```tsx
import type { ShotThreatStats, ScenarioCell } from '../types'


function fmtCell(c: ScenarioCell): string {
  return `${c.shots}/${c.on_goal}`
}


function fmtPct(v: number | null): string {
  return v === null ? '—' : `${(v * 100).toFixed(0)}%`
}


function fmtRate(v: number | null | undefined): string {
  return v == null ? '—' : v.toFixed(1)
}


function StatSubBlock({ title, entries }: {
  title: string
  entries: [string, ScenarioCell, string?][]  // label, cell, optional extra column
}) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4, letterSpacing: '0.05em' }}>
        {title.toUpperCase()}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 6 }}>
        {entries.map(([label, cell, extra]) => (
          <div key={label} style={{
            padding: 8,
            border: '1px solid var(--border, #333)',
            borderRadius: 3,
            fontSize: 12,
          }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: 10, marginBottom: 2 }}>
              {label}
            </div>
            <div style={{ fontWeight: 600 }}>{fmtCell(cell)}</div>
            {extra && (
              <div style={{ color: 'var(--text-secondary)', fontSize: 10 }}>{extra}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}


export default function ShotThreatBlock({ data }: { data?: ShotThreatStats }) {
  if (!data || data.games === 0) return null

  const strengthEntries: [string, ScenarioCell, string][] = [
    ['5v5', data.by_strength['5v5'], `${fmtRate(data.by_strength['5v5'].shots_per_60)} S/60`],
    ['PP', data.by_strength.pp, `${fmtRate(data.by_strength.pp.shots_per_60)} S/60`],
    ['SH', data.by_strength.sh, `${fmtRate(data.by_strength.sh.shots_per_60)} S/60`],
  ]

  const contextEntries: [string, ScenarioCell, string][] = [
    ['Positional', data.by_context.positional, fmtPct(data.by_context.positional.on_goal_pct)],
    ['Counter (rush)', data.by_context.counter, fmtPct(data.by_context.counter.on_goal_pct)],
  ]

  const locationEntries: [string, ScenarioCell, string][] = [
    ['Slot', data.by_location.slot, fmtPct(data.by_location.slot.on_goal_pct)],
    ['Center', data.by_location.center, fmtPct(data.by_location.center.on_goal_pct)],
    ['R Flank', data.by_location.right_flank, fmtPct(data.by_location.right_flank.on_goal_pct)],
    ['L Flank', data.by_location.left_flank, fmtPct(data.by_location.left_flank.on_goal_pct)],
    ['BL R', data.by_location.blue_line_right, fmtPct(data.by_location.blue_line_right.on_goal_pct)],
    ['BL C', data.by_location.blue_line_center, fmtPct(data.by_location.blue_line_center.on_goal_pct)],
    ['BL L', data.by_location.blue_line_left, fmtPct(data.by_location.blue_line_left.on_goal_pct)],
  ]

  const typeEntries: [string, ScenarioCell, string][] = [
    ['Slap', data.by_type.slapshot, fmtPct(data.by_type.slapshot.on_goal_pct)],
    ['Wrist', data.by_type.wristshot, fmtPct(data.by_type.wristshot.on_goal_pct)],
  ]

  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
        Shot Threat by Scenario ({data.totals.shots} shots · {data.totals.goals} G · {data.games} game{data.games !== 1 ? 's' : ''})
      </h3>
      <StatSubBlock title="Strength" entries={strengthEntries} />
      <StatSubBlock title="Location" entries={locationEntries} />
      <StatSubBlock title="Context" entries={contextEntries} />
      <StatSubBlock title="Type" entries={typeEntries} />
    </div>
  )
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ShotThreatBlock.tsx
git commit -m "feat: add ShotThreatBlock component (static compact view)"
```

---

### Task 10: ReportsPage integration

**Files:**
- Modify: `frontend/src/pages/ReportsPage.tsx`

**Interfaces:**
- Consumes: `ShotThreatBlock` component; existing `StatCard`.
- Produces: player expand-detail panel gains 2 new blocks — Shot Threat (via `ShotThreatBlock`) and DDI (2 StatCards: DDI/60 + component breakdown).

- [ ] **Step 1: Extend player report section**

Read `frontend/src/pages/ReportsPage.tsx`. Locate the player expand-detail panel where Phase 3 Tier 2 blocks render. Add:

```tsx
import ShotThreatBlock from '../components/ShotThreatBlock'

// Inside the player expand-detail panel, after existing Tier 2 blocks:
{agg.shot_threat && agg.shot_threat.games > 0 && (
  <ShotThreatBlock data={agg.shot_threat} />
)}

{agg.ddi && agg.ddi.games > 0 && (
  <div className="card" style={{ marginTop: 16 }}>
    <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
      Defensive Disruption Index
    </h3>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
      <StatCard
        label="DDI/60"
        primary={agg.ddi.ddi_per_60 === null ? 'N/A' : agg.ddi.ddi_per_60.toFixed(1)}
      />
      <StatCard
        label="Components (rec / blk / dz-pb)"
        primary={`${agg.ddi.components.puck_recoveries} / ${agg.ddi.components.shots_blocked_defensively} / ${agg.ddi.components.dz_pb_wins}`}
      />
    </div>
    <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 8 }}>
      Composite proxy per §9.9: puck recoveries + defensive blocks + DZ puck battles won, scaled to per-60.
    </div>
  </div>
)}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ReportsPage.tsx
git commit -m "feat: render Shot Threat + DDI blocks on player report"
```

---

### Task 11: MethodologyPage cleanup — un-plan Shot Threat + DDI; update DDI formula text

**Files:**
- Modify: `frontend/src/pages/MethodologyPage.tsx`

**Interfaces:**
- Produces: 2 entries lose `status: 'planned'`; DDI's `formula` and `whyNotGoals`/`limitations` text updated to reflect the puck-recoveries-as-takeaways ruling.

- [ ] **Step 1: Locate the entries**

Read `frontend/src/pages/MethodologyPage.tsx`. Find:
- `name: 'Defensive Disruption Index (DDI/60)'` — currently has `status: 'planned'` and formula uses "takeaways".
- `name: 'Shot Threat by Scenario, All Players'` — currently has `status: 'planned'`.

- [ ] **Step 2: Update DDI entry**

- Remove the `status: 'planned',` line.
- Change `formula` from `'DDI/60 = (takeaways + shots blocked + DZ puck battles won) × 60 ÷ TOI · ...'` to `'DDI/60 = (puck recoveries + shots blocked defensively + DZ puck battles won) × 60 ÷ TOI · Season aggregate: TOI-weighted mean of per-game DDI/60'`.
- Update `whyNotGoals` to swap "takeaways (winning the puck without contact)" with "puck recoveries (securing a loose puck the opponent last controlled — used as the takeaways proxy per the 2026-09-06 ruling; InStat does not expose takeaways as a distinct field)".
- Add a bullet to `limitations`: `'"Takeaways" component uses puck_recoveries as a proxy — a player who wins many contested pucks (PB wins) but doesn\'t recover loose ones will underscore. See spec §9.9 2026-09-06 ruling.'`

- [ ] **Step 3: Update Shot Threat entry**

- Remove the `status: 'planned',` line.
- Add a bullet to `limitations`: `'Shipped as static compact view per Phase 4 UI ruling. Interactive filter chips deferred; if a specific filter combination is not shown, the underlying data is captured per-game and can be surfaced when needs are clear.'`

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/MethodologyPage.tsx
git commit -m "chore: un-plan Shot Threat + DDI in methodology; update DDI formula per ruling"
```

---

### Task 12: End-to-end integration test

**Files:**
- Create: `backend/tests/test_tier3_end_to_end.py`

**Interfaces:**
- Test that `/api/stats/player/{id}` returns Tier 3 blocks (shot_threat, ddi) plus the updated danger_share using true SCA.

- [ ] **Step 1: Write the test**

Create `backend/tests/test_tier3_end_to_end.py`:
```python
import sys, types
sys.modules["weasyprint"] = sys.modules.get("weasyprint") or types.ModuleType("weasyprint")
sys.modules["weasyprint"].HTML = lambda *a, **k: None  # type: ignore

import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_db
from app.models import (
    Player, Game, PlayerGameStats, PlayerGameStatsInStat,
    TeamGameStatsInStat, PlayerGameShotsInStat,
)


def _make_client_and_session(tmp_path):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    return session, Session, engine


def _seed(session):
    players = [Player(name=f"F{i}", number=str(i), position="F", is_center=False, active=True)
               for i in range(1, 4)]
    for p in players:
        session.add(p)
    session.commit()
    games = []
    for i in range(3):
        g = Game(date=date(2025, 10, 1) + timedelta(days=i * 3),
                 opponent=f"O{i}", is_home=True, season="2025-26",
                 data_source="instat")
        session.add(g); games.append(g)
    session.commit()
    for g in games:
        session.add(TeamGameStatsInStat(game_id=g.id, scoring_chance_shots=30,
                                         pp_shots=12, pp_time_seconds_total=600,
                                         pp_time_seconds_in_oz=360, pk_opp_breakouts=2))
        for p in players:
            session.add(PlayerGameStats(player_id=p.id, game_id=g.id,
                                         toi_5v5=15.0, toi_pp=2.0, toi_sh=1.0,
                                         cf60=50, ca60=40, xgf60=2.5, xga60=2.0,
                                         ff60=40, fa60=30, sf60=25, sa60=20))
            session.add(PlayerGameStatsInStat(player_id=p.id, game_id=g.id,
                                               shots=5, puck_recoveries=8,
                                               pb_won_dz=3, pb_total_dz=5,
                                               entries_pass=2, entries_stick=3, entries_dump=1))
            session.add(PlayerGameShotsInStat(player_id=p.id, game_id=g.id,
                                               goals=1, shots_total=5, shots_on_goal=3,
                                               shots_blocked_defensively=4,
                                               pp_shots_total=1, pp_shots_on_goal=1,
                                               slot_shots_total=2, slot_shots_on_goal=2,
                                               center_shots_total=1, center_shots_on_goal=1,
                                               wristshot_total=4, wristshot_on_goal=2))
    session.commit()
    return players[0]


def test_player_agg_returns_tier3_blocks(tmp_path):
    session, Session, _ = _make_client_and_session(tmp_path)
    p = _seed(session)

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        resp = client.get(f"/api/stats/player/{p.id}")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert resp.status_code == 200
    body = resp.json()
    assert "shot_threat" in body
    assert "ddi" in body
    assert body["shot_threat"]["totals"]["goals"] == 3
    assert body["shot_threat"]["games"] == 3
    assert body["ddi"]["components"]["shots_blocked_defensively"] == 12
    assert body["ddi"]["components"]["puck_recoveries"] == 24
    assert body["ddi"]["ddi_per_60"] is not None
    # Danger share should now use slot+center = (2+1) * 3 = 9, NOT r.shots proxy (15)
    assert body["danger_share"]["player_sca_shots"] == 9
```

- [ ] **Step 2: Run the test**

Run: `backend/venv/bin/python -m pytest backend/tests/test_tier3_end_to_end.py -v`
Expected: 1 test passes.

Also fast slice: `backend/venv/bin/python -m pytest backend/tests/ --ignore=backend/tests/test_ingest_router.py --ignore=backend/tests/test_ingest_end_to_end.py --ignore=backend/tests/test_orchestrator.py -q`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_tier3_end_to_end.py
git commit -m "test: end-to-end integration test for tier3 stats + danger_share SCA fix"
```

---

## Final verification

- [ ] **Migration idempotency:** `cd backend && venv/bin/python migrate_v7.py` twice → clean no-op on second run.

- [ ] **Full backend suite passes.** Fast slice + full run. Expect ~180 baseline + ~35-40 Phase 4 additions.

- [ ] **Frontend typecheck passes:** `cd frontend && npx tsc --noEmit` → no errors.

- [ ] **Manual smoke test (deferred):** re-ingest the fixture PDF via `/ingest` (now with 7 templates parsing including shots) and view a player report — Shot Threat block should render with actual InStat data, DDI should show a real per-60 number.

- [ ] **Ledger deferred / follow-ups:**
  - Goalie stats (§9.10) — Phase 4b when per-goalie InStat data is confirmed.
  - Interactive filter chips for Shot Threat — deferred per Phase 4 UI ruling.
  - Line combinations (P4/12) parser — still deferred; no downstream consumer yet.
