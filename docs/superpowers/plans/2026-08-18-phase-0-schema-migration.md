# Phase 0: Schema Migration to Option B — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the data-source dimension to the schema so games can be tagged as sourced from 49ing, InStat, or both. Create the InStat-native tables. Wire the aggregation layer to filter games by per-stat source availability so nothing silently averages incompatible data.

**Architecture:** Add `data_source` column to `Game` (default `"49ing"`). Add `PlayerGameStatsInStat` and `TeamGameStatsInStat` tables holding raw counts and InStat-only fields. Introduce `app/stat_sources.py` declaring which sources supply each tracked stat. Extend `aggregate_player_stats` / `aggregate_team_stats` to filter game sets per stat via that declaration and to report per-stat availability metadata to callers. This lays the data foundation; actual reads/writes of the new InStat tables happen in Phase 2 (ingest) and Phase 3 (Tier 2 stats).

**Tech Stack:** SQLAlchemy · SQLite · FastAPI · Pydantic · React/TypeScript (existing). Uses existing raw-sqlite3 migration pattern (see `backend/migrate_v4.py`), not Alembic.

**Spec:** `docs/superpowers/specs/2026-08-18-ecac-stats-expansion-design.md` (§2 Data source strategy, §3 Schema migration)

## Branch context

**Phase 1's pytest infrastructure has not merged to `main` yet.** If this plan is executed on a branch off `main` (per user preference), Task 1 will create the same pytest scaffolding Phase 1 already shipped. When either branch merges first, git will see the identical files and no-op the second merge. If the executor detects `backend/tests/conftest.py` already exists at branch base, Task 1 becomes a verification step instead of a creation step.

## Global Constraints

- **Data source values:** `Game.data_source` accepts exactly `"49ing"`, `"instat"`, or `"both"` (string column, no enum type — SQLite doesn't enforce enums).
- **Backfill rule:** every existing `Game` row gets `data_source = "49ing"` when the migration runs.
- **Merge rule (both sources present):** for stats both sources cover, 49ing values take precedence. Phase 0 declares this but does not implement full dual-source merging math — that lands per-stat as Phase 3+ builds specific stats.
- **No net-new stats in this phase.** Existing stats continue computing exactly as they do today. The only user-visible change is availability metadata + N/A badges for windows with no qualifying games.
- **Migration script style:** raw `sqlite3` with try/except on `ADD COLUMN`, `CREATE TABLE IF NOT EXISTS` for new tables. Match `migrate_v4.py` pattern. File name: `backend/migrate_v5.py`.
- Use `backend/venv/bin/pytest` for tests. All commands run from within the worktree working directory.
- Commit style: conventional-commits (`feat:`, `test:`, `refactor:`).
- Frontend typecheck must pass: `cd frontend && npx tsc --noEmit`.
- No changes to `enrich_player_agg` orchestration from Phase 1 — it stays a pass-through. Availability metadata is added at the `aggregate_player_stats` layer, which `enrich_player_agg` calls transitively via the router.

---

### Task 1: Verify or bootstrap pytest infrastructure

**Files:**
- Verify (or create if missing): `backend/pytest.ini`, `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_smoke.py`
- Verify: `backend/requirements.txt` includes `pytest>=8.0` and `pytest-cov>=5.0`

**Interfaces:**
- Consumes: nothing
- Produces: same pytest fixtures Phase 1 shipped — `db_session`, `seed_roster`, `seed_games`

- [ ] **Step 1: Detect existing pytest infra**

Run: `ls backend/tests/conftest.py 2>&1`
- If file exists: pytest is present (likely because Phase 1 merged, or the executor is on a Phase 1-adjacent branch). Skip to Step 4 to verify it runs.
- If file does not exist: proceed to Step 2.

- [ ] **Step 2: Add pytest deps + config (if missing)**

Append to `backend/requirements.txt` (skip lines already present):
```
pytest>=8.0
pytest-cov>=5.0
```

Run: `backend/venv/bin/pip install pytest pytest-cov`
Expected: successful install.

Create `backend/pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

- [ ] **Step 3: Create conftest with fixtures (if missing)**

Create `backend/tests/__init__.py` (empty).

Create `backend/tests/conftest.py`:
```python
import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Player, Game


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seed_roster(db_session):
    players = [
        Player(name="Center One",  number="10", position="F", is_center=True,  active=True),
        Player(name="Winger One",  number="7",  position="F", is_center=False, active=True),
        Player(name="Winger Two",  number="9",  position="F", is_center=False, active=True),
        Player(name="Defender One", number="2", position="D", is_center=False, active=True),
        Player(name="Defender Two", number="4", position="D", is_center=False, active=True),
        Player(name="Goalie One",   number="30", position="G", is_center=False, active=True),
    ]
    for p in players:
        db_session.add(p)
    db_session.commit()
    return players


@pytest.fixture
def seed_games(db_session):
    def _seed(n=10):
        base = date(2025, 10, 1)
        games = []
        for i in range(n):
            g = Game(
                date=base + timedelta(days=i * 4),
                opponent=f"Opp{i}",
                is_home=(i % 2 == 0),
                season="2025-26",
            )
            db_session.add(g)
            games.append(g)
        db_session.commit()
        return games
    return _seed
```

Create `backend/tests/test_smoke.py`:
```python
def test_db_session_is_writable(db_session):
    from app.models import Player
    p = Player(name="Test", number="1", position="F", is_center=False, active=True)
    db_session.add(p)
    db_session.commit()
    assert db_session.query(Player).count() == 1


def test_seed_roster_creates_six(db_session, seed_roster):
    from app.models import Player
    assert db_session.query(Player).count() == 6


def test_seed_games_default_is_ten(db_session, seed_games):
    from app.models import Game
    games = seed_games()
    assert len(games) == 10
```

- [ ] **Step 4: Verify pytest runs**

Run: `cd backend && venv/bin/pytest tests/test_smoke.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit (if any files were created)**

If Step 2 or Step 3 created files:
```bash
git add backend/pytest.ini backend/tests/ backend/requirements.txt
git commit -m "test: bootstrap pytest infrastructure for Phase 0"
```

If pytest already existed (Step 1 verified only): no commit; note "pytest already present" in the report.

---

### Task 2: `data_source` column on `Game` + migration

**Files:**
- Modify: `backend/app/models.py` (add column to `Game` class)
- Modify: `backend/app/schemas.py` (extend `Game` / `GameCreate` / `GameUpdate` Pydantic schemas)
- Create: `backend/migrate_v5.py`
- Create: `backend/tests/test_data_source_column.py`

**Interfaces:**
- Consumes: existing `Game` model, existing pytest fixtures
- Produces:
  - `Game.data_source` — SQLAlchemy `Column(String, nullable=False, default="49ing")`
  - Pydantic `Game` and `GameCreate`/`GameUpdate` gain `data_source: Literal["49ing", "instat", "both"]` (default `"49ing"` on create)
  - `migrate_v5.py` runnable script that adds the column to the existing DB and backfills existing rows

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_data_source_column.py`:
```python
import pytest
from datetime import date
from app.models import Game, Player


class TestGameDataSource:
    def test_default_is_49ing(self, db_session):
        g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True, season="2025-26")
        db_session.add(g)
        db_session.commit()
        db_session.refresh(g)
        assert g.data_source == "49ing"

    def test_can_set_instat(self, db_session):
        g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True, season="2025-26",
                 data_source="instat")
        db_session.add(g)
        db_session.commit()
        db_session.refresh(g)
        assert g.data_source == "instat"

    def test_can_set_both(self, db_session):
        g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True, season="2025-26",
                 data_source="both")
        db_session.add(g)
        db_session.commit()
        assert g.data_source == "both"
