# Phase 2: InStat PDF Ingest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate InStat match-report ingest end-to-end: user uploads a PDF, server parses six templates against the deterministic PDF layout, user reviews the extracted values in an editable form, commits to DB. Replaces the manual data-entry pain point for every InStat-sourced game.

**Architecture:** Free/deterministic pipeline built on `pdfplumber`. A section navigator locates our team's pages by header text (not fixed page numbers). Six per-template parsers each return a structured dict. An orchestrator runs all six on one PDF, validators annotate each field, results are stored as an `IngestRun` row (`parsed_json` blob + status). A React review page renders the parsed values, lets the user correct anything, then commits atomically to `TeamGameStatsInStat`, `PlayerGameStatsInStat`, `PlayerGameStats` (TOI only), `PlayerHitMatrix`, and `PlayerPassMatrix`.

**Tech Stack:** Python 3.9 · FastAPI · SQLAlchemy · SQLite · `pdfplumber` (new dep) · Pydantic v2 · React + TypeScript + Vite.

**Spec:** `docs/superpowers/specs/2026-08-18-ecac-stats-expansion-design.md` (§3 matrix tables, §4 ingest pipeline).

## Global Constraints

- **Free tool.** No paid dependencies, no API keys, no external services. `pdfplumber` is the only new backend dependency.
- **PDF format:** InStat match-report, 19 pages, section headers of the form `"<SECTION>: <TEAM NAME> <page number>"`. Empirically verified against `Princeton_Tigers_-_Harvard_Crimson._Match_report_(eng) (1).pdf`.
- **Our team:** initially hardcoded as `OUR_TEAM_NAME = "HARVARD CRIMSON"` in `app/config.py`. Parsers use this to pick our team's pages.
- **Team-stats page (P2) side-by-side format:** columns alternate `PT HC PT HC` (visiting-team value then our-team value, repeated across stats). Parser picks the "HC" (home / our-team) column via team-name detection in the header row, NOT positional assumption.
- **Migration script:** raw `sqlite3` with `try/except` on `ADD COLUMN`, `CREATE TABLE IF NOT EXISTS`. Match Phase 0's `migrate_v5.py` style. File name: `backend/migrate_v6.py`.
- **Test runner:** `backend/venv/bin/python -m pytest` from worktree root. There is no `pytest` binary in `venv/bin/`.
- **Pydantic style:** v2 (`model_config = {"from_attributes": True}`). Match schemas.py convention.
- **Commit style:** conventional-commits (`feat:`, `test:`, `fix:`, `chore:`).
- **Frontend typecheck:** `cd frontend && npx tsc --noEmit` must pass with zero errors after every frontend-touching task.
- **Fixture PDF:** the sample report lives at repo root; Task 1 copies it into `backend/tests/fixtures/instat_sample.pdf` so parsers have a stable path to test against. All parser tests use this fixture.
- **Idempotency:** re-running `migrate_v6.py` on a DB that already has the new tables must succeed silently.
- **No changes to existing computed stats.** Phase 2 populates new source tables and (for InStat-sourced games) `PlayerGameStats` TOI fields. Existing 49ing-sourced games are untouched.
- **Commit-time behavior:** if a game already has data in one of the target tables (e.g. re-ingest of the same game), the commit endpoint upserts by `(game_id, player_id)` where applicable, replacing prior values. This is intentional — coach may re-upload a corrected PDF.
- **Existing manual-entry endpoints untouched.** Coach may still enter InStat data manually and 49ing data always manually.

---

### Task 1: Dependencies, config, and fixture

**Files:**
- Modify: `backend/requirements.txt` (add `pdfplumber`)
- Create: `backend/app/config.py`
- Create: `backend/tests/fixtures/instat_sample.pdf` (copy of repo-root sample)
- Create: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `OUR_TEAM_NAME: str = "HARVARD CRIMSON"` (importable from `app.config`)
  - Fixture PDF at `backend/tests/fixtures/instat_sample.pdf`

- [ ] **Step 1: Add pdfplumber to requirements**

Append to `backend/requirements.txt`:
```
pdfplumber>=0.11.0
```

Run: `backend/venv/bin/python -m pip install pdfplumber`
Expected: successful install.

- [ ] **Step 2: Create app/config.py**

Create `backend/app/config.py`:
```python
"""Static configuration for the ECAC stats app.

Values here are project-wide constants that don't belong in a per-request
settings object. When the app ever tracks more than one team, `OUR_TEAM_NAME`
moves into a Settings table.
"""

OUR_TEAM_NAME = "HARVARD CRIMSON"
```

- [ ] **Step 3: Copy fixture PDF**

Create the fixtures directory and copy the sample PDF:
```bash
mkdir -p backend/tests/fixtures
cp "Princeton_Tigers_-_Harvard_Crimson._Match_report_(eng) (1).pdf" backend/tests/fixtures/instat_sample.pdf
```
Expected: `backend/tests/fixtures/instat_sample.pdf` exists, ~1.4 MB.

- [ ] **Step 4: Add a smoke test**

Create `backend/tests/test_config.py`:
```python
import os
from app.config import OUR_TEAM_NAME


def test_our_team_name_is_string():
    assert isinstance(OUR_TEAM_NAME, str)
    assert OUR_TEAM_NAME  # non-empty


def test_fixture_pdf_exists():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")
    assert os.path.exists(path)
    assert os.path.getsize(path) > 100_000  # sanity: real PDF, not empty
```

Run: `backend/venv/bin/python -m pytest backend/tests/test_config.py -v`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/app/config.py backend/tests/fixtures/instat_sample.pdf backend/tests/test_config.py
git commit -m "chore: add pdfplumber dep, our-team config, and InStat fixture PDF"
```

---

### Task 2: Schema — `IngestRun`, `PlayerHitMatrix`, `PlayerPassMatrix` + migration

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/migrate_v6.py`
- Create: `backend/tests/test_ingest_schema.py`

**Interfaces:**
- Consumes: existing `Player`, `Game`, `Base` from models.py.
- Produces:
  - `IngestRun` SQLAlchemy model
  - `PlayerHitMatrix` SQLAlchemy model
  - `PlayerPassMatrix` SQLAlchemy model
  - Matching Pydantic schemas
  - `migrate_v6.py` — idempotent script that creates all three tables

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_ingest_schema.py`:
```python
import pytest
from datetime import date, datetime
from app.models import (
    Player, Game, IngestRun, PlayerHitMatrix, PlayerPassMatrix,
)


@pytest.fixture
def two_players_and_game(db_session):
    p1 = Player(name="Alpha", number="10", position="F", is_center=True, active=True)
    p2 = Player(name="Bravo", number="7",  position="F", is_center=False, active=True)
    g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True,
             season="2025-26", data_source="instat")
    for obj in (p1, p2, g):
        db_session.add(obj)
    db_session.commit()
    return p1, p2, g


class TestIngestRun:
    def test_can_create(self, db_session, two_players_and_game):
        _, _, g = two_players_and_game
        run = IngestRun(
            game_id=g.id,
            filename="test.pdf",
            parsed_json='{"foo": "bar"}',
            status="pending_review",
        )
        db_session.add(run)
        db_session.commit()
        assert run.id is not None
        assert run.uploaded_at is not None  # auto-populated

    def test_status_defaults_to_pending(self, db_session, two_players_and_game):
        _, _, g = two_players_and_game
        run = IngestRun(game_id=g.id, filename="t.pdf", parsed_json="{}")
        db_session.add(run)
        db_session.commit()
        assert run.status == "pending_review"


class TestPlayerHitMatrix:
    def test_can_create_row(self, db_session, two_players_and_game):
        p1, p2, g = two_players_and_game
        row = PlayerHitMatrix(
            game_id=g.id, from_player_id=p1.id, to_player_id=p2.id,
            delivered=3, received=1,
        )
        db_session.add(row)
        db_session.commit()
        assert row.id is not None

    def test_unique_game_from_to(self, db_session, two_players_and_game):
        from sqlalchemy.exc import IntegrityError
        p1, p2, g = two_players_and_game
        db_session.add(PlayerHitMatrix(game_id=g.id, from_player_id=p1.id,
                                       to_player_id=p2.id, delivered=1, received=0))
        db_session.commit()
        db_session.add(PlayerHitMatrix(game_id=g.id, from_player_id=p1.id,
                                       to_player_id=p2.id, delivered=2, received=0))
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestPlayerPassMatrix:
    def test_can_create_row(self, db_session, two_players_and_game):
        p1, p2, g = two_players_and_game
        row = PlayerPassMatrix(game_id=g.id, from_player_id=p1.id,
                               to_player_id=p2.id, count=7)
        db_session.add(row)
        db_session.commit()
        assert row.id is not None

    def test_unique_game_from_to(self, db_session, two_players_and_game):
        from sqlalchemy.exc import IntegrityError
        p1, p2, g = two_players_and_game
        db_session.add(PlayerPassMatrix(game_id=g.id, from_player_id=p1.id,
                                        to_player_id=p2.id, count=5))
        db_session.commit()
        db_session.add(PlayerPassMatrix(game_id=g.id, from_player_id=p1.id,
                                        to_player_id=p2.id, count=6))
        with pytest.raises(IntegrityError):
            db_session.commit()
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_ingest_schema.py -v`
Expected: `ImportError: cannot import name 'IngestRun' from 'app.models'` (or similar).

- [ ] **Step 3: Add the models**

Append to `backend/app/models.py` (verify `DateTime` is imported at the top; if not, add it to the `sqlalchemy` import line):

```python
class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    parsed_json = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending_review")
    # values: "pending_review" | "committed" | "discarded" | "failed"
    committed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    game = relationship("Game")


class PlayerHitMatrix(Base):
    __tablename__ = "player_hit_matrix"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    from_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    to_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    delivered = Column(Integer, nullable=False, default=0)
    received = Column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("game_id", "from_player_id", "to_player_id"),)


class PlayerPassMatrix(Base):
    __tablename__ = "player_pass_matrix"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    from_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    to_player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    count = Column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("game_id", "from_player_id", "to_player_id"),)
```

Verify at top of file: `Text` and `DateTime` imports, `datetime` from `datetime`. Add if missing:
```python
from datetime import datetime
from sqlalchemy import ..., Text, DateTime
```

- [ ] **Step 4: Add matching Pydantic schemas**

Append to `backend/app/schemas.py`:

```python
class IngestRunOut(BaseModel):
    id: int
    game_id: int
    filename: str
    uploaded_at: datetime
    status: str
    committed_at: Optional[datetime] = None
    error: Optional[str] = None

    model_config = {"from_attributes": True}


class PlayerHitMatrixOut(BaseModel):
    id: Optional[int] = None
    game_id: int
    from_player_id: int
    to_player_id: int
    delivered: int
    received: int

    model_config = {"from_attributes": True}


class PlayerPassMatrixOut(BaseModel):
    id: Optional[int] = None
    game_id: int
    from_player_id: int
    to_player_id: int
    count: int

    model_config = {"from_attributes": True}
```

Verify `from datetime import datetime` and `Optional` imports at top of file. Add if missing.

- [ ] **Step 5: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_ingest_schema.py -v`
Expected: 5 tests pass.

- [ ] **Step 6: Write migration**

Create `backend/migrate_v6.py`:
```python
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
```

- [ ] **Step 7: Verify migration is idempotent**

Run migration twice against a scratch DB:
```bash
cp backend/ecac_stats.db /tmp/scratch_v6.db
DB_ORIG=$(realpath backend/ecac_stats.db)
cp /tmp/scratch_v6.db backend/ecac_stats.db  # use scratch copy
backend/venv/bin/python backend/migrate_v6.py
backend/venv/bin/python backend/migrate_v6.py  # second run: should not error
cp "$DB_ORIG" backend/ecac_stats.db 2>/dev/null || true  # restore
rm /tmp/scratch_v6.db
```
Expected: both runs print "Created ..." (SQLite `CREATE TABLE IF NOT EXISTS` is silent on already-exists), no exceptions.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/migrate_v6.py backend/tests/test_ingest_schema.py
git commit -m "feat: add IngestRun, PlayerHitMatrix, PlayerPassMatrix tables (migration v6)"
```

---

### Task 3: PDF section navigator

**Files:**
- Create: `backend/app/ingest/__init__.py` (empty)
- Create: `backend/app/ingest/pdf_nav.py`
- Create: `backend/tests/test_pdf_nav.py`

**Interfaces:**
- Consumes: `pdfplumber`, `OUR_TEAM_NAME` from `app.config`.
- Produces:
  - `find_section_page(pdf, section: str, team: str) -> int | None` — returns 0-indexed page number for the section belonging to `team`, or None if not found. Section values: `"TEAMS STATS 2"`, `"PLAYERS' STATS"`, `"GAME TIME DISTRIBUTION"`, `"CHALLENGES"`, `"HITS DISTRIBUTION"`, `"PASSES DISTRIBUTION"`.
  - `find_our_team_section_page(pdf, section: str) -> int | None` — thin wrapper that uses `OUR_TEAM_NAME`.
  - `TEAMS_STATS_SECTION`, `PLAYERS_STATS_SECTION`, etc. — string constants for the six section names.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_pdf_nav.py`:
```python
import os
import pytest
import pdfplumber
from app.ingest.pdf_nav import (
    find_section_page, find_our_team_section_page,
    TEAMS_STATS_SECTION, PLAYERS_STATS_SECTION,
    GAME_TIME_SECTION, CHALLENGES_SECTION,
    HITS_DISTRIBUTION_SECTION, PASSES_DISTRIBUTION_SECTION,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestFindSectionPage:
    def test_teams_stats_on_page_2(self, pdf):
        # Teams stats section is match-wide (no team suffix); team parameter ignored
        assert find_section_page(pdf, TEAMS_STATS_SECTION, "HARVARD CRIMSON") == 1

    def test_harvard_players_on_page_11(self, pdf):
        assert find_section_page(pdf, PLAYERS_STATS_SECTION, "HARVARD CRIMSON") == 10

    def test_princeton_players_on_page_3(self, pdf):
        assert find_section_page(pdf, PLAYERS_STATS_SECTION, "PRINCETON TIGERS") == 2

    def test_harvard_hits_matrix_on_page_17(self, pdf):
        assert find_section_page(pdf, HITS_DISTRIBUTION_SECTION, "HARVARD CRIMSON") == 16

    def test_harvard_passes_matrix_on_page_18(self, pdf):
        assert find_section_page(pdf, PASSES_DISTRIBUTION_SECTION, "HARVARD CRIMSON") == 17

    def test_harvard_challenges_on_page_15(self, pdf):
        assert find_section_page(pdf, CHALLENGES_SECTION, "HARVARD CRIMSON") == 14

    def test_harvard_time_distribution_on_page_13(self, pdf):
        assert find_section_page(pdf, GAME_TIME_SECTION, "HARVARD CRIMSON") == 12

    def test_returns_none_when_team_not_found(self, pdf):
        assert find_section_page(pdf, PLAYERS_STATS_SECTION, "NONEXISTENT TEAM") is None


class TestFindOurTeamSectionPage:
    def test_defaults_to_our_team_name(self, pdf):
        # OUR_TEAM_NAME = "HARVARD CRIMSON" per app.config
        assert find_our_team_section_page(pdf, PLAYERS_STATS_SECTION) == 10
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_pdf_nav.py -v`
Expected: `ModuleNotFoundError: No module named 'app.ingest.pdf_nav'`.

- [ ] **Step 3: Implement the module**

Create `backend/app/ingest/__init__.py` (empty).

Create `backend/app/ingest/pdf_nav.py`:
```python
"""PDF section navigation for InStat match reports.

InStat's PDF layout is 19 pages with a symmetric per-team structure. Section
headers follow the pattern:

    <SECTION_NAME>: <TEAM NAME> <page number>

The match-wide TEAMS STATS section is an exception — it has no team suffix
because it's shared. We match sections by scanning the first ~5 lines of
each page's text; if the section is team-scoped, we also require the team
name to be present on the same line.
"""
from typing import Optional
import pdfplumber
from ..config import OUR_TEAM_NAME


# Section names as they appear in PDF headers
TEAMS_STATS_SECTION = "TEAMS STATS 2"           # match-wide
PLAYERS_STATS_SECTION = "PLAYERS' STATS"        # team-scoped
GAME_TIME_SECTION = "GAME TIME DISTRIBUTION"    # team-scoped
CHALLENGES_SECTION = "CHALLENGES"               # team-scoped
HITS_DISTRIBUTION_SECTION = "HITS DISTRIBUTION"     # team-scoped
PASSES_DISTRIBUTION_SECTION = "PASSES DISTRIBUTION" # team-scoped


# Match-wide sections don't carry a team suffix
_MATCH_WIDE_SECTIONS = {TEAMS_STATS_SECTION}


def find_section_page(
    pdf: pdfplumber.PDF, section: str, team: str
) -> Optional[int]:
    """Locate the 0-indexed page containing `section` for `team`.

    For match-wide sections (TEAMS STATS 2), the team argument is ignored.
    Returns None if the section isn't found or the team suffix doesn't match.
    """
    is_match_wide = section in _MATCH_WIDE_SECTIONS
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        for line in text.splitlines()[:5]:
            if section not in line:
                continue
            if is_match_wide:
                return i
            # Team-scoped: require the team name on the same header line
            if team in line:
                return i
    return None


def find_our_team_section_page(
    pdf: pdfplumber.PDF, section: str
) -> Optional[int]:
    """Convenience wrapper: locate a section for OUR_TEAM_NAME."""
    return find_section_page(pdf, section, OUR_TEAM_NAME)
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_pdf_nav.py -v`
Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/__init__.py backend/app/ingest/pdf_nav.py backend/tests/test_pdf_nav.py
git commit -m "feat: add PDF section navigator for InStat match reports"
```

---

### Task 4: Parser — `instat_team_stats` (P2)

**Files:**
- Create: `backend/app/ingest/parsers/__init__.py` (empty)
- Create: `backend/app/ingest/parsers/team_stats.py`
- Create: `backend/tests/test_parse_team_stats.py`

**Interfaces:**
- Consumes: `pdfplumber`, `find_section_page` from `app.ingest.pdf_nav`, `OUR_TEAM_NAME` from `app.config`.
- Produces:
  - `parse_team_stats(pdf: pdfplumber.PDF, our_team: str) -> dict` — returns dict with keys matching `TeamGameStatsInStat` columns: `pp_shots`, `pp_time_seconds_in_oz`, `pp_time_seconds_total`, `pk_opp_breakouts`, `pp_opp_breakouts_allowed`, `puck_possession_seconds_total`, `oz_possession_seconds`, `oz_possession_pct`, `scoring_chance_shots`, `scoring_chance_shots_on_goal`. Values are `int`/`float` or `None` if the field couldn't be extracted.

**Discovery guidance:** The parser needs to interpret P2's side-by-side layout (columns alternate visiting-team, our-team). Before writing the implementation, open the fixture with `pdfplumber` interactively to see the exact table structure. Example REPL exploration:

```python
import pdfplumber
with pdfplumber.open("backend/tests/fixtures/instat_sample.pdf") as pdf:
    p = pdf.pages[1]
    print("--- text ---")
    print(p.extract_text())
    print("--- tables ---")
    for i, t in enumerate(p.extract_tables()):
        print(f"table {i}:")
        for row in t:
            print("  ", row)
```

The header row (first table row after any title) contains team abbreviations (`PT HC`). Use the position of `HC` (or the position matching `our_team`) to pick our team's values from subsequent rows.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_parse_team_stats.py`:
```python
import os
import pytest
import pdfplumber
from app.ingest.parsers.team_stats import parse_team_stats

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseTeamStats:
    def test_returns_dict_with_expected_keys(self, pdf):
        result = parse_team_stats(pdf, our_team="HARVARD CRIMSON")
        expected_keys = {
            "pp_shots", "pp_time_seconds_in_oz", "pp_time_seconds_total",
            "pk_opp_breakouts", "pp_opp_breakouts_allowed",
            "puck_possession_seconds_total",
            "oz_possession_seconds", "oz_possession_pct",
            "scoring_chance_shots", "scoring_chance_shots_on_goal",
        }
        assert set(result.keys()) >= expected_keys

    def test_values_are_numeric_or_none(self, pdf):
        result = parse_team_stats(pdf, our_team="HARVARD CRIMSON")
        for key, val in result.items():
            assert val is None or isinstance(val, (int, float)), (
                f"{key}={val!r} is not numeric or None"
            )

    def test_percentage_field_is_normalized(self, pdf):
        # oz_possession_pct should be 0.0-1.0, not 0-100 (matches model type Float)
        result = parse_team_stats(pdf, our_team="HARVARD CRIMSON")
        pct = result.get("oz_possession_pct")
        if pct is not None:
            assert 0.0 <= pct <= 1.0, f"oz_possession_pct={pct} not in [0,1]"

    def test_returns_at_least_one_populated_field(self, pdf):
        # Guard against a parser that silently returns all-None
        result = parse_team_stats(pdf, our_team="HARVARD CRIMSON")
        populated = [k for k, v in result.items() if v is not None]
        assert len(populated) >= 3, (
            f"Only {len(populated)} fields populated: {populated}"
        )
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_team_stats.py -v`
Expected: `ModuleNotFoundError: No module named 'app.ingest.parsers'`.

- [ ] **Step 3: Explore the fixture and write the parser**

Run the discovery snippet above in a Python REPL. Identify:
1. Which table indexes contain the stat rows.
2. Which columns hold "HC" (our team) values.
3. How row labels identify each stat.
4. Any cells with multiple values crammed together (split on whitespace).