```

- [ ] **Step 2: Verify tests fail**

Run: `cd backend && venv/bin/pytest tests/test_data_source_column.py -v`
Expected: FAIL with `TypeError: 'data_source' is an invalid keyword argument for Game` or similar.

- [ ] **Step 3: Add column to Game model**

Edit `backend/app/models.py`. In the `Game` class, add after the `season` column:

```python
    data_source = Column(String, nullable=False, default="49ing")
    # values: "49ing" | "instat" | "both" (SQLite does not enforce enum; validated at API layer)
```

- [ ] **Step 4: Verify Model tests pass**

Run: `cd backend && venv/bin/pytest tests/test_data_source_column.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Extend Pydantic schemas**

Read `backend/app/schemas.py` to find the `Game`, `GameCreate`, `GameUpdate` (or equivalent) Pydantic classes.

Add a shared literal type at the top of the file:
```python
from typing import Literal

DataSource = Literal["49ing", "instat", "both"]
```

In every schema that represents a Game (create, read, update, whichever exist), add:
```python
    data_source: DataSource = "49ing"
```

For read schemas that mirror the DB, no default is needed but include the field.

- [ ] **Step 6: Write the migration script**

Create `backend/migrate_v5.py`:
```python
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
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/migrate_v5.py backend/tests/test_data_source_column.py
git commit -m "feat: add data_source column to Game with backfill migration"
```

---

### Task 3: `PlayerGameStatsInStat` model + migration extension

**Files:**
- Modify: `backend/app/models.py` (add new class)
- Modify: `backend/app/schemas.py` (add matching Pydantic schema)
- Modify: `backend/migrate_v5.py` (append `CREATE TABLE` for the new table)
- Create: `backend/tests/test_instat_player_model.py`

**Interfaces:**
- Consumes: `Player`, `Game` (FKs)
- Produces:
  - `PlayerGameStatsInStat` SQLAlchemy model with the fields listed in spec §3
  - Pydantic `PlayerGameStatsInStat` schema
  - Migration creates the `player_game_stats_instat` table

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_instat_player_model.py`:
```python
import pytest
from datetime import date
from app.models import Player, Game, PlayerGameStatsInStat