Create `backend/app/ingest/parsers/team_stats.py`:
```python
"""Parser for InStat's TEAMS STATS 2 page (P2).

Layout: columns alternate visiting-team, our-team ("PT HC PT HC ..."). Row
labels identify each stat. This parser reads the header row to locate our
team's columns, then walks stat rows and picks the matching column values.

Returns a dict of TeamGameStatsInStat-compatible field values (int/float/None).
"""
from typing import Optional
import re
import pdfplumber
from ..pdf_nav import find_section_page, TEAMS_STATS_SECTION


def parse_team_stats(pdf: pdfplumber.PDF, our_team: str) -> dict:
    page_idx = find_section_page(pdf, TEAMS_STATS_SECTION, our_team)
    result = {
        "pp_shots": None,
        "pp_time_seconds_in_oz": None,
        "pp_time_seconds_total": None,
        "pk_opp_breakouts": None,
        "pp_opp_breakouts_allowed": None,
        "puck_possession_seconds_total": None,
        "oz_possession_seconds": None,
        "oz_possession_pct": None,
        "scoring_chance_shots": None,
        "scoring_chance_shots_on_goal": None,
    }
    if page_idx is None:
        return result

    page = pdf.pages[page_idx]
    # Implementer: use extract_text() / extract_tables() to walk the page
    # and populate result. Use _parse_time_to_seconds and _parse_pct
    # helpers below for time and percentage cells.
    # See discovery snippet in the plan brief for the exact table shape.
    text = page.extract_text() or ""
    tables = page.extract_tables() or []
    _populate_from_page(result, text, tables, our_team)
    return result


def _populate_from_page(
    result: dict, text: str, tables: list, our_team: str
) -> None:
    """Walk the page's tables and text, filling result dict fields.

    Implementer: this is where the P2-specific extraction logic lives.
    Use the fixture-driven test to iterate: run tests, inspect failures,
    tweak the extraction logic. The tests above only require:
    - all expected keys present
    - values are numeric or None
    - oz_possession_pct is normalized to [0,1]
    - at least 3 fields populated (guard against silent failure)
    """
    # Team abbrev: last-letter uppercase pair from team name
    # e.g. "HARVARD CRIMSON" → "HC"
    _team_abbrev(our_team)  # exposed helper below; keep for later parsers

    # ... implementer fills in extraction here ...
    pass


def _team_abbrev(team_name: str) -> str:
    """Extract 2-letter abbreviation from a team name.

    "HARVARD CRIMSON" → "HC"
    "PRINCETON TIGERS" → "PT"
    """
    parts = [p for p in team_name.strip().split() if p]
    if len(parts) >= 2:
        return parts[0][0] + parts[1][0]
    return team_name[:2].upper()


def _parse_time_to_seconds(s: str) -> Optional[int]:
    """Parse InStat time strings like '05:23' or '1:23:45' to seconds."""
    if not s or s.strip() == "—":
        return None
    m = re.match(r"^(?:(\d+):)?(\d+):(\d+)$", s.strip())
    if not m:
        return None
    h = int(m.group(1) or 0)
    mm, ss = int(m.group(2)), int(m.group(3))
    return h * 3600 + mm * 60 + ss


def _parse_pct(s: str) -> Optional[float]:
    """Parse '50%' or '0.50' to 0.5."""
    if not s or s.strip() == "—":
        return None
    s = s.strip().rstrip("%")
    try:
        val = float(s)
    except ValueError:
        return None
    return val / 100.0 if val > 1.0 else val


def _parse_int(s: str) -> Optional[int]:
    if not s or s.strip() == "—":
        return None
    try:
        return int(s.strip())
    except ValueError:
        return None
```

Note: `_populate_from_page` is left as a discovery-guided implementation. The tests dictate acceptance: parse output must have all expected keys, values must be numeric-or-None, at least 3 populated, oz_possession_pct normalized. The implementer inspects the fixture and fills the extraction logic until tests pass.

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_team_stats.py -v`
Expected: 4 tests pass. If any fail with "0 fields populated," return to Step 3 and expand `_populate_from_page`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/parsers/__init__.py backend/app/ingest/parsers/team_stats.py backend/tests/test_parse_team_stats.py
git commit -m "feat: add InStat team-stats PDF parser (P2)"
```

---

### Task 5: Parser — `instat_players_main` (P3/11)

**Files:**
- Create: `backend/app/ingest/parsers/players_main.py`
- Create: `backend/tests/test_parse_players_main.py`

**Interfaces:**
- Consumes: `find_section_page` from `app.ingest.pdf_nav`, `PLAYERS_STATS_SECTION`.
- Produces:
  - `parse_players_main(pdf: pdfplumber.PDF, our_team: str) -> list[dict]` — returns one dict per player row, each with keys `jersey_number: str`, `player_name: str`, plus optional PlayerGameStatsInStat main fields: `shots`, `shots_on_goal`, `blocked_shots`, `pp_shots`, `pp_shots_on_goal`, `corsi_plus`, `corsi_minus`, `hits_delivered`, `hits_received`, `puck_losses`, `puck_losses_dz`, `puck_recoveries`, `puck_recoveries_oz`, `entries_pass`, `entries_stick`, `entries_dump`. Missing fields are None.

**Discovery guidance:** P11 has 16 rows (Harvard roster). Cells contain multiple values crammed together — e.g. one cell holds `TOI shifts PPTOI SHTOI`. See the earlier example row: `['20:56 18 00:12 03:37', '5/3 60% —', '14 18 -4', '— 1', '— — —']`. Column headers are on rows above the data. Explore with the same pdfplumber REPL pattern from Task 4.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_parse_players_main.py`:
```python
import os
import pytest
import pdfplumber
from app.ingest.parsers.players_main import parse_players_main

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParsePlayersMain:
    def test_returns_list_of_dicts(self, pdf):
        rows = parse_players_main(pdf, our_team="HARVARD CRIMSON")
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_reasonable_row_count(self, pdf):
        # Harvard fixture has ~16 skaters + 1 goalie; parser should return
        # a substantial number, not 0 or a handful
        rows = parse_players_main(pdf, our_team="HARVARD CRIMSON")
        assert 10 <= len(rows) <= 25, f"got {len(rows)} rows"

    def test_each_row_has_jersey_and_name(self, pdf):
        rows = parse_players_main(pdf, our_team="HARVARD CRIMSON")
        for r in rows:
            assert "jersey_number" in r and r["jersey_number"]
            assert "player_name" in r and r["player_name"]

    def test_jersey_numbers_are_strings(self, pdf):
        # Match Player.number column type (String)
        rows = parse_players_main(pdf, our_team="HARVARD CRIMSON")
        for r in rows:
            assert isinstance(r["jersey_number"], str)

    def test_numeric_fields_are_int_or_none(self, pdf):
        rows = parse_players_main(pdf, our_team="HARVARD CRIMSON")
        numeric_keys = {
            "shots", "shots_on_goal", "blocked_shots",
            "pp_shots", "pp_shots_on_goal",
            "corsi_plus", "corsi_minus",
            "hits_delivered", "hits_received",
            "puck_losses", "puck_losses_dz",
            "puck_recoveries", "puck_recoveries_oz",
            "entries_pass", "entries_stick", "entries_dump",
        }
        for r in rows:
            for k in numeric_keys & r.keys():
                assert r[k] is None or isinstance(r[k], int), (
                    f"player {r['player_name']!r} field {k}={r[k]!r} not int/None"
                )

    def test_returns_empty_for_unknown_team(self, pdf):
        rows = parse_players_main(pdf, our_team="NONEXISTENT TEAM")
        assert rows == []
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_players_main.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement the parser**

Follow the same discovery-guided pattern as Task 4:
1. REPL inspect page 11's tables to understand column layout.
2. Write parser that walks table rows, splits multi-value cells on whitespace, maps positional values to field names.
3. Iterate against tests.

Create `backend/app/ingest/parsers/players_main.py`:
```python
"""Parser for InStat's PLAYERS' STATS page (P3 for visitor, P11 for home).

Layout: 16-row table (one per player) with multi-valued cells. Each row
carries the player's jersey and name plus performance stats. Cells often
concatenate several fields (e.g. one cell contains "TOI shifts PPTOI SHTOI").

Returns a list of dicts, one per player, each with a jersey/name and any
PlayerGameStatsInStat main fields the parser could extract.
"""
from typing import Optional
import re
import pdfplumber
from ..pdf_nav import find_section_page, PLAYERS_STATS_SECTION
from .team_stats import _parse_int  # reuse int-with-em-dash helper


def parse_players_main(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    page_idx = find_section_page(pdf, PLAYERS_STATS_SECTION, our_team)
    if page_idx is None:
        return []
    page = pdf.pages[page_idx]
    tables = page.extract_tables() or []
    text = page.extract_text() or ""
    return _extract_player_rows(tables, text)


def _extract_player_rows(tables: list, text: str) -> list[dict]:
    """Walk table rows and produce one dict per player.

    Implementer: this is where the P3/11-specific extraction lives. See
    the plan brief's discovery guidance. Tests dictate acceptance:
    - returns 10-25 dicts
    - each dict has jersey_number (str) and player_name (str)
    - numeric fields (shots, corsi_plus, etc.) are int or None
    """
    # ... implementer fills in extraction here ...
    return []
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_players_main.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/parsers/players_main.py backend/tests/test_parse_players_main.py
git commit -m "feat: add InStat players-main PDF parser (P3/11)"
```

---

### Task 6: Parser — `instat_time_distribution` (P5/13)

**Files:**
- Create: `backend/app/ingest/parsers/time_distribution.py`
- Create: `backend/tests/test_parse_time_distribution.py`

**Interfaces:**
- Consumes: `find_section_page`, `GAME_TIME_SECTION`.
- Produces:
  - `parse_time_distribution(pdf, our_team) -> list[dict]` — one dict per player: `{jersey_number: str, player_name: str, toi_5v5_seconds: int|None, toi_pp_seconds: int|None, toi_sh_seconds: int|None}`.

**Discovery guidance:** Page 5/13 header line 2 in the fixture is `"PP SH PP PP SH SH PP SH"` (or similar) — mixed columns for PP/SH times per player. Look for a "FIRST LINE" label seen in the fixture. Explore with REPL first.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_parse_time_distribution.py`:
```python
import os
import pytest
import pdfplumber
from app.ingest.parsers.time_distribution import parse_time_distribution

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseTimeDistribution:
    def test_returns_list(self, pdf):
        rows = parse_time_distribution(pdf, "HARVARD CRIMSON")
        assert isinstance(rows, list)

    def test_reasonable_row_count(self, pdf):
        rows = parse_time_distribution(pdf, "HARVARD CRIMSON")
        assert 10 <= len(rows) <= 25

    def test_each_row_has_expected_keys(self, pdf):
        rows = parse_time_distribution(pdf, "HARVARD CRIMSON")
        for r in rows:
            for k in ("jersey_number", "player_name",
                      "toi_5v5_seconds", "toi_pp_seconds", "toi_sh_seconds"):
                assert k in r

    def test_seconds_are_int_or_none(self, pdf):
        rows = parse_time_distribution(pdf, "HARVARD CRIMSON")
        for r in rows:
            for k in ("toi_5v5_seconds", "toi_pp_seconds", "toi_sh_seconds"):
                assert r[k] is None or isinstance(r[k], int)

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_time_distribution(pdf, "NOPE") == []
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_time_distribution.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement the parser**

Create `backend/app/ingest/parsers/time_distribution.py`:
```python
"""Parser for InStat's GAME TIME DISTRIBUTION page (P5/13).

Layout: per-player row with PP/SH/EV time splits. Returns one dict per
player with TOI in seconds for each strength state.
"""
import pdfplumber
from ..pdf_nav import find_section_page, GAME_TIME_SECTION
from .team_stats import _parse_time_to_seconds


def parse_time_distribution(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    page_idx = find_section_page(pdf, GAME_TIME_SECTION, our_team)
    if page_idx is None:
        return []
    page = pdf.pages[page_idx]
    tables = page.extract_tables() or []
    return _extract_time_rows(tables)


def _extract_time_rows(tables: list) -> list[dict]:
    """Extract per-player TOI splits from GAME TIME DISTRIBUTION tables.

    Implementer: REPL-inspect the fixture's P13 tables to determine which
    columns hold 5v5, PP, and SH times. Convert with _parse_time_to_seconds.
    Tests require: 10-25 rows, each with jersey/name/toi_5v5_seconds/
    toi_pp_seconds/toi_sh_seconds (int or None).
    """
    # ... implementer fills in ...
    return []
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_time_distribution.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/parsers/time_distribution.py backend/tests/test_parse_time_distribution.py
git commit -m "feat: add InStat time-distribution PDF parser (P5/13)"
```

---

### Task 7: Parser — `instat_challenges` (P7/15)

**Files:**
- Create: `backend/app/ingest/parsers/challenges.py`
- Create: `backend/tests/test_parse_challenges.py`