@pytest.fixture
def sample_player_and_game(db_session):
    p = Player(name="Sample", number="10", position="F", is_center=True, active=True)
    g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True, season="2025-26",
             data_source="instat")
    db_session.add(p)
    db_session.add(g)
    db_session.commit()
    return p, g


class TestPlayerGameStatsInStat:
    def test_can_create_row(self, db_session, sample_player_and_game):
        p, g = sample_player_and_game
        row = PlayerGameStatsInStat(
            player_id=p.id, game_id=g.id,
            shots=8, shots_on_goal=5, blocked_shots=1,
            corsi_plus=15, corsi_minus=10,
            hits_delivered=2, hits_received=1,
            pb_won_dz=6, pb_total_dz=10,
            pb_won_oz=3, pb_total_oz=7,
            pb_won_nz=2, pb_total_nz=4,
            puck_losses=5, puck_losses_dz=1,
            puck_recoveries=8, puck_recoveries_oz=2,
            entries_pass=3, entries_stick=4, entries_dump=1,
        )
        db_session.add(row)
        db_session.commit()
        assert row.id is not None

    def test_all_fields_default_none(self, db_session, sample_player_and_game):
        p, g = sample_player_and_game
        row = PlayerGameStatsInStat(player_id=p.id, game_id=g.id)
        db_session.add(row)
        db_session.commit()
        assert row.shots is None
        assert row.pb_won_dz is None
        assert row.entries_pass is None

    def test_unique_player_game(self, db_session, sample_player_and_game):
        from sqlalchemy.exc import IntegrityError
        p, g = sample_player_and_game
        db_session.add(PlayerGameStatsInStat(player_id=p.id, game_id=g.id))
        db_session.commit()
        db_session.add(PlayerGameStatsInStat(player_id=p.id, game_id=g.id))
        with pytest.raises(IntegrityError):
            db_session.commit()
```

- [ ] **Step 2: Verify tests fail**

Run: `cd backend && venv/bin/pytest tests/test_instat_player_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'PlayerGameStatsInStat'`.

- [ ] **Step 3: Add the SQLAlchemy model**

Append to `backend/app/models.py`:
```python
class PlayerGameStatsInStat(Base):
    __tablename__ = "player_game_stats_instat"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)

    __table_args__ = (UniqueConstraint("player_id", "game_id"),)

    # Individual shooting (raw counts per game)
    shots = Column(Integer, nullable=True)
    shots_on_goal = Column(Integer, nullable=True)
    blocked_shots = Column(Integer, nullable=True)
    pp_shots = Column(Integer, nullable=True)
    pp_shots_on_goal = Column(Integer, nullable=True)

    # On-ice Corsi (raw counts)
    corsi_plus = Column(Integer, nullable=True)
    corsi_minus = Column(Integer, nullable=True)

    # Physical
    hits_delivered = Column(Integer, nullable=True)
    hits_received = Column(Integer, nullable=True)

    # Puck battles by zone
    pb_won_dz = Column(Integer, nullable=True)
    pb_total_dz = Column(Integer, nullable=True)
    pb_won_oz = Column(Integer, nullable=True)
    pb_total_oz = Column(Integer, nullable=True)
    pb_won_nz = Column(Integer, nullable=True)
    pb_total_nz = Column(Integer, nullable=True)

    # Turnovers / recoveries
    puck_losses = Column(Integer, nullable=True)
    puck_losses_dz = Column(Integer, nullable=True)
    puck_recoveries = Column(Integer, nullable=True)
    puck_recoveries_oz = Column(Integer, nullable=True)

    # Zone entries
    entries_pass = Column(Integer, nullable=True)
    entries_stick = Column(Integer, nullable=True)
    entries_dump = Column(Integer, nullable=True)

    player = relationship("Player")
    game = relationship("Game")
```

- [ ] **Step 4: Verify model tests pass**

Run: `cd backend && venv/bin/pytest tests/test_instat_player_model.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Add Pydantic schema**

Append to `backend/app/schemas.py`:
```python
class PlayerGameStatsInStat(BaseModel):
    id: int | None = None
    player_id: int
    game_id: int
    shots: int | None = None
    shots_on_goal: int | None = None
    blocked_shots: int | None = None
    pp_shots: int | None = None
    pp_shots_on_goal: int | None = None
    corsi_plus: int | None = None
    corsi_minus: int | None = None
    hits_delivered: int | None = None
    hits_received: int | None = None
    pb_won_dz: int | None = None
    pb_total_dz: int | None = None
    pb_won_oz: int | None = None
    pb_total_oz: int | None = None
    pb_won_nz: int | None = None
    pb_total_nz: int | None = None
    puck_losses: int | None = None
    puck_losses_dz: int | None = None
    puck_recoveries: int | None = None
    puck_recoveries_oz: int | None = None
    entries_pass: int | None = None
    entries_stick: int | None = None
    entries_dump: int | None = None

    class Config:
        from_attributes = True
```