**Interfaces:**
- Consumes: `find_section_page`, `CHALLENGES_SECTION`.
- Produces:
  - `parse_challenges(pdf, our_team) -> list[dict]` — one dict per player: `{jersey_number, player_name, pb_won_dz, pb_total_dz, pb_won_oz, pb_total_oz, pb_won_nz, pb_total_nz}`. Counts are int-or-None.

**Discovery guidance:** P7/15 shows puck-battle results by zone. Cells often hold "won—total" or "won/total" pairs; split accordingly. REPL-inspect first.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_parse_challenges.py`:
```python
import os
import pytest
import pdfplumber
from app.ingest.parsers.challenges import parse_challenges

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseChallenges:
    def test_returns_list(self, pdf):
        rows = parse_challenges(pdf, "HARVARD CRIMSON")
        assert isinstance(rows, list)

    def test_reasonable_row_count(self, pdf):
        rows = parse_challenges(pdf, "HARVARD CRIMSON")
        assert 10 <= len(rows) <= 25

    def test_each_row_has_expected_keys(self, pdf):
        rows = parse_challenges(pdf, "HARVARD CRIMSON")
        for r in rows:
            for k in ("jersey_number", "player_name",
                      "pb_won_dz", "pb_total_dz",
                      "pb_won_oz", "pb_total_oz",
                      "pb_won_nz", "pb_total_nz"):
                assert k in r

    def test_won_never_exceeds_total(self, pdf):
        rows = parse_challenges(pdf, "HARVARD CRIMSON")
        for r in rows:
            for won, tot in [("pb_won_dz", "pb_total_dz"),
                             ("pb_won_oz", "pb_total_oz"),
                             ("pb_won_nz", "pb_total_nz")]:
                w, t = r[won], r[tot]
                if w is not None and t is not None:
                    assert w <= t, f"{r['player_name']}: {won}={w} > {tot}={t}"

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_challenges(pdf, "NOPE") == []
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_challenges.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement the parser**

Create `backend/app/ingest/parsers/challenges.py`:
```python
"""Parser for InStat's CHALLENGES page (P7/15).

Layout: per-player puck-battle counts by zone (DZ / OZ / NZ). Cells report
'won—total' or 'won/total'. Returns list of dicts with the pb_* fields
matching PlayerGameStatsInStat.
"""
import re
import pdfplumber
from ..pdf_nav import find_section_page, CHALLENGES_SECTION


def parse_challenges(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    page_idx = find_section_page(pdf, CHALLENGES_SECTION, our_team)
    if page_idx is None:
        return []
    page = pdf.pages[page_idx]
    tables = page.extract_tables() or []
    return _extract_challenge_rows(tables)


def _parse_won_total(cell: str) -> tuple[int | None, int | None]:
    """Parse 'won—total' or 'won/total' or '—' cells.

    Returns (won, total). Either or both may be None.
    """
    if not cell or cell.strip() == "—":
        return None, None
    m = re.match(r"^\s*(\d+)\s*[—/-]\s*(\d+)\s*$", cell.strip())
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _extract_challenge_rows(tables: list) -> list[dict]:
    """Implementer: extract per-player DZ/OZ/NZ challenge counts.

    Tests require: 10-25 rows, each with the 8 expected keys, won ≤ total
    invariant per zone. Use _parse_won_total on each zone cell.
    """
    # ... implementer fills in ...
    return []
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_challenges.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/parsers/challenges.py backend/tests/test_parse_challenges.py
git commit -m "feat: add InStat challenges PDF parser (P7/15)"
```

---

### Task 8: Parser — `instat_hit_matrix` (P9/17)

**Files:**
- Create: `backend/app/ingest/parsers/hit_matrix.py`
- Create: `backend/tests/test_parse_hit_matrix.py`

**Interfaces:**
- Consumes: `find_section_page`, `HITS_DISTRIBUTION_SECTION`, `_parse_won_total` from `challenges.py`.
- Produces:
  - `parse_hit_matrix(pdf, our_team) -> list[dict]` — one dict per non-empty from→to pair: `{from_jersey: str, from_name: str, to_jersey: str, to_name: str, delivered: int, received: int}`. Matrix cells are "delivered—received"; rows where every column is `"—"` are omitted.

**Discovery guidance:** From the earlier inspection, the matrix has:
- Header row 1: jersey numbers as columns (`15 8 2 12 4 17 20 22 10 9 7 11 18 28 3 23 21 27 TOTAL`).
- Header row 2: last names as columns.
- Data rows: last-name, jersey, N cells of "won—total" values, TOTAL.
- "—" indicates no interaction.

Return one row per non-empty from/to pair, not the raw matrix.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_parse_hit_matrix.py`:
```python
import os
import pytest
import pdfplumber
from app.ingest.parsers.hit_matrix import parse_hit_matrix

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParseHitMatrix:
    def test_returns_list(self, pdf):
        rows = parse_hit_matrix(pdf, "HARVARD CRIMSON")
        assert isinstance(rows, list)

    def test_all_rows_are_non_empty_pairs(self, pdf):
        # Parser omits pairs where both delivered and received are 0 (from '—')
        rows = parse_hit_matrix(pdf, "HARVARD CRIMSON")
        for r in rows:
            assert r["delivered"] > 0 or r["received"] > 0, (
                f"row {r} has no interaction; should be omitted"
            )

    def test_each_row_has_pair_and_counts(self, pdf):
        rows = parse_hit_matrix(pdf, "HARVARD CRIMSON")
        for r in rows:
            for k in ("from_jersey", "from_name", "to_jersey", "to_name",
                      "delivered", "received"):
                assert k in r
            assert isinstance(r["delivered"], int)
            assert isinstance(r["received"], int)

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_hit_matrix(pdf, "NOPE") == []
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_hit_matrix.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement the parser**

Create `backend/app/ingest/parsers/hit_matrix.py`:
```python
"""Parser for InStat's HITS DISTRIBUTION page (P9/17).

Layout: NxN matrix with players as both rows and columns. Each cell is
'delivered—received' (from row's perspective vs. column player), or '—'
for no interaction. Returns one dict per non-empty from/to pair.
"""
import pdfplumber
from ..pdf_nav import find_section_page, HITS_DISTRIBUTION_SECTION
from .challenges import _parse_won_total  # 'a—b' → (a, b) parser


def parse_hit_matrix(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    page_idx = find_section_page(pdf, HITS_DISTRIBUTION_SECTION, our_team)
    if page_idx is None:
        return []
    page = pdf.pages[page_idx]
    text = page.extract_text() or ""
    return _extract_hit_pairs(text)


def _extract_hit_pairs(text: str) -> list[dict]:
    """Walk the text-extracted matrix and yield one dict per non-empty cell.

    Implementer: the matrix in extract_text() output has:
      - line with jersey numbers (columns)
      - line with last names (columns)
      - repeating: last-name line, jersey line, cell values line
    Use _parse_won_total to parse each 'a—b' cell. Skip cells that
    parse to (None, None) or (0, 0).
    """
    # ... implementer fills in ...
    return []
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_hit_matrix.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/parsers/hit_matrix.py backend/tests/test_parse_hit_matrix.py
git commit -m "feat: add InStat hit-matrix PDF parser (P9/17)"
```

---

### Task 9: Parser — `instat_pass_matrix` (P10/18)

**Files:**
- Create: `backend/app/ingest/parsers/pass_matrix.py`
- Create: `backend/tests/test_parse_pass_matrix.py`

**Interfaces:**
- Consumes: `find_section_page`, `PASSES_DISTRIBUTION_SECTION`.
- Produces:
  - `parse_pass_matrix(pdf, our_team) -> list[dict]` — one dict per non-zero from→to pair: `{from_jersey: str, from_name: str, to_jersey: str, to_name: str, count: int}`. Cells are plain integer counts (unlike hits, no "delivered—received" split). Zero-count pairs omitted.

**Discovery guidance:** Same matrix shape as hits page but cells are single integers, not `a—b` pairs. `"—"` denotes zero.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_parse_pass_matrix.py`:
```python
import os
import pytest
import pdfplumber
from app.ingest.parsers.pass_matrix import parse_pass_matrix

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def pdf():
    with pdfplumber.open(FIXTURE) as p:
        yield p


class TestParsePassMatrix:
    def test_returns_list(self, pdf):
        rows = parse_pass_matrix(pdf, "HARVARD CRIMSON")
        assert isinstance(rows, list)

    def test_all_rows_have_positive_count(self, pdf):
        rows = parse_pass_matrix(pdf, "HARVARD CRIMSON")
        for r in rows:
            assert r["count"] > 0

    def test_each_row_has_pair_and_count(self, pdf):
        rows = parse_pass_matrix(pdf, "HARVARD CRIMSON")
        for r in rows:
            for k in ("from_jersey", "from_name", "to_jersey", "to_name", "count"):
                assert k in r
            assert isinstance(r["count"], int)

    def test_reasonable_pair_count(self, pdf):
        # Fixture's Harvard passes matrix has 139 total passes across many pairs
        rows = parse_pass_matrix(pdf, "HARVARD CRIMSON")
        assert 20 <= len(rows) <= 200

    def test_returns_empty_for_unknown_team(self, pdf):
        assert parse_pass_matrix(pdf, "NOPE") == []
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_pass_matrix.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement the parser**

Create `backend/app/ingest/parsers/pass_matrix.py`:
```python
"""Parser for InStat's PASSES DISTRIBUTION page (P10/18).

Layout: NxN matrix of pass counts. Each cell is a plain integer; '—' = 0.
Returns one dict per non-zero from→to pair.
"""
import pdfplumber
from ..pdf_nav import find_section_page, PASSES_DISTRIBUTION_SECTION


def parse_pass_matrix(pdf: pdfplumber.PDF, our_team: str) -> list[dict]:
    page_idx = find_section_page(pdf, PASSES_DISTRIBUTION_SECTION, our_team)
    if page_idx is None:
        return []
    page = pdf.pages[page_idx]
    text = page.extract_text() or ""
    return _extract_pass_pairs(text)


def _extract_pass_pairs(text: str) -> list[dict]:
    """Walk the text-extracted matrix and yield one dict per non-zero cell.

    Implementer: shape mirrors hit_matrix (jersey-name header rows,
    repeating name/jersey/cells rows), but cells are single integers.
    Treat '—' as 0 and omit; treat digits as int and emit.
    """
    # ... implementer fills in ...
    return []
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_parse_pass_matrix.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/parsers/pass_matrix.py backend/tests/test_parse_pass_matrix.py
git commit -m "feat: add InStat pass-matrix PDF parser (P10/18)"
```

---

### Task 10: Validators + template registry + orchestrator

**Files:**
- Create: `backend/app/ingest/validators.py`
- Create: `backend/app/ingest/templates.py`
- Create: `backend/app/ingest/orchestrator.py`
- Create: `backend/tests/test_validators.py`
- Create: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: all six parsers from `app.ingest.parsers.*`, `OUR_TEAM_NAME`, `Player` model.
- Produces:
  - `validate_jersey(jersey: str, roster: dict[str, Player]) -> tuple[Player | None, list[str]]` — returns (matched player or None, list of warning strings).
  - `TEMPLATES: dict[str, callable]` — maps template name to parser fn. Keys: `"instat_team_stats"`, `"instat_players_main"`, `"instat_time_distribution"`, `"instat_challenges"`, `"instat_hit_matrix"`, `"instat_pass_matrix"`.
  - `parse_all(pdf_path: str, our_team: str) -> dict` — runs all six parsers, returns `{"templates": {name: parsed_data, ...}, "warnings": [...]}`.
  - `validate_parsed(parsed: dict, db_session) -> dict` — annotates parsed dict with jersey-vs-roster warnings; returns same-shape dict with `_warnings` keys added at row/template level.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_validators.py`:
```python
import pytest
from app.models import Player
from app.ingest.validators import validate_jersey