(If the file already uses `orm_mode = True` on other classes, use `orm_mode` instead — match existing convention.)

- [ ] **Step 6: Append CREATE TABLE to migrate_v5.py**

Append to `backend/migrate_v5.py`:
```python
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
```

Move the `con.commit()` and `con.close()` and final `print("Migration v5 ... complete.")` line to the END of the file (below all task additions).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/migrate_v5.py backend/tests/test_instat_player_model.py
git commit -m "feat: add PlayerGameStatsInStat model for InStat-native player data"
```

---

### Task 4: `TeamGameStatsInStat` model + migration extension

**Files:**
- Modify: `backend/app/models.py` (add class)
- Modify: `backend/app/schemas.py` (add schema)
- Modify: `backend/migrate_v5.py` (append CREATE TABLE)
- Create: `backend/tests/test_instat_team_model.py`

**Interfaces:**
- Consumes: `Game` (FK)
- Produces: `TeamGameStatsInStat` model + `team_game_stats_instat` table

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_instat_team_model.py`:
```python
import pytest
from datetime import date
from app.models import Game, TeamGameStatsInStat


@pytest.fixture
def sample_game(db_session):
    g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True, season="2025-26",
             data_source="instat")
    db_session.add(g)
    db_session.commit()
    return g


class TestTeamGameStatsInStat:
    def test_can_create_row(self, db_session, sample_game):
        row = TeamGameStatsInStat(
            game_id=sample_game.id,
            pp_shots=12, pp_time_seconds_in_oz=317, pp_time_seconds_total=429,
            pk_opp_breakouts=6, pp_opp_breakouts_allowed=2,
            puck_possession_seconds_total=1197,
            oz_possession_seconds=597, oz_possession_pct=0.50,
            scoring_chance_shots=33, scoring_chance_shots_on_goal=24,
        )
        db_session.add(row)
        db_session.commit()
        assert row.id is not None

    def test_all_fields_default_none(self, db_session, sample_game):
        row = TeamGameStatsInStat(game_id=sample_game.id)
        db_session.add(row)
        db_session.commit()
        assert row.pp_shots is None
        assert row.oz_possession_pct is None

    def test_unique_game(self, db_session, sample_game):
        from sqlalchemy.exc import IntegrityError
        db_session.add(TeamGameStatsInStat(game_id=sample_game.id))
        db_session.commit()
        db_session.add(TeamGameStatsInStat(game_id=sample_game.id))
        with pytest.raises(IntegrityError):
            db_session.commit()
```

- [ ] **Step 2: Verify tests fail**

Run: `cd backend && venv/bin/pytest tests/test_instat_team_model.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add the SQLAlchemy model**

Append to `backend/app/models.py`:
```python
class TeamGameStatsInStat(Base):
    __tablename__ = "team_game_stats_instat"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), unique=True, nullable=False)

    # Special teams detail
    pp_shots = Column(Integer, nullable=True)
    pp_time_seconds_in_oz = Column(Integer, nullable=True)
    pp_time_seconds_total = Column(Integer, nullable=True)
    pk_opp_breakouts = Column(Integer, nullable=True)
    pp_opp_breakouts_allowed = Column(Integer, nullable=True)

    # Puck possession (5v5)
    puck_possession_seconds_total = Column(Integer, nullable=True)
    oz_possession_seconds = Column(Integer, nullable=True)
    oz_possession_pct = Column(Float, nullable=True)

    # Team-level shot quality
    scoring_chance_shots = Column(Integer, nullable=True)
    scoring_chance_shots_on_goal = Column(Integer, nullable=True)

    game = relationship("Game")
```

- [ ] **Step 4: Verify model tests pass**

Run: `cd backend && venv/bin/pytest tests/test_instat_team_model.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Add Pydantic schema**

Append to `backend/app/schemas.py`:
```python
class TeamGameStatsInStat(BaseModel):
    id: int | None = None
    game_id: int
    pp_shots: int | None = None
    pp_time_seconds_in_oz: int | None = None
    pp_time_seconds_total: int | None = None
    pk_opp_breakouts: int | None = None
    pp_opp_breakouts_allowed: int | None = None
    puck_possession_seconds_total: int | None = None
    oz_possession_seconds: int | None = None
    oz_possession_pct: float | None = None
    scoring_chance_shots: int | None = None
    scoring_chance_shots_on_goal: int | None = None

    class Config:
        from_attributes = True
```

(Match existing `orm_mode` convention if that's what other schemas use.)

- [ ] **Step 6: Append CREATE TABLE to migrate_v5.py**

Insert before the final `con.commit()`:
```python
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
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/migrate_v5.py backend/tests/test_instat_team_model.py
git commit -m "feat: add TeamGameStatsInStat model for InStat-native team data"
```

---

### Task 5: `STAT_SOURCES` declaration + availability helpers

**Files:**
- Create: `backend/app/stat_sources.py`
- Create: `backend/tests/test_stat_sources.py`

**Interfaces:**
- Consumes: `Game` (checks `game.data_source`)
- Produces:
  - `STAT_SOURCES: dict[str, set[str]]` — maps stat_key → set of `"49ing"` / `"instat"` values that can supply it
  - `stat_available_from(source: str, stat_key: str) -> bool` — does a game with `data_source == source` provide this stat?
  - `games_with_stat(games: list[Game], stat_key: str) -> list[Game]` — filter games where the stat is available
  - `AVAILABILITY_META = TypedDict` — the shape returned to callers

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_stat_sources.py`:
```python
import pytest
from datetime import date
from app.models import Game
from app.stat_sources import (
    STAT_SOURCES, stat_available_from, games_with_stat
)


class TestStatSources:
    def test_cf60_available_from_49ing(self):
        assert stat_available_from("49ing", "cf60") is True

    def test_cf60_available_from_both(self):
        # 49ing side of "both" supplies cf60
        assert stat_available_from("both", "cf60") is True

    def test_puck_battle_pct_only_from_instat(self):
        assert stat_available_from("instat", "puck_battle_pct") is True
        assert stat_available_from("49ing", "puck_battle_pct") is False
        assert stat_available_from("both", "puck_battle_pct") is True

    def test_attack_scenario_only_from_49ing(self):
        # Per spec §9: attack scenario xG is team-level 49ing-only
        assert stat_available_from("49ing", "rush_share") is True
        assert stat_available_from("instat", "rush_share") is False


class TestGamesWithStat:
    def _game(self, data_source, id_=None):
        g = Game(date=date(2025, 10, 1), opponent="X",
                 is_home=True, season="2025-26", data_source=data_source)
        if id_ is not None:
            g.id = id_
        return g

    def test_filters_49ing_games_out_for_instat_only_stat(self):
        games = [self._game("49ing", 1), self._game("instat", 2), self._game("both", 3)]
        result = games_with_stat(games, "puck_battle_pct")
        ids = {g.id for g in result}
        assert ids == {2, 3}

    def test_keeps_all_when_stat_is_universal(self):
        games = [self._game("49ing", 1), self._game("instat", 2), self._game("both", 3)]
        result = games_with_stat(games, "toi_5v5")  # TOI both sources supply
        assert len(result) == 3

    def test_empty_for_stat_no_source_supplies(self):
        games = [self._game("49ing", 1)]
        result = games_with_stat(games, "totally_unknown_stat")
        assert result == []


class TestStatSourcesCoverage:
    def test_all_existing_stat_keys_declared(self):
        """Every stat currently returned by aggregate_player_stats or
        aggregate_team_stats must have an entry in STAT_SOURCES so the
        aggregation layer doesn't accidentally filter to zero games."""
        existing_player_stats = {
            "toi_5v5", "on_ice_cf_pct", "on_ice_xgf_pct", "on_ice_sf_pct",
            "cf60", "ca60", "ff60", "fa60", "sf60", "sa60",
            "xfsh_pct", "xfsv_pct",
            "icf", "isf",
            "median_shift_seconds",
            "personal_fo_pct", "on_ice_fo_pct",
        }
        existing_team_stats = {
            "cf_pct", "xgf_pct", "xgf60", "xga60",
            "pp_cf_pct", "pp_xgf_pct", "pk_cf_pct", "pk_xgf_pct",
            "rush_share", "oz_fc_share", "oz_fo_share", "sust_pos_share",
        }
        missing = (existing_player_stats | existing_team_stats) - set(STAT_SOURCES.keys())
        assert not missing, f"Missing STAT_SOURCES entries for: {missing}"
```

- [ ] **Step 2: Verify tests fail**

Run: `cd backend && venv/bin/pytest tests/test_stat_sources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.stat_sources'`.

- [ ] **Step 3: Implement the module**

Create `backend/app/stat_sources.py`:
```python
"""Source-availability declarations for every tracked stat.

Each stat_key maps to the set of Game.data_source values that supply the
data required to compute it. A game with data_source == "both" satisfies
either single-source requirement (source merge preference is 49ing per
spec §2, applied at the aggregation layer per-stat).

Adding a new stat: add its key here with the sources it needs, or the
aggregation layer will silently drop all games from its window.
"""
from typing import Iterable
from .models import Game


# Sources for stats produced by aggregate_player_stats
_PLAYER_STAT_SOURCES: dict[str, set[str]] = {
    # 49ing supplies per-60 rates and on-ice percentages directly.
    # InStat supplies raw Corsi counts that can be scaled to per-60.
    # Both are marked here; aggregation prefers 49ing when a game has both.
    "toi_5v5":         {"49ing", "instat"},
    "on_ice_cf_pct":   {"49ing", "instat"},
    "on_ice_xgf_pct":  {"49ing"},               # xG not available from InStat per player
    "on_ice_sf_pct":   {"49ing", "instat"},
    "cf60":            {"49ing", "instat"},
    "ca60":            {"49ing", "instat"},
    "ff60":            {"49ing"},
    "fa60":            {"49ing"},
    "sf60":            {"49ing", "instat"},
    "sa60":            {"49ing", "instat"},
    "xfsh_pct":        {"49ing"},
    "xfsv_pct":        {"49ing"},
    "icf":             {"49ing", "instat"},     # ICF = shots attempted (either source has raw counts)
    "isf":             {"49ing", "instat"},
    "median_shift_seconds": {"49ing"},          # 49ing exposes median directly; InStat exposes shift timeline only
    "personal_fo_pct": {"49ing", "instat"},
    "on_ice_fo_pct":   {"49ing", "instat"},
}

# Sources for stats produced by aggregate_team_stats
_TEAM_STAT_SOURCES: dict[str, set[str]] = {
    "cf_pct":         {"49ing", "instat"},
    "xgf_pct":        {"49ing"},                # team xG per game — 49ing only
    "xgf60":          {"49ing"},
    "xga60":          {"49ing"},
    "pp_cf_pct":      {"49ing", "instat"},
    "pp_xgf_pct":     {"49ing"},
    "pk_cf_pct":      {"49ing", "instat"},
    "pk_xgf_pct":     {"49ing"},
    "rush_share":     {"49ing"},                # attack-scenario xG — 49ing only per spec §9
    "oz_fc_share":    {"49ing"},
    "oz_fo_share":    {"49ing"},
    "sust_pos_share": {"49ing"},
}

STAT_SOURCES: dict[str, set[str]] = {
    **_PLAYER_STAT_SOURCES,
    **_TEAM_STAT_SOURCES,
    # Add future stats here as they are built (Phase 3+):
    # "puck_battle_pct":  {"instat"},
    # "pb_dz_pct":        {"instat"},
    # "pb_oz_pct":        {"instat"},
    # "entry_pass_pct":   {"instat"},
    # "impact_score":     {"49ing", "instat"},
}

# Phase-2/3 stats declared here even though no aggregation yet reads them,
# so the availability layer answers correctly the moment they land:
STAT_SOURCES["puck_battle_pct"] = {"instat"}
STAT_SOURCES["pb_dz_pct"] = {"instat"}
STAT_SOURCES["pb_oz_pct"] = {"instat"}
STAT_SOURCES["pb_nz_pct"] = {"instat"}
STAT_SOURCES["entry_pass_pct"] = {"instat"}
STAT_SOURCES["entry_stick_pct"] = {"instat"}
STAT_SOURCES["entry_dump_pct"] = {"instat"}
STAT_SOURCES["impact_score"] = {"49ing", "instat"}


def stat_available_from(data_source: str, stat_key: str) -> bool:
    """Does a game tagged with data_source supply the data needed for stat_key?"""
    needed = STAT_SOURCES.get(stat_key)
    if needed is None:
        return False
    if data_source == "both":
        # Any-of; both sides are present so anything either source has is available.
        return bool(needed)
    return data_source in needed


def games_with_stat(games: Iterable[Game], stat_key: str) -> list[Game]:
    """Filter to games where this stat's source data is available."""
    return [g for g in games if stat_available_from(g.data_source, stat_key)]
```

- [ ] **Step 4: Verify all tests pass**

Run: `cd backend && venv/bin/pytest tests/test_stat_sources.py -v`
Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/stat_sources.py backend/tests/test_stat_sources.py
git commit -m "feat: add STAT_SOURCES declaration and game filtering helpers"
```

---

### Task 6: Aggregation layer availability metadata

**Files:**
- Modify: `backend/app/calculations.py` (extend both aggregate functions with an `availability` return field)
- Create: `backend/tests/test_source_aware_aggregation.py`

**Interfaces:**
- Consumes: `STAT_SOURCES`, `games_with_stat` from `app.stat_sources`
- Produces:
  - `aggregate_player_stats` return dict gains a new `"availability"` key:
    `{"cf60": {"games": 12, "sources": ["49ing"]}, ...}`
  - `aggregate_team_stats` return dict gains the same `"availability"` key
  - Signatures unchanged (still take player/rows/games or rows/games)

**Note:** Phase 0 does NOT change how stat values are computed. All existing 49ing games will report `sources: ["49ing"]` and `games: <same as before>` for every stat, because backfill made every existing row `data_source="49ing"` and every 49ing-supported stat has that source. The availability layer becomes meaningful once InStat games start landing.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_source_aware_aggregation.py`:
```python
import pytest
from datetime import date, timedelta
from app.models import Player, Game, PlayerGameStats, TeamGameStats
from app.calculations import aggregate_player_stats, aggregate_team_stats


@pytest.fixture
def player(db_session):
    p = Player(name="Test", number="10", position="F", is_center=True, active=True)
    db_session.add(p)
    db_session.commit()
    return p


@pytest.fixture
def games_mixed_sources(db_session):
    games = []
    for i, source in enumerate(["49ing", "49ing", "instat"]):
        g = Game(date=date(2025, 10, 1) + timedelta(days=i * 4),
                 opponent=f"O{i}", is_home=True, season="2025-26",
                 data_source=source)
        db_session.add(g)
        games.append(g)
    db_session.commit()
    return games


class TestAggregatePlayerStatsAvailability:
    def test_returns_availability_dict(self, db_session, player, games_mixed_sources):
        # Add per-60 rows for the two 49ing games only
        for g in games_mixed_sources[:2]:
            db_session.add(PlayerGameStats(
                player_id=player.id, game_id=g.id,
                toi_5v5=15.0, cf60=50.0, ca60=40.0,
                xgf60=2.5, xga60=2.0,
                ff60=40.0, fa60=30.0, sf60=25.0, sa60=20.0,
            ))
        db_session.commit()
        pgs_rows = db_session.query(PlayerGameStats).filter_by(player_id=player.id).all()

        result = aggregate_player_stats(player, pgs_rows, games_mixed_sources)

        assert "availability" in result
        # cf60 is available from both sources → all 3 games "count" for the window,
        # but only 2 have data → availability reports the 2
        assert result["availability"]["cf60"]["games"] == 2
        # xfsh_pct is 49ing-only → available games = 2, both marked 49ing
        assert result["availability"]["xfsh_pct"]["games"] == 2
        assert set(result["availability"]["xfsh_pct"]["sources"]) == {"49ing"}


class TestAggregateTeamStatsAvailability:
    def test_returns_availability_dict(self, db_session, games_mixed_sources):
        for g in games_mixed_sources[:2]:
            db_session.add(TeamGameStats(
                game_id=g.id,
                cf_for_5v5=60, cf_against_5v5=40,
                xgf_5v5=2.5, xga_5v5=2.0,
                total_game_time=60, toi_pp=5, toi_pk=5, other_toi=0,
            ))
        db_session.commit()
        tgs_rows = db_session.query(TeamGameStats).all()

        result = aggregate_team_stats(tgs_rows, games_mixed_sources)

        assert "availability" in result
        # xgf_pct 49ing-only, 2 games have data
        assert result["availability"]["xgf_pct"]["games"] == 2
        # cf_pct is both-source; 2 games have data (49ing rows only for now)
        assert result["availability"]["cf_pct"]["games"] == 2
```

- [ ] **Step 2: Verify tests fail**

Run: `cd backend && venv/bin/pytest tests/test_source_aware_aggregation.py -v`
Expected: FAIL with `KeyError: 'availability'`.

- [ ] **Step 3: Extend the aggregators**

Read `backend/app/calculations.py`. Locate `aggregate_player_stats` and `aggregate_team_stats`.

Add the following helper at the top of the file (below imports):
```python
from .stat_sources import STAT_SOURCES, games_with_stat


def _availability_for(games: list, stat_keys: list[str], rows_by_game_id: dict) -> dict:
    """Build the per-stat availability metadata block.

    games: the game set for the window (filtered by date range at the router).
    stat_keys: which stat_keys to report on.
    rows_by_game_id: mapping game_id → row (the data-holding row; PlayerGameStats
    for player aggregation, TeamGameStats for team). Presence indicates a row exists.
    """
    out = {}
    for key in stat_keys:
        eligible = games_with_stat(games, key)
        # Restrict to games that actually have a data row loaded (empty stats
        # rows exist for backfilled games; we still count them because the
        # user entered them as 49ing games, i.e. data intentionally missing is
        # different from source-unsupported).
        eligible_ids = {g.id for g in eligible}
        counted = sum(1 for gid in eligible_ids if gid in rows_by_game_id)
        sources = sorted({g.data_source if g.data_source != "both" else "49ing"
                          for g in eligible if g.id in rows_by_game_id})
        out[key] = {"games": counted, "sources": sources}
    return out
```

In `aggregate_player_stats`, right before the `return` statement, add:
```python
    rows_by_game_id = {r.game_id: r for r in pgs_rows}
    player_stat_keys = [
        "toi_5v5", "on_ice_cf_pct", "on_ice_xgf_pct", "on_ice_sf_pct",
        "cf60", "ca60", "ff60", "fa60", "sf60", "sa60",
        "xfsh_pct", "xfsv_pct", "icf", "isf",
        "median_shift_seconds", "personal_fo_pct", "on_ice_fo_pct",
    ]
    result["availability"] = _availability_for(games, player_stat_keys, rows_by_game_id)
    return result
```

(Assume the existing function returns a dict named `result` at the end. If it builds and returns the dict inline, refactor to a `result = { ... }` then `result["availability"] = ...; return result` pattern. Do NOT change any existing computed field's value — only add the availability block.)

In `aggregate_team_stats`, apply the equivalent change:
```python
    rows_by_game_id = {r.game_id: r for r in team_stats_rows}
    team_stat_keys = [
        "cf_pct", "xgf_pct", "xgf60", "xga60",
        "pp_cf_pct", "pp_xgf_pct", "pk_cf_pct", "pk_xgf_pct",
        "rush_share", "oz_fc_share", "oz_fo_share", "sust_pos_share",
    ]
    result["availability"] = _availability_for(games, team_stat_keys, rows_by_game_id)
    return result
```

- [ ] **Step 4: Verify all tests pass**

Run: `cd backend && venv/bin/pytest tests/test_source_aware_aggregation.py -v`
Expected: 2 tests pass.

Also run the whole suite to confirm no regressions on Phase 1 tests if present:
```
cd backend && venv/bin/pytest -q
```
Expected: all previously-passing tests still pass (Phase 0's additions add rows).

- [ ] **Step 5: Commit**

```bash
git add backend/app/calculations.py backend/tests/test_source_aware_aggregation.py
git commit -m "feat: aggregate functions emit per-stat availability metadata"
```

---

### Task 7: Frontend types + N/A rendering

**Files:**
- Modify: `frontend/src/types.ts` (add `data_source` to `Game`, add `availability` to `PlayerAggStats` and `TeamAggStats`)
- Modify: `frontend/src/components/StatCard.tsx` OR `ReportsPage.tsx` (render "N/A" when a stat's availability reports zero games)

**Interfaces:**
- Consumes: JSON shape from `/api/stats/player/{id}` and `/api/stats/team` — both now include `availability: Record<string, {games: number; sources: string[]}>`
- Consumes: `Game` now includes `data_source`

- [ ] **Step 1: Extend types**

Modify `frontend/src/types.ts`:

Add to the `Game` interface (near the existing fields):
```typescript
  data_source: '49ing' | 'instat' | 'both'
```

Add a new interface near `Baseline`:
```typescript
export interface StatAvailability {
  games: number
  sources: string[]
}
```

Extend `PlayerAggStats` with:
```typescript
  availability?: Record<string, StatAvailability>
```

Extend `TeamAggStats` with:
```typescript
  availability?: Record<string, StatAvailability>
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors. (Some may appear if existing code accesses these fields; the type is optional so no callers should break.)

- [ ] **Step 3: Render N/A for insufficient availability**

Read `frontend/src/components/StatCard.tsx` to understand how it currently renders a stat value.

Add a check: if `availability?.[statKey]?.games === 0`, render "N/A" (with a small tooltip label like "source not available for this window"). Otherwise, render as before.

Concrete change: at the top of `StatCard`, accept an optional `availability?: StatAvailability` prop. In the value-rendering block, replace the current formatted value with:

```tsx
{availability && availability.games === 0
  ? <span style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }} title={`Source ${availability.sources.join(', ') || 'unavailable'} for this window`}>N/A</span>
  : <the existing value expression>}
```

If StatCard doesn't currently take a `statKey` or availability, the simplest thing is to add an optional `availability?: {games: number; sources: string[]}` prop and let callers pass it. Do NOT rewire every existing caller — the prop is optional and defaults to unset, so existing behavior is preserved.

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Manual verification (deferred)**

Note in the report that manual verification is deferred: the availability block won't have `games === 0` values until Phase 2 ingests real InStat games. To verify prematurely, the coach can temporarily change one game's `data_source` to `"instat"` in the DB and re-fetch the report — an InStat-only stat should show "N/A".

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/components/StatCard.tsx
git commit -m "feat: expose data_source and stat availability metadata in frontend"
```

---

## Final verification

- [ ] **Run migration against a real DB** — verify idempotency:
  ```
  cd backend && venv/bin/python migrate_v5.py
  cd backend && venv/bin/python migrate_v5.py   # second run — should print "Skipped" and "already exists"
  ```

- [ ] **Full backend suite:** `cd backend && venv/bin/pytest -v` → all tests pass (Phase 1's tests too if the branch base has them; otherwise Phase 0 tests only).

- [ ] **Typecheck:** `cd frontend && npx tsc --noEmit` → no errors.

- [ ] **Verify no regression on existing endpoints:** hit `/api/stats/player/{id}` with an existing game window and confirm the response includes `availability` and every stat still has a numeric value.

- [ ] **Ledger deferred items for Phase 3+:**
  - Dual-source merge math (49ing precedence when both present) — deferred per-stat as new stats need it.
  - Manual InStat data entry UI — deferred to Phase 2 ingest.
  - Population of `PlayerGameStatsInStat` / `TeamGameStatsInStat` rows — deferred to Phase 2 ingest.
  - Source picker in game creation form — deferred until manual InStat entry becomes useful (currently every manual entry is 49ing).