class TestValidateJersey:
    def test_matches_existing_player(self, db_session, seed_roster):
        # seed_roster fixture (from conftest.py) creates 6 players with numbers 10,7,9,2,4,30
        roster = {p.number: p for p in db_session.query(Player).all()}
        player, warnings = validate_jersey("10", roster)
        assert player is not None
        assert player.number == "10"
        assert warnings == []

    def test_returns_none_and_warning_for_unknown_jersey(self, db_session, seed_roster):
        roster = {p.number: p for p in db_session.query(Player).all()}
        player, warnings = validate_jersey("99", roster)
        assert player is None
        assert len(warnings) == 1
        assert "99" in warnings[0]
```

Create `backend/tests/test_orchestrator.py`:
```python
import os
from app.ingest.orchestrator import parse_all, TEMPLATES

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


class TestTemplates:
    def test_has_all_six_templates(self):
        expected = {
            "instat_team_stats", "instat_players_main", "instat_time_distribution",
            "instat_challenges", "instat_hit_matrix", "instat_pass_matrix",
        }
        assert set(TEMPLATES.keys()) == expected


class TestParseAll:
    def test_returns_dict_with_all_templates(self):
        result = parse_all(FIXTURE, "HARVARD CRIMSON")
        assert "templates" in result
        assert set(result["templates"].keys()) == {
            "instat_team_stats", "instat_players_main", "instat_time_distribution",
            "instat_challenges", "instat_hit_matrix", "instat_pass_matrix",
        }

    def test_returns_warnings_list(self):
        result = parse_all(FIXTURE, "HARVARD CRIMSON")
        assert "warnings" in result
        assert isinstance(result["warnings"], list)

    def test_team_stats_is_dict(self):
        result = parse_all(FIXTURE, "HARVARD CRIMSON")
        assert isinstance(result["templates"]["instat_team_stats"], dict)

    def test_players_main_is_list(self):
        result = parse_all(FIXTURE, "HARVARD CRIMSON")
        assert isinstance(result["templates"]["instat_players_main"], list)

    def test_unknown_team_returns_warning(self):
        result = parse_all(FIXTURE, "NONEXISTENT TEAM")
        # All parsers return empty; warnings note the team wasn't found
        assert len(result["warnings"]) >= 1
        assert "team" in result["warnings"][0].lower() or "NONEXISTENT" in " ".join(result["warnings"])
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_validators.py backend/tests/test_orchestrator.py -v`
Expected: ImportError for validators + orchestrator modules.

- [ ] **Step 3: Implement validators**

Create `backend/app/ingest/validators.py`:
```python
"""Field-level validation for parsed InStat data.

Each validator returns a value (possibly None if invalid) and a list of
warning strings. Warnings are surfaced in the review UI but do not block
commit — the coach can accept them or fix them inline.
"""
from typing import Optional
from ..models import Player


def validate_jersey(
    jersey: str, roster: dict[str, Player]
) -> tuple[Optional[Player], list[str]]:
    """Look up a player by jersey number against the current roster.

    roster: {jersey_number_str: Player}
    Returns (Player or None, warnings).
    """
    player = roster.get(str(jersey).strip())
    if player is None:
        return None, [f"Jersey {jersey!r} not found in roster"]
    return player, []
```

- [ ] **Step 4: Implement template registry + orchestrator**

Create `backend/app/ingest/templates.py`:
```python
"""Central registry mapping template name → parser function.

Adding a new template: import the parser, add the entry, and add the target
table's commit logic to app.ingest.commit.
"""
from .parsers.team_stats import parse_team_stats
from .parsers.players_main import parse_players_main
from .parsers.time_distribution import parse_time_distribution
from .parsers.challenges import parse_challenges
from .parsers.hit_matrix import parse_hit_matrix
from .parsers.pass_matrix import parse_pass_matrix


TEMPLATES = {
    "instat_team_stats": parse_team_stats,
    "instat_players_main": parse_players_main,
    "instat_time_distribution": parse_time_distribution,
    "instat_challenges": parse_challenges,
    "instat_hit_matrix": parse_hit_matrix,
    "instat_pass_matrix": parse_pass_matrix,
}
```

Create `backend/app/ingest/orchestrator.py`:
```python
"""Run every InStat template against a single PDF.

Returns {"templates": {name: parsed_data}, "warnings": [str, ...]}.
Warnings are non-fatal notes for the review UI (e.g. team not found,
sections missing).
"""
import pdfplumber
from .templates import TEMPLATES
from .pdf_nav import (
    find_section_page,
    TEAMS_STATS_SECTION, PLAYERS_STATS_SECTION,
    GAME_TIME_SECTION, CHALLENGES_SECTION,
    HITS_DISTRIBUTION_SECTION, PASSES_DISTRIBUTION_SECTION,
)


def parse_all(pdf_path: str, our_team: str) -> dict:
    """Run all six template parsers on one PDF.

    pdf_path: filesystem path to an InStat match-report PDF.
    our_team: team name to extract data for (e.g. "HARVARD CRIMSON").
    Returns {"templates": {name: parsed_data}, "warnings": [...]}.
    """
    templates_out = {}
    warnings = []
    with pdfplumber.open(pdf_path) as pdf:
        # Sanity check: our team's players' stats section must exist
        players_page = find_section_page(pdf, PLAYERS_STATS_SECTION, our_team)
        if players_page is None:
            warnings.append(
                f"Team {our_team!r} not found in PDF; parsers returned empty data."
            )
        for name, parser in TEMPLATES.items():
            templates_out[name] = parser(pdf, our_team)
    return {"templates": templates_out, "warnings": warnings}
```

- [ ] **Step 5: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_validators.py backend/tests/test_orchestrator.py -v`
Expected: 7 tests pass (2 validator + 5 orchestrator).

- [ ] **Step 6: Commit**

```bash
git add backend/app/ingest/validators.py backend/app/ingest/templates.py backend/app/ingest/orchestrator.py backend/tests/test_validators.py backend/tests/test_orchestrator.py
git commit -m "feat: add validators, template registry, and orchestrator for InStat ingest"
```

---

### Task 11: Commit layer

**Files:**
- Create: `backend/app/ingest/commit.py`
- Create: `backend/tests/test_ingest_commit.py`

**Interfaces:**
- Consumes: `parse_all` output shape, all target models (`TeamGameStatsInStat`, `PlayerGameStatsInStat`, `PlayerGameStats`, `PlayerHitMatrix`, `PlayerPassMatrix`), `validate_jersey`.
- Produces:
  - `commit_parsed(parsed: dict, game_id: int, db_session) -> dict` — writes all templates' data to DB in a single transaction. Returns `{"wrote": {template_name: row_count}, "skipped": [warning_strings]}`. Upserts by `(game_id, player_id)` where applicable.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_ingest_commit.py`:
```python
import pytest
from datetime import date
from app.models import (
    Player, Game, TeamGameStatsInStat, PlayerGameStatsInStat,
    PlayerHitMatrix, PlayerPassMatrix,
)
from app.ingest.commit import commit_parsed


@pytest.fixture
def game_and_players(db_session):
    g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True,
             season="2025-26", data_source="instat")
    p10 = Player(name="Ten", number="10", position="F", is_center=True, active=True)
    p7  = Player(name="Seven", number="7", position="F", is_center=False, active=True)
    db_session.add_all([g, p10, p7])
    db_session.commit()
    return g, p10, p7


class TestCommitParsed:
    def test_writes_team_stats(self, db_session, game_and_players):
        g, _, _ = game_and_players
        parsed = {
            "templates": {
                "instat_team_stats": {
                    "pp_shots": 12, "pp_time_seconds_total": 429,
                    "oz_possession_pct": 0.50,
                    # rest None
                    "pp_time_seconds_in_oz": None, "pk_opp_breakouts": None,
                    "pp_opp_breakouts_allowed": None,
                    "puck_possession_seconds_total": None,
                    "oz_possession_seconds": None,
                    "scoring_chance_shots": None, "scoring_chance_shots_on_goal": None,
                },
                "instat_players_main": [], "instat_time_distribution": [],
                "instat_challenges": [], "instat_hit_matrix": [], "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        report = commit_parsed(parsed, g.id, db_session)
        assert report["wrote"]["instat_team_stats"] == 1
        row = db_session.query(TeamGameStatsInStat).filter_by(game_id=g.id).one()
        assert row.pp_shots == 12
        assert row.oz_possession_pct == 0.50

    def test_writes_players_main(self, db_session, game_and_players):
        g, p10, p7 = game_and_players
        parsed = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [
                    {"jersey_number": "10", "player_name": "Ten",
                     "shots": 5, "corsi_plus": 12, "hits_delivered": 2},
                    {"jersey_number": "7", "player_name": "Seven",
                     "shots": 3, "corsi_plus": 8},
                ],
                "instat_time_distribution": [], "instat_challenges": [],
                "instat_hit_matrix": [], "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        report = commit_parsed(parsed, g.id, db_session)
        assert report["wrote"]["instat_players_main"] == 2
        rows = db_session.query(PlayerGameStatsInStat).filter_by(game_id=g.id).all()
        assert len(rows) == 2

    def test_writes_hit_matrix(self, db_session, game_and_players):
        g, p10, p7 = game_and_players
        parsed = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [], "instat_time_distribution": [],
                "instat_challenges": [],
                "instat_hit_matrix": [
                    {"from_jersey": "10", "from_name": "Ten",
                     "to_jersey": "7", "to_name": "Seven",
                     "delivered": 3, "received": 1},
                ],
                "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        report = commit_parsed(parsed, g.id, db_session)
        assert report["wrote"]["instat_hit_matrix"] == 1
        row = db_session.query(PlayerHitMatrix).filter_by(game_id=g.id).one()
        assert row.from_player_id == p10.id
        assert row.to_player_id == p7.id
        assert row.delivered == 3

    def test_skips_unknown_jersey(self, db_session, game_and_players):
        g, _, _ = game_and_players
        parsed = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [
                    {"jersey_number": "99", "player_name": "Ghost", "shots": 1},
                ],
                "instat_time_distribution": [], "instat_challenges": [],
                "instat_hit_matrix": [], "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        report = commit_parsed(parsed, g.id, db_session)
        assert report["wrote"]["instat_players_main"] == 0
        assert any("99" in s for s in report["skipped"])

    def test_upserts_on_reingest(self, db_session, game_and_players):
        g, p10, _ = game_and_players
        parsed_v1 = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [
                    {"jersey_number": "10", "player_name": "Ten", "shots": 5},
                ],
                "instat_time_distribution": [], "instat_challenges": [],
                "instat_hit_matrix": [], "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        commit_parsed(parsed_v1, g.id, db_session)
        # Re-ingest with different value
        parsed_v2 = {
            "templates": {
                "instat_team_stats": _empty_team(),
                "instat_players_main": [
                    {"jersey_number": "10", "player_name": "Ten", "shots": 9},
                ],
                "instat_time_distribution": [], "instat_challenges": [],
                "instat_hit_matrix": [], "instat_pass_matrix": [],
            },
            "warnings": [],
        }
        commit_parsed(parsed_v2, g.id, db_session)
        rows = db_session.query(PlayerGameStatsInStat).filter_by(game_id=g.id).all()
        assert len(rows) == 1
        assert rows[0].shots == 9


def _empty_team():
    return {
        "pp_shots": None, "pp_time_seconds_in_oz": None,
        "pp_time_seconds_total": None, "pk_opp_breakouts": None,
        "pp_opp_breakouts_allowed": None,
        "puck_possession_seconds_total": None,
        "oz_possession_seconds": None, "oz_possession_pct": None,
        "scoring_chance_shots": None, "scoring_chance_shots_on_goal": None,
    }
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_ingest_commit.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement the commit layer**

Create `backend/app/ingest/commit.py`:
```python
"""Write parsed InStat data to target tables.

One transaction per commit call. Upserts by (game_id, player_id) or
(game_id, from_player_id, to_player_id) for matrix rows — so re-ingest
of the same game replaces prior values.
"""
from ..models import (
    Player, TeamGameStatsInStat, PlayerGameStatsInStat,
    PlayerHitMatrix, PlayerPassMatrix,
)


def commit_parsed(parsed: dict, game_id: int, db_session) -> dict:
    """Write all templates' data to DB atomically.

    Returns {"wrote": {template_name: row_count}, "skipped": [warnings]}.
    Rolls back on any exception.
    """
    templates = parsed["templates"]
    wrote = {name: 0 for name in templates}
    skipped: list[str] = []

    roster = {p.number: p for p in db_session.query(Player).all()}

    try:
        # instat_team_stats: single upsert on game_id
        team = templates.get("instat_team_stats") or {}
        if any(v is not None for v in team.values()):
            existing = db_session.query(TeamGameStatsInStat).filter_by(
                game_id=game_id
            ).one_or_none()
            if existing is None:
                existing = TeamGameStatsInStat(game_id=game_id)
                db_session.add(existing)
            for k, v in team.items():
                setattr(existing, k, v)
            wrote["instat_team_stats"] = 1

        # instat_players_main: upsert per player row
        for row in templates.get("instat_players_main") or []:
            player = roster.get(str(row.get("jersey_number", "")).strip())
            if player is None:
                skipped.append(
                    f"players_main: jersey {row.get('jersey_number')!r} not in roster"
                )
                continue
            existing = db_session.query(PlayerGameStatsInStat).filter_by(
                game_id=game_id, player_id=player.id
            ).one_or_none()
            if existing is None:
                existing = PlayerGameStatsInStat(game_id=game_id, player_id=player.id)
                db_session.add(existing)
            for k in ("shots", "shots_on_goal", "blocked_shots",
                      "pp_shots", "pp_shots_on_goal",
                      "corsi_plus", "corsi_minus",
                      "hits_delivered", "hits_received",
                      "puck_losses", "puck_losses_dz",
                      "puck_recoveries", "puck_recoveries_oz",
                      "entries_pass", "entries_stick", "entries_dump"):
                if k in row:
                    setattr(existing, k, row[k])
            wrote["instat_players_main"] += 1

        # instat_challenges: upsert per player row into pb_* fields
        for row in templates.get("instat_challenges") or []:
            player = roster.get(str(row.get("jersey_number", "")).strip())
            if player is None:
                skipped.append(
                    f"challenges: jersey {row.get('jersey_number')!r} not in roster"
                )
                continue
            existing = db_session.query(PlayerGameStatsInStat).filter_by(
                game_id=game_id, player_id=player.id
            ).one_or_none()
            if existing is None:
                existing = PlayerGameStatsInStat(game_id=game_id, player_id=player.id)
                db_session.add(existing)
            for k in ("pb_won_dz", "pb_total_dz",
                      "pb_won_oz", "pb_total_oz",
                      "pb_won_nz", "pb_total_nz"):
                if k in row:
                    setattr(existing, k, row[k])
            wrote["instat_challenges"] += 1

        # instat_time_distribution: upsert PlayerGameStats toi/pp/sh
        # (Only for InStat-sourced games; if PlayerGameStats already
        # populated by 49ing, this overwrites — fine per data_source == "both"
        # 49ing-precedence rule NOT applying to raw TOI which is identical
        # across sources.)
        from ..models import PlayerGameStats
        for row in templates.get("instat_time_distribution") or []:
            player = roster.get(str(row.get("jersey_number", "")).strip())
            if player is None:
                skipped.append(
                    f"time_distribution: jersey {row.get('jersey_number')!r} not in roster"
                )
                continue
            existing = db_session.query(PlayerGameStats).filter_by(
                game_id=game_id, player_id=player.id
            ).one_or_none()
            if existing is None:
                existing = PlayerGameStats(game_id=game_id, player_id=player.id)
                db_session.add(existing)
            # Convert seconds → minutes for the model's Float TOI fields
            if row.get("toi_5v5_seconds") is not None:
                existing.toi_5v5 = row["toi_5v5_seconds"] / 60.0
            if row.get("toi_pp_seconds") is not None:
                existing.toi_pp = row["toi_pp_seconds"] / 60.0
            if row.get("toi_sh_seconds") is not None:
                existing.toi_sh = row["toi_sh_seconds"] / 60.0
            wrote["instat_time_distribution"] += 1

        # instat_hit_matrix: upsert per from→to pair
        for row in templates.get("instat_hit_matrix") or []:
            f_player = roster.get(str(row.get("from_jersey", "")).strip())
            t_player = roster.get(str(row.get("to_jersey", "")).strip())
            if f_player is None or t_player is None:
                skipped.append(
                    f"hit_matrix: pair {row.get('from_jersey')}→{row.get('to_jersey')} not in roster"
                )
                continue
            existing = db_session.query(PlayerHitMatrix).filter_by(
                game_id=game_id, from_player_id=f_player.id, to_player_id=t_player.id
            ).one_or_none()
            if existing is None:
                existing = PlayerHitMatrix(
                    game_id=game_id, from_player_id=f_player.id, to_player_id=t_player.id
                )
                db_session.add(existing)
            existing.delivered = row.get("delivered", 0)
            existing.received = row.get("received", 0)
            wrote["instat_hit_matrix"] += 1

        # instat_pass_matrix: upsert per from→to pair
        for row in templates.get("instat_pass_matrix") or []:
            f_player = roster.get(str(row.get("from_jersey", "")).strip())
            t_player = roster.get(str(row.get("to_jersey", "")).strip())
            if f_player is None or t_player is None:
                skipped.append(
                    f"pass_matrix: pair {row.get('from_jersey')}→{row.get('to_jersey')} not in roster"
                )
                continue
            existing = db_session.query(PlayerPassMatrix).filter_by(
                game_id=game_id, from_player_id=f_player.id, to_player_id=t_player.id
            ).one_or_none()
            if existing is None:
                existing = PlayerPassMatrix(
                    game_id=game_id, from_player_id=f_player.id, to_player_id=t_player.id
                )
                db_session.add(existing)
            existing.count = row.get("count", 0)
            wrote["instat_pass_matrix"] += 1

        db_session.commit()
    except Exception:
        db_session.rollback()
        raise

    return {"wrote": wrote, "skipped": skipped}
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_ingest_commit.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/commit.py backend/tests/test_ingest_commit.py
git commit -m "feat: add ingest commit layer with upsert-by-game semantics"
```

---

### Task 12: Ingest router endpoints

**Files:**
- Modify: `backend/app/main.py` (register new router)
- Create: `backend/app/routers/ingest.py`
- Create: `backend/tests/test_ingest_router.py`
- Modify: `backend/.gitignore` — add `uploads/` if not already ignored

**Interfaces:**
- Consumes: `parse_all`, `commit_parsed`, `OUR_TEAM_NAME`, `IngestRun` model.
- Produces:
  - `POST /api/ingest/upload` — multipart form with `file: UploadFile` and `game_id: int`. Saves PDF to `backend/uploads/ingest/{ingest_run_id}.pdf`, parses it, creates `IngestRun` with `parsed_json`, returns `{"ingest_run_id": int, "warnings": [...], "preview": {...}}`.
  - `GET /api/ingest/{id}` — returns `{"id", "game_id", "status", "parsed_json": {...}, "warnings", "committed_at"}`.
  - `POST /api/ingest/{id}/commit` — takes optional `parsed_json` body (edited version from review UI); commits to DB, sets `status="committed"`. Returns commit report.
  - `DELETE /api/ingest/{id}` — soft-deletes (sets `status="discarded"`).

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_ingest_router.py`:
```python
import os
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_db
from app.models import Player, Game, IngestRun


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def test_db(tmp_path):
    """Isolated SQLite file per test — bypasses the app's real DB."""
    db_url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    # Seed Harvard roster with jerseys matching the fixture PDF
    for name, num in [
        ("Finnegan", "8"), ("Paulsen", "7"), ("Ley", "16"), ("Biotti", "5"),
        ("Sun", "20"), ("Kasica", "21"), ("MacDonald", "3"), ("Lapp", "9"),
        ("Megdanis", "10"), ("McGathey", "4"), ("Sproule", "17"),
        ("McSweeney", "14"), ("Lucia", "28"), ("Dinges", "24"),
        ("Boosamra", "12"), ("Hamann", "11"),
    ]:
        session.add(Player(name=name, number=num, position="F",
                           is_center=False, active=True))
    session.add(Game(date=date(2026, 3, 2), opponent="Princeton",
                     is_home=False, season="2025-26", data_source="instat"))
    session.commit()
    yield session, Session
    session.close()


@pytest.fixture
def client(test_db, monkeypatch, tmp_path):
    """TestClient wired to the isolated test DB via dependency_overrides."""
    _, Session = test_db
    monkeypatch.setenv("INGEST_UPLOAD_DIR", str(tmp_path / "uploads"))

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def clean_db(test_db):
    """Convenience: return the test session for direct query in assertions."""
    session, _ = test_db
    return session


class TestUploadEndpoint:
    def test_upload_returns_ingest_run_id(self, client, clean_db):
        game = clean_db.query(Game).first()
        with open(FIXTURE, "rb") as f:
            resp = client.post(
                "/api/ingest/upload",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"game_id": str(game.id)},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "ingest_run_id" in body
        assert "preview" in body

    def test_upload_creates_ingest_run_row(self, client, clean_db):
        game = clean_db.query(Game).first()
        with open(FIXTURE, "rb") as f:
            resp = client.post(
                "/api/ingest/upload",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"game_id": str(game.id)},
            )
        run_id = resp.json()["ingest_run_id"]
        row = clean_db.query(IngestRun).filter_by(id=run_id).one()
        assert row.status == "pending_review"
        assert row.filename == "sample.pdf"


class TestGetEndpoint:
    def test_get_returns_parsed_data(self, client, clean_db):
        game = clean_db.query(Game).first()
        with open(FIXTURE, "rb") as f:
            up = client.post(
                "/api/ingest/upload",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"game_id": str(game.id)},
            )
        run_id = up.json()["ingest_run_id"]
        resp = client.get(f"/api/ingest/{run_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending_review"
        assert "parsed_json" in body


class TestCommitEndpoint:
    def test_commit_writes_to_db_and_sets_status(self, client, clean_db):
        game = clean_db.query(Game).first()
        with open(FIXTURE, "rb") as f:
            up = client.post(
                "/api/ingest/upload",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"game_id": str(game.id)},
            )
        run_id = up.json()["ingest_run_id"]
        resp = client.post(f"/api/ingest/{run_id}/commit")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "wrote" in body
        clean_db.expire_all()
        row = clean_db.query(IngestRun).filter_by(id=run_id).one()
        assert row.status == "committed"
        assert row.committed_at is not None


class TestDeleteEndpoint:
    def test_delete_sets_status_discarded(self, client, clean_db):
        game = clean_db.query(Game).first()
        with open(FIXTURE, "rb") as f:
            up = client.post(
                "/api/ingest/upload",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"game_id": str(game.id)},
            )
        run_id = up.json()["ingest_run_id"]
        resp = client.delete(f"/api/ingest/{run_id}")
        assert resp.status_code == 200
        clean_db.expire_all()
        row = clean_db.query(IngestRun).filter_by(id=run_id).one()
        assert row.status == "discarded"
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_ingest_router.py -v`
Expected: 404 / ImportError.

- [ ] **Step 3: Implement the router**

Create `backend/app/routers/ingest.py`:
```python
"""Endpoints for InStat PDF ingest.

Flow: upload → parse → store IngestRun → review (frontend) → commit or discard.
"""
import os
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import IngestRun, Game
from ..config import OUR_TEAM_NAME
from ..ingest.orchestrator import parse_all
from ..ingest.commit import commit_parsed


router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _upload_dir() -> str:
    d = os.environ.get(
        "INGEST_UPLOAD_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "ingest"),
    )
    os.makedirs(d, exist_ok=True)
    return d


@router.post("/upload")
def upload(
    file: UploadFile = File(...),
    game_id: int = Form(...),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter_by(id=game_id).one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    # Persist the file first (need the run_id to name it — two-phase)
    run = IngestRun(
        game_id=game_id,
        filename=file.filename or "unknown.pdf",
        parsed_json="{}",
        status="pending_review",
    )
    db.add(run)
    db.commit()

    dest = os.path.join(_upload_dir(), f"{run.id}.pdf")
    with open(dest, "wb") as f:
        f.write(file.file.read())

    try:
        parsed = parse_all(dest, OUR_TEAM_NAME)
    except Exception as e:
        run.status = "failed"
        run.error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Parse failed: {e}")

    run.parsed_json = json.dumps(parsed)
    db.commit()

    return {
        "ingest_run_id": run.id,
        "warnings": parsed["warnings"],
        "preview": parsed["templates"],
    }


@router.get("/{ingest_run_id}")
def get_run(ingest_run_id: int, db: Session = Depends(get_db)):
    run = db.query(IngestRun).filter_by(id=ingest_run_id).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": run.id,
        "game_id": run.game_id,
        "filename": run.filename,
        "uploaded_at": run.uploaded_at.isoformat() if run.uploaded_at else None,
        "status": run.status,
        "parsed_json": json.loads(run.parsed_json) if run.parsed_json else {},
        "committed_at": run.committed_at.isoformat() if run.committed_at else None,
        "error": run.error,
    }


class CommitPayload(BaseModel):
    parsed_json: Optional[dict] = None  # edited-by-user override


@router.post("/{ingest_run_id}/commit")
def commit_run(
    ingest_run_id: int,
    payload: Optional[CommitPayload] = None,
    db: Session = Depends(get_db),
):
    run = db.query(IngestRun).filter_by(id=ingest_run_id).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Not found")
    if run.status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Run is {run.status!r}, cannot commit",
        )

    parsed = (
        payload.parsed_json if (payload and payload.parsed_json is not None)
        else json.loads(run.parsed_json)
    )

    report = commit_parsed(parsed, run.game_id, db)

    run.status = "committed"
    run.committed_at = datetime.utcnow()
    run.parsed_json = json.dumps(parsed)  # persist the edited version
    db.commit()

    return report


@router.delete("/{ingest_run_id}")
def discard_run(ingest_run_id: int, db: Session = Depends(get_db)):
    run = db.query(IngestRun).filter_by(id=ingest_run_id).one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Not found")
    run.status = "discarded"
    db.commit()
    return {"status": "discarded"}
```

- [ ] **Step 4: Register router in main.py**

Edit `backend/app/main.py` — add near other `app.include_router` calls:
```python
from .routers import ingest as ingest_router
app.include_router(ingest_router.router)
```

- [ ] **Step 5: Update .gitignore**

Check `backend/.gitignore` (create if missing) — ensure `uploads/` is ignored:
```bash
grep -qxF "uploads/" backend/.gitignore 2>/dev/null || echo "uploads/" >> backend/.gitignore
```

- [ ] **Step 6: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_ingest_router.py -v`
Expected: 5 tests pass.

Also run the full suite: `backend/venv/bin/python -m pytest backend/tests/ -q`
Expected: all previously-passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/ingest.py backend/app/main.py backend/.gitignore backend/tests/test_ingest_router.py
git commit -m "feat: add /api/ingest endpoints (upload, get, commit, discard)"
```

---

### Task 13: Frontend — `/ingest` upload page

**Files:**
- Create: `frontend/src/pages/IngestPage.tsx`
- Modify: `frontend/src/App.tsx` — add route + nav link
- Modify: `frontend/src/api/client.ts` — add `uploadIngest`, `getIngestRun` functions
- Modify: `frontend/src/types.ts` — add `IngestPreview`, `IngestRun` types

**Interfaces:**
- Consumes: `POST /api/ingest/upload`, `GET /api/games` (existing).
- Produces:
  - `IngestPage` React component at route `/ingest`.
  - `client.uploadIngest(file: File, gameId: number): Promise<{ingest_run_id, warnings, preview}>`.
  - `client.getIngestRun(id: number): Promise<IngestRun>`.
  - TypeScript types `IngestPreview` (mirrors backend `templates` shape) and `IngestRun`.

- [ ] **Step 1: Extend types**

Modify `frontend/src/types.ts` — append:
```typescript
export interface IngestTeamStats {
  pp_shots: number | null
  pp_time_seconds_in_oz: number | null
  pp_time_seconds_total: number | null
  pk_opp_breakouts: number | null
  pp_opp_breakouts_allowed: number | null
  puck_possession_seconds_total: number | null
  oz_possession_seconds: number | null
  oz_possession_pct: number | null
  scoring_chance_shots: number | null
  scoring_chance_shots_on_goal: number | null
}

export interface IngestPlayerRow {
  jersey_number: string
  player_name: string
  [key: string]: string | number | null
}

export interface IngestMatrixRow {
  from_jersey: string
  from_name: string
  to_jersey: string
  to_name: string
  delivered?: number
  received?: number
  count?: number
}

export interface IngestPreview {
  instat_team_stats: IngestTeamStats
  instat_players_main: IngestPlayerRow[]
  instat_time_distribution: IngestPlayerRow[]
  instat_challenges: IngestPlayerRow[]
  instat_hit_matrix: IngestMatrixRow[]
  instat_pass_matrix: IngestMatrixRow[]
}

export interface IngestRun {
  id: number
  game_id: number
  filename: string
  uploaded_at: string
  status: 'pending_review' | 'committed' | 'discarded' | 'failed'
  parsed_json: { templates: IngestPreview; warnings: string[] }
  committed_at: string | null
  error: string | null
}
```

- [ ] **Step 2: Extend client**

Modify `frontend/src/api/client.ts` — add:
```typescript
export async function uploadIngest(
  file: File, gameId: number
): Promise<{ ingest_run_id: number; warnings: string[]; preview: IngestPreview }> {
  const form = new FormData()
  form.append('file', file)
  form.append('game_id', String(gameId))
  const res = await fetch('/api/ingest/upload', { method: 'POST', body: form })
  if (!res.ok) throw new Error(`upload failed: ${res.status} ${await res.text()}`)
  return res.json()
}

export async function getIngestRun(id: number): Promise<IngestRun> {
  const res = await fetch(`/api/ingest/${id}`)
  if (!res.ok) throw new Error(`getIngestRun failed: ${res.status}`)
  return res.json()
}
```

Also import the types at the top: `import type { IngestPreview, IngestRun } from '../types'`.

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Create the IngestPage component**

Create `frontend/src/pages/IngestPage.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getGames, uploadIngest } from '../api/client'
import type { Game } from '../types'

export function IngestPage() {
  const navigate = useNavigate()
  const [games, setGames] = useState<Game[]>([])
  const [gameId, setGameId] = useState<number | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getGames().then(setGames).catch((e) => setError(String(e)))
  }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!file || gameId === null) {
      setError('Pick a game and a PDF file.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const { ingest_run_id } = await uploadIngest(file, gameId)
      navigate(`/ingest/${ingest_run_id}`)
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 640 }}>
      <h1>Ingest InStat Match Report</h1>
      <p style={{ color: 'var(--text-secondary)' }}>
        Upload an InStat match-report PDF for a game. The system parses it,
        then shows you the extracted values for review before committing.
      </p>
      <form onSubmit={submit} style={{ display: 'grid', gap: 16, marginTop: 16 }}>
        <label>
          Game:
          <select
            value={gameId ?? ''}
            onChange={(e) => setGameId(e.target.value ? Number(e.target.value) : null)}
            style={{ marginLeft: 8, padding: 4 }}
          >
            <option value="">— pick a game —</option>
            {games.map((g) => (
              <option key={g.id} value={g.id}>
                {g.date} vs. {g.opponent} ({g.is_home ? 'H' : 'A'})
              </option>
            ))}
          </select>
        </label>
        <label>
          PDF:
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            style={{ marginLeft: 8 }}
          />
        </label>
        <button type="submit" disabled={busy || !file || gameId === null}>
          {busy ? 'Uploading & parsing…' : 'Upload and parse'}
        </button>
        {error && (
          <div style={{ color: 'var(--color-red, #d63030)' }}>{error}</div>
        )}
      </form>
    </div>
  )
}
```

- [ ] **Step 5: Register route and nav link**

Modify `frontend/src/App.tsx` — add import and route. Locate the routes block (search for `<Route`) and add:
```tsx
import { IngestPage } from './pages/IngestPage'
// ...
<Route path="/ingest" element={<IngestPage />} />
```

Add a nav link in the site header (find the existing nav element in App.tsx, add):
```tsx
<Link to="/ingest">Ingest</Link>
```
Follow the existing nav link pattern (same wrapper element, same spacing).

- [ ] **Step 6: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/IngestPage.tsx frontend/src/App.tsx frontend/src/api/client.ts frontend/src/types.ts
git commit -m "feat: add /ingest upload page with PDF+game picker"
```

---

### Task 14: Frontend — `/ingest/:id` review page

**Files:**
- Create: `frontend/src/pages/IngestReviewPage.tsx`
- Modify: `frontend/src/App.tsx` — add route
- Modify: `frontend/src/api/client.ts` — add `commitIngest`, `discardIngest`

**Interfaces:**
- Consumes: `GET /api/ingest/{id}`, `POST /api/ingest/{id}/commit`, `DELETE /api/ingest/{id}`.
- Produces:
  - `IngestReviewPage` React component at route `/ingest/:id`.
  - `client.commitIngest(id, parsedJson?)`.
  - `client.discardIngest(id)`.

- [ ] **Step 1: Extend client**

Modify `frontend/src/api/client.ts` — append:
```typescript
export async function commitIngest(
  id: number, parsedJson?: { templates: IngestPreview; warnings: string[] }
): Promise<{ wrote: Record<string, number>; skipped: string[] }> {
  const body = parsedJson !== undefined ? JSON.stringify({ parsed_json: parsedJson }) : undefined
  const res = await fetch(`/api/ingest/${id}/commit`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body,
  })
  if (!res.ok) throw new Error(`commit failed: ${res.status} ${await res.text()}`)
  return res.json()
}

export async function discardIngest(id: number): Promise<{ status: string }> {
  const res = await fetch(`/api/ingest/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`discard failed: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Create the review page**

Create `frontend/src/pages/IngestReviewPage.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getIngestRun, commitIngest, discardIngest } from '../api/client'
import type { IngestRun, IngestPreview } from '../types'


export function IngestReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [run, setRun] = useState<IngestRun | null>(null)
  const [preview, setPreview] = useState<IngestPreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ wrote: Record<string, number>; skipped: string[] } | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!id) return
    getIngestRun(Number(id))
      .then((r) => {
        setRun(r)
        setPreview(r.parsed_json.templates)
      })
      .catch((e) => setError(String(e)))
  }, [id])

  if (error) return <div style={{ padding: 24, color: 'var(--color-red)' }}>{error}</div>
  if (!run || !preview) return <div style={{ padding: 24 }}>Loading…</div>

  async function commit() {
    setBusy(true)
    try {
      const r = await commitIngest(Number(id), { templates: preview!, warnings: run!.parsed_json.warnings })
      setResult(r)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function discard() {
    if (!confirm('Discard this ingest? The uploaded PDF is preserved but no DB changes will be made.')) return
    await discardIngest(Number(id))
    navigate('/ingest')
  }

  if (result) {
    return (
      <div style={{ padding: 24 }}>
        <h1>Committed ✓</h1>
        <p>Rows written per template:</p>
        <ul>
          {Object.entries(result.wrote).map(([k, v]) => (
            <li key={k}>{k}: {v}</li>
          ))}
        </ul>
        {result.skipped.length > 0 && (
          <>
            <p style={{ marginTop: 16 }}>Skipped rows:</p>
            <ul>{result.skipped.map((s, i) => <li key={i}>{s}</li>)}</ul>
          </>
        )}
        <button onClick={() => navigate('/ingest')}>Back to ingest</button>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 1000 }}>
      <h1>Review ingest: {run.filename}</h1>
      <p style={{ color: 'var(--text-secondary)' }}>
        Status: {run.status} · Game #{run.game_id} · Uploaded {run.uploaded_at}
      </p>

      {run.parsed_json.warnings.length > 0 && (
        <div style={{ background: 'var(--warn-bg, #4a3a1e)', padding: 12, borderRadius: 4, marginBottom: 16 }}>
          <strong>Warnings:</strong>
          <ul>{run.parsed_json.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}

      <TemplateSection title="Team stats" data={preview.instat_team_stats}
        onChange={(v) => setPreview({ ...preview, instat_team_stats: v })} />

      <PlayerRowsSection title="Players (main)" rows={preview.instat_players_main}
        onChange={(v) => setPreview({ ...preview, instat_players_main: v })} />

      <PlayerRowsSection title="Time distribution" rows={preview.instat_time_distribution}
        onChange={(v) => setPreview({ ...preview, instat_time_distribution: v })} />

      <PlayerRowsSection title="Challenges (puck battles)" rows={preview.instat_challenges}
        onChange={(v) => setPreview({ ...preview, instat_challenges: v })} />

      <MatrixSection title={`Hit matrix (${preview.instat_hit_matrix.length} pairs)`}
        rows={preview.instat_hit_matrix} kind="hits" />

      <MatrixSection title={`Pass matrix (${preview.instat_pass_matrix.length} pairs)`}
        rows={preview.instat_pass_matrix} kind="passes" />

      <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
        <button onClick={commit} disabled={busy}>
          {busy ? 'Committing…' : 'Commit to database'}
        </button>
        <button onClick={discard} disabled={busy} style={{ background: 'transparent' }}>
          Discard
        </button>
      </div>
    </div>
  )
}


function TemplateSection<T extends Record<string, number | null>>({
  title, data, onChange,
}: { title: string; data: T; onChange: (v: T) => void }) {
  const [open, setOpen] = useState(true)
  return (
    <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      style={{ border: '1px solid var(--border-color, #333)', borderRadius: 4, padding: 8, marginTop: 12 }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{title}</summary>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginTop: 8 }}>
        {Object.entries(data).map(([k, v]) => (
          <label key={k} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ minWidth: 200 }}>{k}:</span>
            <input
              type="number"
              value={v ?? ''}
              step="any"
              onChange={(e) => onChange({ ...data, [k]: e.target.value === '' ? null : Number(e.target.value) } as T)}
              style={{ padding: 4, flex: 1 }}
            />
          </label>
        ))}
      </div>
    </details>
  )
}


function PlayerRowsSection({
  title, rows, onChange,
}: { title: string; rows: any[]; onChange: (v: any[]) => void }) {
  const [open, setOpen] = useState(false)
  if (rows.length === 0) return null
  const keys = Object.keys(rows[0])
  return (
    <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      style={{ border: '1px solid var(--border-color, #333)', borderRadius: 4, padding: 8, marginTop: 12 }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{title} ({rows.length} players)</summary>
      <table style={{ marginTop: 8, width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>{keys.map((k) => <th key={k} style={{ textAlign: 'left', padding: 4, borderBottom: '1px solid #333' }}>{k}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {keys.map((k) => (
                <td key={k} style={{ padding: 2 }}>
                  <input
                    value={r[k] ?? ''}
                    onChange={(e) => {
                      const next = [...rows]
                      const val = e.target.value
                      next[i] = { ...r, [k]: val === '' ? null : (isNaN(Number(val)) ? val : Number(val)) }
                      onChange(next)
                    }}
                    style={{ width: '100%', padding: 2, border: '1px solid #444', background: 'transparent', color: 'inherit' }}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}


function MatrixSection({
  title, rows, kind,
}: { title: string; rows: any[]; kind: 'hits' | 'passes' }) {
  const [open, setOpen] = useState(false)
  if (rows.length === 0) return null
  return (
    <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      style={{ border: '1px solid var(--border-color, #333)', borderRadius: 4, padding: 8, marginTop: 12 }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{title}</summary>
      <table style={{ marginTop: 8, borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr>
            <th style={{ padding: 4 }}>From</th>
            <th style={{ padding: 4 }}>To</th>
            {kind === 'hits' ? (
              <>
                <th style={{ padding: 4 }}>Delivered</th>
                <th style={{ padding: 4 }}>Received</th>
              </>
            ) : (
              <th style={{ padding: 4 }}>Count</th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td style={{ padding: 4 }}>#{r.from_jersey} {r.from_name}</td>
              <td style={{ padding: 4 }}>#{r.to_jersey} {r.to_name}</td>
              {kind === 'hits' ? (
                <>
                  <td style={{ padding: 4 }}>{r.delivered}</td>
                  <td style={{ padding: 4 }}>{r.received}</td>
                </>
              ) : (
                <td style={{ padding: 4 }}>{r.count}</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ marginTop: 8, color: 'var(--text-secondary)', fontSize: 12 }}>
        Matrix rows are read-only in this view — edit players' main stats above if a jersey needs to change.
      </p>
    </details>
  )
}
```

- [ ] **Step 4: Register route**

Modify `frontend/src/App.tsx` — add:
```tsx
import { IngestReviewPage } from './pages/IngestReviewPage'
// ...
<Route path="/ingest/:id" element={<IngestReviewPage />} />
```

- [ ] **Step 5: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/IngestReviewPage.tsx frontend/src/App.tsx frontend/src/api/client.ts
git commit -m "feat: add /ingest/:id review page with editable extracted values"
```

---

### Task 15: End-to-end integration test

**Files:**
- Create: `backend/tests/test_ingest_end_to_end.py`

**Interfaces:**
- Consumes: full ingest stack (upload → parse → commit) + DB models.
- Produces: one integration test that uploads the fixture PDF, commits, and asserts DB state matches expected shape.

- [ ] **Step 1: Write the integration test**

Create `backend/tests/test_ingest_end_to_end.py`:
```python
"""End-to-end verification of the ingest pipeline.

Uploads the fixture PDF, commits it, then queries every target table
to confirm data landed. Uses the same isolated-DB fixture pattern as
test_ingest_router.py (dependency_overrides + tmp SQLite).
"""
import os
from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_db
from app.models import (
    Player, Game, TeamGameStatsInStat, PlayerGameStatsInStat,
    PlayerGameStats, PlayerHitMatrix, PlayerPassMatrix, IngestRun,
)


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "instat_sample.pdf")


@pytest.fixture
def test_db(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    for name, num in [
        ("Finnegan", "8"), ("Paulsen", "7"), ("Ley", "16"), ("Biotti", "5"),
        ("Sun", "20"), ("Kasica", "21"), ("MacDonald", "3"), ("Lapp", "9"),
        ("Megdanis", "10"), ("McGathey", "4"), ("Sproule", "17"),
        ("McSweeney", "14"), ("Lucia", "28"), ("Dinges", "24"),
        ("Boosamra", "12"), ("Hamann", "11"),
    ]:
        session.add(Player(name=name, number=num, position="F",
                           is_center=False, active=True))
    session.add(Game(date=date(2026, 3, 2), opponent="Princeton",
                     is_home=False, season="2025-26", data_source="instat"))
    session.commit()
    yield session, Session
    session.close()


@pytest.fixture
def client(test_db, tmp_path, monkeypatch):
    _, Session = test_db
    monkeypatch.setenv("INGEST_UPLOAD_DIR", str(tmp_path / "uploads"))

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_db(test_db):
    session, _ = test_db
    return session


class TestEndToEnd:
    def test_full_ingest_and_commit(self, client, seeded_db):
        game = seeded_db.query(Game).first()

        # Upload
        with open(FIXTURE, "rb") as f:
            resp = client.post(
                "/api/ingest/upload",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"game_id": str(game.id)},
            )
        assert resp.status_code == 200, resp.text
        run_id = resp.json()["ingest_run_id"]

        # Commit
        resp = client.post(f"/api/ingest/{run_id}/commit")
        assert resp.status_code == 200, resp.text
        report = resp.json()

        # Verify DB state
        seeded_db.expire_all()

        # Team stats row exists
        team = seeded_db.query(TeamGameStatsInStat).filter_by(game_id=game.id).one()
        assert team is not None

        # At least some player rows landed
        assert seeded_db.query(PlayerGameStatsInStat).filter_by(game_id=game.id).count() >= 10
        assert seeded_db.query(PlayerGameStats).filter_by(game_id=game.id).count() >= 10

        # Matrices populated (pass matrix expected non-empty; hit matrix may be small)
        assert seeded_db.query(PlayerPassMatrix).filter_by(game_id=game.id).count() >= 10

        # IngestRun is marked committed
        run = seeded_db.query(IngestRun).filter_by(id=run_id).one()
        assert run.status == "committed"
        assert run.committed_at is not None

        # Report matches DB counts
        assert report["wrote"]["instat_team_stats"] == 1
        assert report["wrote"]["instat_players_main"] > 0
        assert report["wrote"]["instat_pass_matrix"] > 0
```

- [ ] **Step 2: Run the test**

Run: `backend/venv/bin/python -m pytest backend/tests/test_ingest_end_to_end.py -v`
Expected: 1 test passes.

Also run the whole suite:
`backend/venv/bin/python -m pytest backend/tests/ -q`
Expected: all tests pass (baseline 68 + all Phase 2 additions).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_ingest_end_to_end.py
git commit -m "test: end-to-end integration test for InStat ingest pipeline"
```

---

## Final verification

- [ ] **Migration idempotency:**
  ```
  cd backend && venv/bin/python migrate_v6.py
  cd backend && venv/bin/python migrate_v6.py   # second run — clean no-op
  ```

- [ ] **Full backend suite passes.** All tests green including baseline 68 + Phase 2 additions (~50-60 new depending on parser edge cases).

- [ ] **Frontend typecheck passes:** `cd frontend && npx tsc --noEmit` → no errors.

- [ ] **Manual smoke test (documented, deferred):** the coach uploads a real InStat PDF via `/ingest`, reviews the extracted data, commits. Any parser adjustments discovered during smoke testing land as follow-up commits.

- [ ] **Ledger deferred / follow-ups:**
  - Manual smoke test with a second real PDF (different game) — verifies parser generality.
  - Move `our_team_name` to a settings table when the app tracks more than one team.
  - Consider adding a diff view showing "what will change" before commit (compare parsed values against existing DB rows).
  - Shots-log parser (P6/14) — Phase 4 scope.
  - Line-combinations parser (P4/12) — no downstream consumer yet.
