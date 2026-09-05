# Phase 3: Tier 2 Stats — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship six Tier 2 coach-visible stats (Contested Puck Win %, Zone Entry Composition, Turnover Location Ratio, Special Teams v2, Danger-Zone Shot Share, Impact Score) computed from the InStat data Phase 2 now ingests, plus existing 49ing data. Every stat surfaces on the player report and (where applicable) team report with availability metadata driving N/A rendering.

**Architecture:** Pure compute layer in `app/tier2_stats.py` — one function per stat, each taking already-loaded rows (no DB access). Router loads InStat rows once via new helpers in `app/enrichment.py`, passes them to `enrich_player_agg` which orchestrates all Tier 2 stat computations onto the response payload. Frontend gets three new components (`PuckBattleBlock`, `EntryCompositionBar`, `ImpactScoreCard`) plus reuses Phase 1's `StatCard` where the shape fits. Methodology page loses "🚧 Coming Soon" pills for shipped stats.

**Tech Stack:** Python 3.9 · SQLAlchemy · FastAPI · Pydantic v2 · React + TypeScript + Vite. All Phase 0/1/2 infrastructure is prerequisite.

**Spec:** `docs/superpowers/specs/2026-08-18-ecac-stats-expansion-design.md` (§6 Tier 2 stats overview, §9 methodology formulas §9.1–§9.6).

## Global Constraints

- **Stat sources honored:** Contested Puck Win, Zone Entry, Turnover Ratio, Special Teams v2 are InStat-only. Impact Score and Danger-Zone Shot Share are both-source with 49ing components. Missing InStat data → the stat renders N/A (leveraging Phase 0's availability metadata system).
- **Impact Score formula (spec §9.1):** per-game z-score across (up to) four components — `on_ice_xGF60 - xGA60`, `on_ice_CF%`, `puck_battle_W%` (InStat only), `controlled_entry_%` (InStat only, F/W only). Component missing → dropped from that game's mean. Season aggregate = TOI-weighted mean of per-game Impact scores, clamped to `[-3, +3]`. Position cohorts (Phase 1 `app/cohorts.py`) supply the reference distribution.
- **Special Teams v2 is TEAM-LEVEL** — attaches to team aggregate, not player. All three metrics computed from `TeamGameStatsInStat` (`pp_shots`, `pp_time_seconds_total`, `pp_time_seconds_in_oz`, `pk_opp_breakouts`, `pp_opp_breakouts_allowed`).
- **Compute functions are pure** — take already-loaded rows, no DB access. Router does the queries once. Keeps functions unit-testable without a DB fixture.
- **No changes to existing computed stats** — Tier 2 is additive. Phase 0/1 fields, per-60 rates, comparisons, flags all keep their current values.
- **Availability metadata** — where a stat is missing all supporting InStat rows in the window, the response payload emits `{value: None, sources: []}` shape; frontend N/A renderer (Phase 0's `StatCard` availability prop) handles display.
- **Test runner:** `backend/venv/bin/python -m pytest ...` from worktree root. No `pytest` binary — always use `python -m pytest`.
- **Pydantic v2** style (`model_config = {"from_attributes": True}`).
- **Commit style:** conventional-commits (`feat:`, `test:`, `fix:`, `chore:`).
- **Frontend typecheck:** `cd frontend && npx tsc --noEmit` must pass with zero errors after every frontend-touching task.
- **Position groups** (spec §9.12): C (centers), F (all forwards), W (wingers), D (defenders), G (goalies). Impact Score's `controlled_entry_%` component is F/W-only per spec §9.1.
- **Migrations:** none. Phase 3 adds no new tables — reads existing `PlayerGameStatsInStat` / `TeamGameStatsInStat` / `PlayerGameStats`.
- **`ReportsPage.tsx` and `MethodologyPage.tsx` are the only frontend files that change beyond types + new components** — this preserves Phase 1's report structure.

---

### Task 1: Foundation — `app/tier2_stats.py` module + row-loading helpers

**Files:**
- Create: `backend/app/tier2_stats.py`
- Modify: `backend/app/enrichment.py` (add row-loader helpers)
- Create: `backend/tests/test_tier2_stats_foundation.py`

**Interfaces:**
- Consumes: existing `PlayerGameStatsInStat`, `TeamGameStatsInStat`, `Game`, `Player` models.
- Produces:
  - `app/tier2_stats.py` module scaffold with shared imports.
  - `load_player_instat_rows(db, player_id, date_from=None, date_to=None) -> list[PlayerGameStatsInStat]` in `enrichment.py`.
  - `load_team_instat_rows(db, date_from=None, date_to=None) -> list[TeamGameStatsInStat]` in `enrichment.py`.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_tier2_stats_foundation.py`:
```python
import pytest
from datetime import date
from app.models import Player, Game, PlayerGameStatsInStat, TeamGameStatsInStat
from app.enrichment import load_player_instat_rows, load_team_instat_rows


@pytest.fixture
def seeded_instat(db_session):
    p = Player(name="Ten", number="10", position="F", is_center=True, active=True)
    games = [
        Game(date=date(2025, 10, 1), opponent="A", is_home=True,  season="2025-26", data_source="instat"),
        Game(date=date(2025, 10, 8), opponent="B", is_home=False, season="2025-26", data_source="instat"),
        Game(date=date(2025, 10, 15), opponent="C", is_home=True, season="2025-26", data_source="49ing"),
    ]
    db_session.add(p)
    for g in games:
        db_session.add(g)
    db_session.commit()

    for g in games[:2]:  # only InStat games get InStat rows
        db_session.add(PlayerGameStatsInStat(
            player_id=p.id, game_id=g.id,
            shots=5, hits_delivered=2, pb_won_dz=3, pb_total_dz=5,
        ))
        db_session.add(TeamGameStatsInStat(
            game_id=g.id, pp_shots=8, pp_time_seconds_total=300,
        ))
    db_session.commit()
    return p, games


class TestLoadPlayerInstatRows:
    def test_loads_all_when_no_date_filter(self, db_session, seeded_instat):
        p, _ = seeded_instat
        rows = load_player_instat_rows(db_session, p.id)
        assert len(rows) == 2

    def test_filters_by_date_range(self, db_session, seeded_instat):
        p, _ = seeded_instat
        rows = load_player_instat_rows(db_session, p.id,
                                       date_from=date(2025, 10, 5),
                                       date_to=date(2025, 10, 20))
        assert len(rows) == 1

    def test_returns_empty_for_unknown_player(self, db_session, seeded_instat):
        rows = load_player_instat_rows(db_session, 99999)
        assert rows == []


class TestLoadTeamInstatRows:
    def test_loads_all_when_no_date_filter(self, db_session, seeded_instat):
        rows = load_team_instat_rows(db_session)
        assert len(rows) == 2

    def test_filters_by_date_range(self, db_session, seeded_instat):
        rows = load_team_instat_rows(db_session,
                                     date_from=date(2025, 10, 5),
                                     date_to=date(2025, 10, 20))
        assert len(rows) == 1


class TestModuleScaffold:
    def test_module_importable(self):
        import app.tier2_stats  # noqa: F401
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_tier2_stats_foundation.py -v`
Expected: `ImportError` (module and helpers don't exist yet).

- [ ] **Step 3: Create the module scaffold**

Create `backend/app/tier2_stats.py`:
```python
"""Tier 2 stat computations — Contested Puck Win %, Zone Entry Composition,
Turnover Location Ratio, Special Teams v2, Danger-Zone Shot Share, Impact Score.

All functions in this module are PURE — they take already-loaded SQLAlchemy
rows and return dicts. Callers (typically the enrichment layer) load the rows
via the helpers in enrichment.py and pass them in.

See spec §9.1–§9.6 for formulas.
"""
from typing import Optional
```

- [ ] **Step 4: Add loader helpers to enrichment.py**

Modify `backend/app/enrichment.py` — append at end:

```python
from datetime import date as _date
from sqlalchemy.orm import Session
from typing import Optional as _Optional
from .models import PlayerGameStatsInStat, TeamGameStatsInStat, Game


def load_player_instat_rows(
    db: Session,
    player_id: int,
    date_from: _Optional[_date] = None,
    date_to: _Optional[_date] = None,
) -> list[PlayerGameStatsInStat]:
    """Load PlayerGameStatsInStat rows for a player, optionally filtered by
    game date range. Returns [] if the player has no rows."""
    q = db.query(PlayerGameStatsInStat).join(Game).filter(
        PlayerGameStatsInStat.player_id == player_id
    )
    if date_from is not None:
        q = q.filter(Game.date >= date_from)
    if date_to is not None:
        q = q.filter(Game.date <= date_to)
    return q.all()


def load_team_instat_rows(
    db: Session,
    date_from: _Optional[_date] = None,
    date_to: _Optional[_date] = None,
) -> list[TeamGameStatsInStat]:
    """Load TeamGameStatsInStat rows, optionally filtered by game date range."""
    q = db.query(TeamGameStatsInStat).join(Game)
    if date_from is not None:
        q = q.filter(Game.date >= date_from)
    if date_to is not None:
        q = q.filter(Game.date <= date_to)
    return q.all()
```

- [ ] **Step 5: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_tier2_stats_foundation.py -v`
Expected: 6 tests pass.

Also run full suite: `backend/venv/bin/python -m pytest backend/tests/ --ignore=backend/tests/test_ingest_router.py --ignore=backend/tests/test_ingest_end_to_end.py --ignore=backend/tests/test_orchestrator.py -q`
Expected: baseline + 6 new tests pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tier2_stats.py backend/app/enrichment.py backend/tests/test_tier2_stats_foundation.py
git commit -m "feat: add tier2_stats module scaffold and InStat row-loading helpers"
```

---

### Task 2: `contested_puck_win_pct` (§9.2)

**Files:**
- Modify: `backend/app/tier2_stats.py`
- Create: `backend/tests/test_contested_puck.py`

**Interfaces:**
- Consumes: `PlayerGameStatsInStat` rows (loaded via `load_player_instat_rows`).
- Produces:
  - `contested_puck_win_pct(instat_rows: list[PlayerGameStatsInStat]) -> dict` — returns `{"overall_pct": float|None, "dz_pct": float|None, "oz_pct": float|None, "nz_pct": float|None, "games": int}`. Percentages are fractions in `[0, 1]` or `None` if the zone had zero total attempts. `games` is count of rows with any pb_total_* > 0.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_contested_puck.py`:
```python
import pytest
from app.tier2_stats import contested_puck_win_pct
from app.models import PlayerGameStatsInStat


def _row(pb_won_dz=None, pb_total_dz=None, pb_won_oz=None, pb_total_oz=None,
         pb_won_nz=None, pb_total_nz=None):
    r = PlayerGameStatsInStat(game_id=1, player_id=1)
    r.pb_won_dz = pb_won_dz
    r.pb_total_dz = pb_total_dz
    r.pb_won_oz = pb_won_oz
    r.pb_total_oz = pb_total_oz
    r.pb_won_nz = pb_won_nz
    r.pb_total_nz = pb_total_nz
    return r


class TestContestedPuckWinPct:
    def test_empty_returns_all_none(self):
        result = contested_puck_win_pct([])
        assert result == {
            "overall_pct": None, "dz_pct": None,
            "oz_pct": None, "nz_pct": None, "games": 0,
        }

    def test_single_game_all_zones(self):
        rows = [_row(3, 5, 4, 6, 2, 4)]
        r = contested_puck_win_pct(rows)
        assert r["dz_pct"] == pytest.approx(0.6)
        assert r["oz_pct"] == pytest.approx(4/6)
        assert r["nz_pct"] == pytest.approx(0.5)
        assert r["overall_pct"] == pytest.approx(9 / 15)
        assert r["games"] == 1

    def test_multi_game_aggregates_won_and_total(self):
        rows = [_row(3, 5, 2, 4, 1, 2), _row(4, 8, 3, 6, 2, 3)]
        r = contested_puck_win_pct(rows)
        assert r["dz_pct"] == pytest.approx(7 / 13)
        assert r["oz_pct"] == pytest.approx(5 / 10)
        assert r["nz_pct"] == pytest.approx(3 / 5)
        assert r["overall_pct"] == pytest.approx(15 / 28)
        assert r["games"] == 2

    def test_zone_with_zero_total_returns_none(self):
        rows = [_row(pb_won_dz=1, pb_total_dz=2)]  # OZ and NZ absent
        r = contested_puck_win_pct(rows)
        assert r["dz_pct"] == pytest.approx(0.5)
        assert r["oz_pct"] is None
        assert r["nz_pct"] is None
        # Overall computed from what's present
        assert r["overall_pct"] == pytest.approx(0.5)

    def test_none_fields_treated_as_zero(self):
        rows = [_row(None, None, 2, 4, None, None)]
        r = contested_puck_win_pct(rows)
        assert r["dz_pct"] is None
        assert r["oz_pct"] == pytest.approx(0.5)
        assert r["nz_pct"] is None

    def test_games_counts_rows_with_any_pb_total(self):
        rows = [_row(1, 2, None, None, None, None),
                _row(None, None, 3, 5, None, None),
                _row(None, None, None, None, None, None)]  # empty row not counted
        r = contested_puck_win_pct(rows)
        assert r["games"] == 2
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_contested_puck.py -v`
Expected: `ImportError: cannot import name 'contested_puck_win_pct'`.

- [ ] **Step 3: Implement**

Append to `backend/app/tier2_stats.py`:

```python
def contested_puck_win_pct(instat_rows: list) -> dict:
    """Aggregate puck-battle W% overall and by zone (§9.2).

    Percentages in [0, 1]. Zones with zero total attempts across the window
    return None. `games` counts rows with any pb_total_* > 0.
    """
    won_dz = tot_dz = won_oz = tot_oz = won_nz = tot_nz = 0
    games = 0
    for r in instat_rows:
        has_any = False
        if r.pb_total_dz and r.pb_total_dz > 0:
            won_dz += r.pb_won_dz or 0
            tot_dz += r.pb_total_dz
            has_any = True
        if r.pb_total_oz and r.pb_total_oz > 0:
            won_oz += r.pb_won_oz or 0
            tot_oz += r.pb_total_oz
            has_any = True
        if r.pb_total_nz and r.pb_total_nz > 0:
            won_nz += r.pb_won_nz or 0
            tot_nz += r.pb_total_nz
            has_any = True
        if has_any:
            games += 1

    def _pct(w: int, t: int) -> Optional[float]:
        return w / t if t > 0 else None

    total_won = won_dz + won_oz + won_nz
    total_tot = tot_dz + tot_oz + tot_nz
    return {
        "overall_pct": _pct(total_won, total_tot),
        "dz_pct": _pct(won_dz, tot_dz),
        "oz_pct": _pct(won_oz, tot_oz),
        "nz_pct": _pct(won_nz, tot_nz),
        "games": games,
    }
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_contested_puck.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tier2_stats.py backend/tests/test_contested_puck.py
git commit -m "feat: add contested_puck_win_pct tier2 stat function"
```

---

### Task 3: `zone_entry_composition` (§9.4)

**Files:**
- Modify: `backend/app/tier2_stats.py`
- Create: `backend/tests/test_zone_entry.py`

**Interfaces:**
- Consumes: `PlayerGameStatsInStat` rows.
- Produces:
  - `zone_entry_composition(instat_rows) -> dict` — returns `{"pass_pct": float|None, "stick_pct": float|None, "dump_pct": float|None, "total_entries": int, "games": int}`. Percentages are fractions summing to 1.0 (if total > 0); `None` if `total_entries == 0`.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_zone_entry.py`:
```python
import pytest
from app.tier2_stats import zone_entry_composition
from app.models import PlayerGameStatsInStat


def _row(entries_pass=None, entries_stick=None, entries_dump=None):
    r = PlayerGameStatsInStat(game_id=1, player_id=1)
    r.entries_pass = entries_pass
    r.entries_stick = entries_stick
    r.entries_dump = entries_dump
    return r


class TestZoneEntryComposition:
    def test_empty_returns_none_pcts(self):
        assert zone_entry_composition([]) == {
            "pass_pct": None, "stick_pct": None, "dump_pct": None,
            "total_entries": 0, "games": 0,
        }

    def test_single_game(self):
        rows = [_row(3, 4, 2)]
        r = zone_entry_composition(rows)
        assert r["pass_pct"] == pytest.approx(3 / 9)
        assert r["stick_pct"] == pytest.approx(4 / 9)
        assert r["dump_pct"] == pytest.approx(2 / 9)
        assert r["total_entries"] == 9
        assert r["games"] == 1

    def test_multi_game_aggregates(self):
        rows = [_row(3, 4, 2), _row(1, 2, 1)]
        r = zone_entry_composition(rows)
        assert r["pass_pct"] == pytest.approx(4 / 13)
        assert r["stick_pct"] == pytest.approx(6 / 13)
        assert r["dump_pct"] == pytest.approx(3 / 13)
        assert r["total_entries"] == 13
        assert r["games"] == 2

    def test_all_zero_returns_none(self):
        rows = [_row(0, 0, 0), _row(None, None, None)]
        r = zone_entry_composition(rows)
        assert r["pass_pct"] is None
        assert r["stick_pct"] is None
        assert r["dump_pct"] is None
        assert r["total_entries"] == 0
        assert r["games"] == 0

    def test_none_fields_treated_as_zero(self):
        rows = [_row(None, 5, None)]
        r = zone_entry_composition(rows)
        assert r["pass_pct"] == pytest.approx(0.0)
        assert r["stick_pct"] == pytest.approx(1.0)
        assert r["dump_pct"] == pytest.approx(0.0)
        assert r["total_entries"] == 5
        assert r["games"] == 1
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_zone_entry.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement**

Append to `backend/app/tier2_stats.py`:

```python
def zone_entry_composition(instat_rows: list) -> dict:
    """Aggregate entry method percentages (§9.4).

    Returns pass/stick/dump percentages as fractions in [0, 1] summing to 1.0
    (when total > 0). All-None when the window has no entries.
    """
    pass_total = stick_total = dump_total = 0
    games = 0
    for r in instat_rows:
        p = r.entries_pass or 0
        s = r.entries_stick or 0
        d = r.entries_dump or 0
        if (p + s + d) > 0:
            pass_total += p
            stick_total += s
            dump_total += d
            games += 1

    total = pass_total + stick_total + dump_total
    if total == 0:
        return {
            "pass_pct": None, "stick_pct": None, "dump_pct": None,
            "total_entries": 0, "games": 0,
        }
    return {
        "pass_pct": pass_total / total,
        "stick_pct": stick_total / total,
        "dump_pct": dump_total / total,
        "total_entries": total,
        "games": games,
    }
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_zone_entry.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tier2_stats.py backend/tests/test_zone_entry.py
git commit -m "feat: add zone_entry_composition tier2 stat function"
```

---

### Task 4: `turnover_location_ratio` (§9.5)

**Files:**
- Modify: `backend/app/tier2_stats.py`
- Create: `backend/tests/test_turnover_ratio.py`

**Interfaces:**
- Consumes: `PlayerGameStatsInStat` rows.
- Produces:
  - `turnover_location_ratio(instat_rows) -> dict` — returns `{"dz_loss_share": float|None, "oz_recovery_share": float|None, "total_losses": int, "total_recoveries": int, "games": int}`. Shares are fractions in `[0, 1]`, `None` when the denominator is 0.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_turnover_ratio.py`:
```python
import pytest
from app.tier2_stats import turnover_location_ratio
from app.models import PlayerGameStatsInStat


def _row(puck_losses=None, puck_losses_dz=None, puck_recoveries=None, puck_recoveries_oz=None):
    r = PlayerGameStatsInStat(game_id=1, player_id=1)
    r.puck_losses = puck_losses
    r.puck_losses_dz = puck_losses_dz
    r.puck_recoveries = puck_recoveries
    r.puck_recoveries_oz = puck_recoveries_oz
    return r


class TestTurnoverLocationRatio:
    def test_empty(self):
        assert turnover_location_ratio([]) == {
            "dz_loss_share": None, "oz_recovery_share": None,
            "total_losses": 0, "total_recoveries": 0, "games": 0,
        }

    def test_single_game(self):
        rows = [_row(6, 2, 8, 3)]
        r = turnover_location_ratio(rows)
        assert r["dz_loss_share"] == pytest.approx(2 / 6)
        assert r["oz_recovery_share"] == pytest.approx(3 / 8)
        assert r["total_losses"] == 6
        assert r["total_recoveries"] == 8
        assert r["games"] == 1

    def test_multi_game_aggregates(self):
        rows = [_row(6, 2, 8, 3), _row(4, 1, 5, 2)]
        r = turnover_location_ratio(rows)
        assert r["dz_loss_share"] == pytest.approx(3 / 10)
        assert r["oz_recovery_share"] == pytest.approx(5 / 13)

    def test_zero_losses_returns_none_share(self):
        rows = [_row(0, 0, 5, 2)]
        r = turnover_location_ratio(rows)
        assert r["dz_loss_share"] is None
        assert r["oz_recovery_share"] == pytest.approx(2 / 5)

    def test_none_fields_treated_as_zero(self):
        rows = [_row(None, None, None, None)]
        r = turnover_location_ratio(rows)
        assert r["dz_loss_share"] is None
        assert r["oz_recovery_share"] is None
        assert r["games"] == 0
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_turnover_ratio.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement**

Append to `backend/app/tier2_stats.py`:

```python
def turnover_location_ratio(instat_rows: list) -> dict:
    """Aggregate turnover-location metrics (§9.5).

    - dz_loss_share: DZ losses ÷ total losses
    - oz_recovery_share: OZ recoveries ÷ total recoveries
    Both are None when their denominator is 0.
    """
    total_losses = 0
    dz_losses = 0
    total_recoveries = 0
    oz_recoveries = 0
    games = 0
    for r in instat_rows:
        losses = r.puck_losses or 0
        recoveries = r.puck_recoveries or 0
        if losses > 0 or recoveries > 0:
            games += 1
        total_losses += losses
        dz_losses += r.puck_losses_dz or 0
        total_recoveries += recoveries
        oz_recoveries += r.puck_recoveries_oz or 0

    return {
        "dz_loss_share": (dz_losses / total_losses) if total_losses > 0 else None,
        "oz_recovery_share": (oz_recoveries / total_recoveries) if total_recoveries > 0 else None,
        "total_losses": total_losses,
        "total_recoveries": total_recoveries,
        "games": games,
    }
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_turnover_ratio.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tier2_stats.py backend/tests/test_turnover_ratio.py
git commit -m "feat: add turnover_location_ratio tier2 stat function"
```

---

### Task 5: `special_teams_v2` (§9.3, team-level)

**Files:**
- Modify: `backend/app/tier2_stats.py`
- Create: `backend/tests/test_special_teams_v2.py`

**Interfaces:**
- Consumes: `TeamGameStatsInStat` rows.
- Produces:
  - `special_teams_v2(team_instat_rows) -> dict` — returns `{"pp_shots_per_min": float|None, "pp_oz_ratio": float|None, "pk_opp_breakout_rate": float|None, "pp_minutes": float|None, "pk_count": int, "games": int}`. All None when no InStat team rows have the source data.
  - `pp_shots_per_min` = total PP shots ÷ total PP minutes (seconds/60).
  - `pp_oz_ratio` = PP time in OZ ÷ total PP time.
  - `pk_opp_breakout_rate` = opp breakouts allowed on PK ÷ PK count. PK count = number of games with `pk_opp_breakouts` populated (proxy — the current InStat table doesn't record PK count directly, so we use games-with-data as denominator).

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_special_teams_v2.py`:
```python
import pytest
from app.tier2_stats import special_teams_v2
from app.models import TeamGameStatsInStat


def _row(pp_shots=None, pp_time_seconds_total=None, pp_time_seconds_in_oz=None,
         pk_opp_breakouts=None, pp_opp_breakouts_allowed=None):
    r = TeamGameStatsInStat(game_id=1)
    r.pp_shots = pp_shots
    r.pp_time_seconds_total = pp_time_seconds_total
    r.pp_time_seconds_in_oz = pp_time_seconds_in_oz
    r.pk_opp_breakouts = pk_opp_breakouts
    r.pp_opp_breakouts_allowed = pp_opp_breakouts_allowed
    return r


class TestSpecialTeamsV2:
    def test_empty(self):
        r = special_teams_v2([])
        assert r == {
            "pp_shots_per_min": None, "pp_oz_ratio": None,
            "pk_opp_breakout_rate": None, "pp_minutes": None,
            "pk_count": 0, "games": 0,
        }

    def test_single_game(self):
        rows = [_row(pp_shots=12, pp_time_seconds_total=600,
                     pp_time_seconds_in_oz=360, pk_opp_breakouts=2)]
        r = special_teams_v2(rows)
        assert r["pp_shots_per_min"] == pytest.approx(12 / 10.0)
        assert r["pp_oz_ratio"] == pytest.approx(0.6)
        assert r["pk_opp_breakout_rate"] == pytest.approx(2.0)  # 2 breakouts / 1 pk game
        assert r["pp_minutes"] == pytest.approx(10.0)
        assert r["pk_count"] == 1
        assert r["games"] == 1

    def test_multi_game(self):
        rows = [_row(pp_shots=10, pp_time_seconds_total=300, pp_time_seconds_in_oz=180,
                     pk_opp_breakouts=1),
                _row(pp_shots=15, pp_time_seconds_total=600, pp_time_seconds_in_oz=300,
                     pk_opp_breakouts=3)]
        r = special_teams_v2(rows)
        assert r["pp_shots_per_min"] == pytest.approx(25 / 15.0)
        assert r["pp_oz_ratio"] == pytest.approx(480 / 900)
        assert r["pk_opp_breakout_rate"] == pytest.approx(4 / 2)
        assert r["pp_minutes"] == pytest.approx(15.0)
        assert r["pk_count"] == 2
        assert r["games"] == 2

    def test_pp_time_zero_returns_none_rates(self):
        rows = [_row(pp_shots=None, pp_time_seconds_total=0, pp_time_seconds_in_oz=0)]
        r = special_teams_v2(rows)
        assert r["pp_shots_per_min"] is None
        assert r["pp_oz_ratio"] is None
        assert r["pp_minutes"] == 0.0
        assert r["games"] == 0  # no populated data, not counted

    def test_all_none_returns_none_rates(self):
        rows = [_row()]
        r = special_teams_v2(rows)
        assert r["pp_shots_per_min"] is None
        assert r["pp_oz_ratio"] is None
        assert r["pk_opp_breakout_rate"] is None
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_special_teams_v2.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement**

Append to `backend/app/tier2_stats.py`:

```python
def special_teams_v2(team_instat_rows: list) -> dict:
    """Team-level advanced special-teams stats (§9.3).

    - pp_shots_per_min: total PP shots ÷ total PP minutes
    - pp_oz_ratio: PP OZ seconds ÷ total PP seconds
    - pk_opp_breakout_rate: total opp breakouts allowed on PK ÷ games with PK data
    """
    total_pp_shots = 0
    total_pp_seconds = 0
    total_oz_pp_seconds = 0
    total_pk_breakouts = 0
    pk_count = 0
    games = 0

    for r in team_instat_rows:
        pp_secs = r.pp_time_seconds_total or 0
        oz_secs = r.pp_time_seconds_in_oz or 0
        pp_shots = r.pp_shots or 0
        pk_bk = r.pk_opp_breakouts

        has_data = pp_secs > 0 or pp_shots > 0 or pk_bk is not None
        if has_data:
            games += 1
        if pp_secs > 0:
            total_pp_seconds += pp_secs
            total_oz_pp_seconds += oz_secs
            total_pp_shots += pp_shots
        if pk_bk is not None:
            total_pk_breakouts += pk_bk
            pk_count += 1

    pp_minutes = total_pp_seconds / 60.0 if total_pp_seconds > 0 else (
        0.0 if any(r.pp_time_seconds_total is not None for r in team_instat_rows) else None
    )

    return {
        "pp_shots_per_min": (total_pp_shots / pp_minutes) if pp_minutes and pp_minutes > 0 else None,
        "pp_oz_ratio": (total_oz_pp_seconds / total_pp_seconds) if total_pp_seconds > 0 else None,
        "pk_opp_breakout_rate": (total_pk_breakouts / pk_count) if pk_count > 0 else None,
        "pp_minutes": pp_minutes,
        "pk_count": pk_count,
        "games": games,
    }
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_special_teams_v2.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tier2_stats.py backend/tests/test_special_teams_v2.py
git commit -m "feat: add special_teams_v2 team-level tier2 stat function"
```

---

### Task 6: `danger_zone_shot_share` (§9.6)

**Files:**
- Modify: `backend/app/tier2_stats.py`
- Create: `backend/tests/test_danger_zone_share.py`

**Interfaces:**
- Consumes: `PlayerGameStatsInStat` rows (for player's SCA shots) + `TeamGameStatsInStat` rows (for team totals) + `pgs_rows` (PlayerGameStats — for TOI in minutes).
- Produces:
  - `danger_zone_shot_share(instat_rows, team_instat_rows, pgs_rows) -> dict` — returns `{"share_pct": float|None, "shots_per_60": float|None, "player_sca_shots": int, "team_sca_shots": int, "games": int}`.
  - `share_pct` = player's InStat `scoring_chance_shots` sum (via a fallback lookup — see below) ÷ team's `TeamGameStatsInStat.scoring_chance_shots` sum. If team total is 0, None. **Note:** `PlayerGameStatsInStat` currently has no direct `scoring_chance_shots` column (Task 6 in Phase 4 will add InStat's shots-log parsing). For Phase 3, we use `PlayerGameStatsInStat.shots` as a proxy for the numerator ONLY when the model doesn't have SCA shots — this is imperfect but the best available. The report should mark this stat with a clear caveat until Phase 4 fills in true SCA shots.

Given the caveat, the compute function accepts a `player_sca_getter` callable so the caller can inject the source. For Phase 3 default, use `getattr(row, "scoring_chance_shots", None) or row.shots`.

- `shots_per_60` = player's SCA shots × 60 ÷ TOI in minutes (across the window).

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_danger_zone_share.py`:
```python
import pytest
from app.tier2_stats import danger_zone_shot_share
from app.models import PlayerGameStatsInStat, TeamGameStatsInStat, PlayerGameStats


def _instat(shots=None):
    r = PlayerGameStatsInStat(game_id=1, player_id=1)
    r.shots = shots
    return r


def _team(scoring_chance_shots=None):
    r = TeamGameStatsInStat(game_id=1)
    r.scoring_chance_shots = scoring_chance_shots
    return r


def _pgs(toi_5v5=None):
    r = PlayerGameStats(game_id=1, player_id=1)
    r.toi_5v5 = toi_5v5
    return r


class TestDangerZoneShotShare:
    def test_empty(self):
        r = danger_zone_shot_share([], [], [])
        assert r == {
            "share_pct": None, "shots_per_60": None,
            "player_sca_shots": 0, "team_sca_shots": 0, "games": 0,
        }

    def test_basic_share(self):
        instat = [_instat(shots=4), _instat(shots=6)]
        team = [_team(scoring_chance_shots=20), _team(scoring_chance_shots=25)]
        pgs = [_pgs(toi_5v5=15.0), _pgs(toi_5v5=18.0)]
        r = danger_zone_shot_share(instat, team, pgs)
        assert r["player_sca_shots"] == 10
        assert r["team_sca_shots"] == 45
        assert r["share_pct"] == pytest.approx(10 / 45)
        assert r["shots_per_60"] == pytest.approx(10 * 60 / 33.0)
        assert r["games"] == 2

    def test_zero_team_sca_returns_none_share(self):
        instat = [_instat(shots=3)]
        team = [_team(scoring_chance_shots=0)]
        pgs = [_pgs(toi_5v5=10.0)]
        r = danger_zone_shot_share(instat, team, pgs)
        assert r["share_pct"] is None
        assert r["shots_per_60"] == pytest.approx(3 * 60 / 10.0)

    def test_zero_toi_returns_none_per_60(self):
        instat = [_instat(shots=3)]
        team = [_team(scoring_chance_shots=10)]
        pgs = []
        r = danger_zone_shot_share(instat, team, pgs)
        assert r["share_pct"] == pytest.approx(3 / 10)
        assert r["shots_per_60"] is None

    def test_none_shots_treated_as_zero(self):
        instat = [_instat(shots=None), _instat(shots=5)]
        team = [_team(scoring_chance_shots=10)]
        pgs = [_pgs(toi_5v5=10.0)]
        r = danger_zone_shot_share(instat, team, pgs)
        assert r["player_sca_shots"] == 5
        assert r["team_sca_shots"] == 10
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_danger_zone_share.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement**

Append to `backend/app/tier2_stats.py`:

```python
def danger_zone_shot_share(
    instat_rows: list,
    team_instat_rows: list,
    pgs_rows: list,
) -> dict:
    """Player's share of team's high-danger shots + per-60 rate (§9.6).

    Numerator: sum of player's SCA shots (or `shots` as a proxy until Phase 4
    adds true per-player scoring-chance shot tracking).
    Denominator: sum of team's scoring_chance_shots across the same games.
    """
    player_sca = 0
    games_with_data = 0
    for r in instat_rows:
        sca = getattr(r, "scoring_chance_shots", None)
        val = sca if sca is not None else (r.shots or 0)
        if val > 0:
            games_with_data += 1
        player_sca += val

    team_sca = sum((t.scoring_chance_shots or 0) for t in team_instat_rows)
    total_toi = sum((p.toi_5v5 or 0) for p in pgs_rows)

    return {
        "share_pct": (player_sca / team_sca) if team_sca > 0 else None,
        "shots_per_60": (player_sca * 60.0 / total_toi) if total_toi > 0 else None,
        "player_sca_shots": player_sca,
        "team_sca_shots": team_sca,
        "games": games_with_data,
    }
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_danger_zone_share.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tier2_stats.py backend/tests/test_danger_zone_share.py
git commit -m "feat: add danger_zone_shot_share tier2 stat function"
```

---

### Task 7: `impact_score` (§9.1) — composite z-score stat

**Files:**
- Modify: `backend/app/tier2_stats.py`
- Create: `backend/tests/test_impact_score.py`

**Interfaces:**
- Consumes:
  - `PlayerGameStats` rows (for xGF60, xGA60, cf60, ca60 per game) — 49ing components.
  - `PlayerGameStatsInStat` rows keyed by game_id (for puck_battle_W%, controlled_entry_%) — InStat components.
  - `Player` object (for `position` to select cohort).
  - `position_cohorts: dict[str, list[float]]` — per-position distribution of each stat, used for z-score reference. Passed in by caller.
- Produces:
  - `impact_score(player, pgs_rows, instat_rows_by_game, position_cohorts) -> dict` — returns `{"score": float|None, "games": int, "components_used": list[str], "clamped": bool, "per_game": list[dict]}`.
  - `score`: TOI-weighted mean of per-game Impact scores, clamped to `[-3, +3]`. `clamped` is True when clamping actually changed the value.
  - `per_game`: list of `{"game_id": int, "impact": float, "components": {name: z}, "toi_5v5": float}` for callers who want the trend.
  - Games with `toi_5v5 < 5` excluded per spec.
  - Cohort z-score: `(value - mean) / stddev`. If cohort has fewer than 3 values or stddev == 0, that component is skipped for that game.

**Position cohort mapping (from spec §9.1):**
- `z_xg`: `on_ice_xGF60 - xGA60` (per-game diff). Cohort of same position's `xgf60 - xga60` values across the season.
- `z_terr`: `on_ice_CF%` computed as `cf60 / (cf60 + ca60)`. Cohort of same-position CF%.
- `z_battle` (InStat only): puck_battle_W% = sum(pb_won_*) / sum(pb_total_*) for that game.
- `z_entry` (InStat only, F/W only): `(entries_pass + entries_stick) / total_entries` for that game.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_impact_score.py`:
```python
import pytest
from app.tier2_stats import impact_score
from app.models import Player, PlayerGameStats, PlayerGameStatsInStat


def _pgs(game_id, toi_5v5=15.0, xgf60=2.5, xga60=2.0, cf60=50.0, ca60=45.0):
    r = PlayerGameStats(game_id=game_id, player_id=1)
    r.toi_5v5 = toi_5v5
    r.xgf60 = xgf60
    r.xga60 = xga60
    r.cf60 = cf60
    r.ca60 = ca60
    return r


def _instat(game_id, pb_w=3, pb_t=5, e_pass=2, e_stick=3, e_dump=1):
    r = PlayerGameStatsInStat(game_id=game_id, player_id=1)
    r.pb_won_dz = pb_w
    r.pb_total_dz = pb_t
    r.pb_won_oz = 0
    r.pb_total_oz = 0
    r.pb_won_nz = 0
    r.pb_total_nz = 0
    r.entries_pass = e_pass
    r.entries_stick = e_stick
    r.entries_dump = e_dump
    return r


COHORTS = {
    "F": {
        "xg_diff": [0.0, 0.5, -0.3, 0.2, -0.1, 0.4],
        "cf_pct": [0.5, 0.55, 0.48, 0.52, 0.51, 0.49],
        "battle_w_pct": [0.5, 0.55, 0.6, 0.48, 0.52, 0.53],
        "controlled_entry_pct": [0.6, 0.7, 0.55, 0.65, 0.58, 0.62],
    },
    "D": {"xg_diff": [], "cf_pct": [], "battle_w_pct": [], "controlled_entry_pct": []},
}


class TestImpactScore:
    def _player(self, position="F"):
        p = Player(name="X", number="1", position=position, is_center=False, active=True)
        p.id = 1
        return p

    def test_empty(self):
        p = self._player()
        r = impact_score(p, [], {}, COHORTS)
        assert r == {
            "score": None, "games": 0, "components_used": [],
            "clamped": False, "per_game": [],
        }

    def test_single_game_all_components(self):
        p = self._player()
        pgs = [_pgs(game_id=1)]
        instat = {1: _instat(game_id=1)}
        r = impact_score(p, pgs, instat, COHORTS)
        assert r["score"] is not None
        assert r["games"] == 1
        assert set(r["components_used"]) <= {"z_xg", "z_terr", "z_battle", "z_entry"}
        assert len(r["per_game"]) == 1

    def test_short_toi_game_excluded(self):
        p = self._player()
        pgs = [_pgs(game_id=1, toi_5v5=3.0), _pgs(game_id=2, toi_5v5=20.0)]
        instat = {1: _instat(game_id=1), 2: _instat(game_id=2)}
        r = impact_score(p, pgs, instat, COHORTS)
        # Only game 2 counts
        assert r["games"] == 1

    def test_missing_instat_drops_components(self):
        p = self._player()
        pgs = [_pgs(game_id=1)]
        r = impact_score(p, pgs, {}, COHORTS)
        assert r["games"] == 1
        assert "z_battle" not in r["per_game"][0]["components"]
        assert "z_entry" not in r["per_game"][0]["components"]

    def test_defender_no_entry_component(self):
        p = self._player(position="D")
        pgs = [_pgs(game_id=1)]
        instat = {1: _instat(game_id=1)}
        # D position: z_entry not applicable (spec §9.1: F/W only)
        r = impact_score(p, pgs, instat, COHORTS)
        # z_xg/z_terr should attempt cohort lookup ("D" cohort is empty in fixture)
        # so those components skip. z_battle uses "D" cohort which is empty too.
        # Result should be None (no valid components).
        assert r["games"] == 1
        assert all("z_entry" not in g["components"] for g in r["per_game"])

    def test_clamping(self):
        # Construct a scenario where raw mean would exceed +3
        p = self._player()
        # Player performs 5σ above cohort in all components
        strong_cohort = {
            "F": {
                "xg_diff": [0.0] * 10,  # stddev = 0 → skip
                "cf_pct": [0.5] * 5 + [0.51],  # near-zero stddev
                "battle_w_pct": [0.5] * 5 + [0.51],
                "controlled_entry_pct": [0.5] * 5 + [0.51],
            },
        }
        pgs = [_pgs(game_id=1, xgf60=100, xga60=0, cf60=100, ca60=0)]
        instat = {1: _instat(game_id=1, pb_w=100, pb_t=100, e_pass=100, e_stick=0, e_dump=0)}
        r = impact_score(p, pgs, instat, strong_cohort)
        if r["score"] is not None:
            assert -3.0 <= r["score"] <= 3.0
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_impact_score.py -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement**

Append to `backend/app/tier2_stats.py`:

```python
from statistics import mean, pstdev


def _z_score(value: float, cohort: list) -> Optional[float]:
    """Return z-score for value against cohort. None if cohort < 3 or stddev == 0."""
    if len(cohort) < 3:
        return None
    m = mean(cohort)
    s = pstdev(cohort)
    if s == 0:
        return None
    return (value - m) / s


def impact_score(
    player,
    pgs_rows: list,
    instat_rows_by_game: dict,
    position_cohorts: dict,
) -> dict:
    """Composite per-game Impact score, TOI-weighted season aggregate (§9.1).

    Per-game score = mean(available z-scores) across up to 4 components:
      z_xg: (xgf60 - xga60) vs cohort xg_diff
      z_terr: cf60/(cf60+ca60) vs cohort cf_pct
      z_battle: puck-battle W% vs cohort battle_w_pct (InStat only)
      z_entry: controlled-entry % vs cohort controlled_entry_pct (InStat only, F/W)

    Season score = TOI-weighted mean of per-game scores, clamped to [-3, +3].

    Games with toi_5v5 < 5 are excluded.
    """
    position = getattr(player, "position", "") or ""
    cohort = position_cohorts.get(position, {})
    is_forward = position in ("F", "W", "C")

    per_game: list[dict] = []
    weighted_sum = 0.0
    weight_total = 0.0
    components_used_set: set = set()

    for pgs in pgs_rows:
        toi = pgs.toi_5v5 or 0
        if toi < 5:
            continue

        components: dict[str, float] = {}

        # z_xg: (xgf60 - xga60) vs cohort xg_diff
        if pgs.xgf60 is not None and pgs.xga60 is not None:
            z = _z_score(pgs.xgf60 - pgs.xga60, cohort.get("xg_diff", []))
            if z is not None:
                components["z_xg"] = z

        # z_terr: on-ice CF% vs cohort cf_pct
        cf = pgs.cf60 or 0
        ca = pgs.ca60 or 0
        if (cf + ca) > 0:
            cf_pct = cf / (cf + ca)
            z = _z_score(cf_pct, cohort.get("cf_pct", []))
            if z is not None:
                components["z_terr"] = z

        # InStat components
        instat = instat_rows_by_game.get(pgs.game_id)
        if instat is not None:
            # z_battle
            pb_won = (instat.pb_won_dz or 0) + (instat.pb_won_oz or 0) + (instat.pb_won_nz or 0)
            pb_tot = (instat.pb_total_dz or 0) + (instat.pb_total_oz or 0) + (instat.pb_total_nz or 0)
            if pb_tot > 0:
                z = _z_score(pb_won / pb_tot, cohort.get("battle_w_pct", []))
                if z is not None:
                    components["z_battle"] = z

            # z_entry (F/W only)
            if is_forward:
                p_e = instat.entries_pass or 0
                s_e = instat.entries_stick or 0
                d_e = instat.entries_dump or 0
                tot_e = p_e + s_e + d_e
                if tot_e > 0:
                    controlled = (p_e + s_e) / tot_e
                    z = _z_score(controlled, cohort.get("controlled_entry_pct", []))
                    if z is not None:
                        components["z_entry"] = z

        if not components:
            # No valid components this game — still record the game so
            # caller can see why score is missing
            per_game.append({
                "game_id": pgs.game_id,
                "impact": None,
                "components": {},
                "toi_5v5": toi,
            })
            continue

        components_used_set.update(components.keys())
        impact = sum(components.values()) / len(components)
        per_game.append({
            "game_id": pgs.game_id,
            "impact": impact,
            "components": components,
            "toi_5v5": toi,
        })
        weighted_sum += impact * toi
        weight_total += toi

    if weight_total == 0:
        return {
            "score": None,
            "games": len(per_game),
            "components_used": sorted(components_used_set),
            "clamped": False,
            "per_game": per_game,
        }

    raw = weighted_sum / weight_total
    clamped_val = max(-3.0, min(3.0, raw))
    return {
        "score": clamped_val,
        "games": len(per_game),
        "components_used": sorted(components_used_set),
        "clamped": clamped_val != raw,
        "per_game": per_game,
    }
```

- [ ] **Step 4: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_impact_score.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tier2_stats.py backend/tests/test_impact_score.py
git commit -m "feat: add impact_score composite tier2 stat function"
```

---

### Task 8: Extend `enrich_player_agg` to attach Tier 2 stats

**Files:**
- Modify: `backend/app/enrichment.py`
- Modify: `backend/app/routers/stats.py` (pass InStat rows into enrich)
- Modify: `backend/app/routers/reports.py` (same)
- Create: `backend/tests/test_enrich_tier2.py`

**Interfaces:**
- Consumes: all Tier 2 stat functions from `app.tier2_stats`; loaders from `app.enrichment`; existing cohort infrastructure from `app.cohorts`.
- Produces:
  - Extended `enrich_player_agg(player, agg, all_aggs, *, instat_rows=None, team_instat_rows=None, pgs_rows=None, position_cohorts=None)` — new keyword-only args default to empty/None.
  - When InStat rows are provided, `agg` gains keys: `contested_puck`, `zone_entry`, `turnover_ratio`, `danger_share`, `impact_score`. Each is the dict returned by its computation function.
  - Existing behavior (comparisons/flags/game_flags) unchanged when new params omitted.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_enrich_tier2.py`:
```python
import pytest
from datetime import date
from app.models import (
    Player, Game, PlayerGameStats, PlayerGameStatsInStat, TeamGameStatsInStat,
)
from app.enrichment import enrich_player_agg


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
    for g in [g1, g2]:
        pgs = PlayerGameStats(
            player_id=p.id, game_id=g.id,
            toi_5v5=15.0, xgf60=2.5, xga60=2.0, cf60=50, ca60=40,
            ff60=40, fa60=35, sf60=30, sa60=25,
        )
        db_session.add(pgs)
        pgs_rows.append(pgs)

    instat_rows = []
    team_rows = []
    for g in [g1, g2]:
        ir = PlayerGameStatsInStat(
            player_id=p.id, game_id=g.id,
            shots=5, pb_won_dz=3, pb_total_dz=5,
            entries_pass=2, entries_stick=3, entries_dump=1,
            puck_losses=6, puck_losses_dz=2, puck_recoveries=8, puck_recoveries_oz=3,
        )
        tr = TeamGameStatsInStat(
            game_id=g.id, pp_shots=12, pp_time_seconds_total=600,
            pp_time_seconds_in_oz=360, pk_opp_breakouts=2,
            scoring_chance_shots=25,
        )
        db_session.add_all([ir, tr])
        instat_rows.append(ir)
        team_rows.append(tr)
    db_session.commit()

    agg = {
        "player_id": p.id, "player_name": p.name,
        "games_played": 2, "small_sample": False,
        "toi_5v5": 15.0, "trend": [],
        # ... other fields will be filled with test values as needed
    }
    return p, agg, pgs_rows, instat_rows, team_rows


class TestEnrichTier2:
    def test_no_instat_rows_preserves_existing_behavior(self, enriched_setup):
        p, agg, _, _, _ = enriched_setup
        result = enrich_player_agg(p, agg, [(p, agg)])
        assert "flags" in result
        assert "comparisons" in result
        assert "contested_puck" not in result

    def test_with_instat_attaches_tier2_stats(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows = enriched_setup
        cohorts = {"F": {
            "xg_diff": [0.0, 0.3, -0.2, 0.4, 0.1],
            "cf_pct": [0.5, 0.52, 0.48, 0.55, 0.51],
            "battle_w_pct": [0.5, 0.55, 0.48, 0.52, 0.53],
            "controlled_entry_pct": [0.6, 0.65, 0.7, 0.55, 0.58],
        }}
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts=cohorts,
        )
        for k in ("contested_puck", "zone_entry", "turnover_ratio",
                  "danger_share", "impact_score"):
            assert k in result, f"missing {k}"

    def test_contested_puck_shape(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows = enriched_setup
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts={},
        )
        cp = result["contested_puck"]
        assert cp["overall_pct"] == pytest.approx(6 / 10)
        assert cp["games"] == 2

    def test_impact_score_null_with_empty_cohorts(self, enriched_setup):
        p, agg, pgs_rows, instat_rows, team_rows = enriched_setup
        result = enrich_player_agg(
            p, agg, [(p, agg)],
            instat_rows=instat_rows,
            team_instat_rows=team_rows,
            pgs_rows=pgs_rows,
            position_cohorts={},
        )
        assert result["impact_score"]["score"] is None
```

- [ ] **Step 2: Verify tests fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_enrich_tier2.py -v`
Expected: fails — enrich_player_agg doesn't accept new kwargs.

- [ ] **Step 3: Extend enrich_player_agg**

Modify `backend/app/enrichment.py` — replace the `enrich_player_agg` function:

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
) -> dict:
    """Attach comparisons/flags/game_flags (Phase 1) and Tier 2 stats
    (Phase 3) to a player aggregate in-place. Returns the same dict.

    Phase 1 layers always run. Tier 2 layers run only when InStat rows are
    provided — passing None (or omitting) preserves pre-Phase-3 behavior.
    """
    agg["comparisons"] = build_comparisons(player, agg, all_aggs)

    trend = agg.get("trend", [])
    rolling = [evaluate_rule(r, trend) for r in DEFAULT_FLAG_RULES]
    rolling = [f for f in rolling if f is not None]
    toi_f = evaluate_toi_trend(trend)
    if toi_f is not None:
        rolling.append(toi_f)
    agg["flags"] = [asdict(f) for f in top_flags(rolling, n=3)]

    game_flags: dict[int, list] = {}
    for f in evaluate_toi_outliers(trend):
        if f.game_id is None:
            continue
        game_flags.setdefault(f.game_id, []).append(asdict(f))
    agg["game_flags"] = game_flags

    # Phase 3: Tier 2 stats
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
        )
        instat_by_game = {r.game_id: r for r in instat_rows}
        agg["impact_score"] = impact_score(
            player, pgs_rows or [], instat_by_game, position_cohorts or {},
        )

    return agg
```

- [ ] **Step 4: Update stats.py router to pass InStat rows and cohorts**

Read `backend/app/routers/stats.py` first. Find the player-agg endpoint (`/api/stats/player/{player_id}`). It currently:
1. Loads player + games + PlayerGameStats in the date window.
2. Calls `aggregate_player_stats(...)`.
3. Calls `enrich_player_agg(player, agg, all_aggs)`.

Extend the endpoint to:
1. After loading `pgs_rows`, also load `instat_rows = load_player_instat_rows(db, player.id, date_from, date_to)` and `team_rows = load_team_instat_rows(db, date_from, date_to)`.
2. Build position cohorts. Use existing `app.cohorts.cohort_baseline` — call it once per position across the full window:
   ```python
   from .cohorts import position_group, cohort_matches, cohort_baseline
   # Build cohort distributions per position for each Impact Score stat
   all_players = db.query(Player).filter_by(active=True).all()
   # Position → { stat_key: list[values] }
   position_cohorts = _build_position_cohorts(all_players, db, date_from, date_to)
   ```
3. Pass all four kwargs (`instat_rows`, `team_instat_rows`, `pgs_rows`, `position_cohorts`) to `enrich_player_agg`.

The `_build_position_cohorts` helper is a router-local function that builds the cohort distributions. Add it in stats.py:

```python
def _build_position_cohorts(all_players, db, date_from, date_to) -> dict:
    """Build per-position stat distributions for Impact Score z-scoring."""
    from .cohorts import position_group
    from .enrichment import load_player_instat_rows
    cohorts: dict[str, dict[str, list]] = {}
    for p in all_players:
        pos = position_group(p)
        if pos not in cohorts:
            cohorts[pos] = {"xg_diff": [], "cf_pct": [], "battle_w_pct": [], "controlled_entry_pct": []}
        pgs = db.query(PlayerGameStats).join(Game).filter(
            PlayerGameStats.player_id == p.id
        )
        if date_from:
            pgs = pgs.filter(Game.date >= date_from)
        if date_to:
            pgs = pgs.filter(Game.date <= date_to)
        for r in pgs.all():
            if r.toi_5v5 and r.toi_5v5 >= 5:
                if r.xgf60 is not None and r.xga60 is not None:
                    cohorts[pos]["xg_diff"].append(r.xgf60 - r.xga60)
                cf, ca = r.cf60 or 0, r.ca60 or 0
                if (cf + ca) > 0:
                    cohorts[pos]["cf_pct"].append(cf / (cf + ca))
        for ir in load_player_instat_rows(db, p.id, date_from, date_to):
            pb_w = (ir.pb_won_dz or 0) + (ir.pb_won_oz or 0) + (ir.pb_won_nz or 0)
            pb_t = (ir.pb_total_dz or 0) + (ir.pb_total_oz or 0) + (ir.pb_total_nz or 0)
            if pb_t > 0:
                cohorts[pos]["battle_w_pct"].append(pb_w / pb_t)
            p_e = ir.entries_pass or 0
            s_e = ir.entries_stick or 0
            d_e = ir.entries_dump or 0
            tot_e = p_e + s_e + d_e
            if tot_e > 0:
                cohorts[pos]["controlled_entry_pct"].append((p_e + s_e) / tot_e)
    return cohorts
```

Then in the player-agg endpoint, before calling `enrich_player_agg`:
```python
from .enrichment import load_player_instat_rows, load_team_instat_rows

instat_rows = load_player_instat_rows(db, player.id, date_from, date_to)
team_rows = load_team_instat_rows(db, date_from, date_to)
all_players = db.query(Player).filter_by(active=True).all()
position_cohorts = _build_position_cohorts(all_players, db, date_from, date_to)

enriched = enrich_player_agg(
    player, agg, all_aggs,
    instat_rows=instat_rows,
    team_instat_rows=team_rows,
    pgs_rows=pgs_rows,
    position_cohorts=position_cohorts,
)
```

- [ ] **Step 5: Update reports.py router similarly**

Read `backend/app/routers/reports.py`. Find the player report endpoint and make the same extension: load InStat rows, build cohorts, pass to enrich_player_agg.

Refactor `_build_position_cohorts` to a shared helper — move it to `enrichment.py`:

```python
# In enrichment.py:
def build_position_cohorts(all_players, db, date_from=None, date_to=None) -> dict:
    """Build per-position stat distributions for Impact Score z-scoring.

    Used by both stats and reports routers so cohort computation stays
    consistent."""
    # ... (paste the function body from Step 4)
```

Then both stats.py and reports.py import from enrichment.

- [ ] **Step 6: Verify tests pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_enrich_tier2.py -v`
Expected: 4 tests pass.

Full suite (fast slice): `backend/venv/bin/python -m pytest backend/tests/ --ignore=backend/tests/test_ingest_router.py --ignore=backend/tests/test_ingest_end_to_end.py --ignore=backend/tests/test_orchestrator.py -q`
Expected: all pass, no regressions.

- [ ] **Step 7: Commit**

```bash
git add backend/app/enrichment.py backend/app/routers/stats.py backend/app/routers/reports.py backend/tests/test_enrich_tier2.py
git commit -m "feat: enrich player agg with tier2 stats + wire routers"
```

---

### Task 9: Extend team aggregate with Special Teams v2

**Files:**
- Modify: `backend/app/routers/stats.py` (team-agg endpoint)
- Create: `backend/tests/test_team_agg_st_v2.py`

**Interfaces:**
- Consumes: `special_teams_v2` from `app.tier2_stats`; `load_team_instat_rows` from `app.enrichment`.
- Produces:
  - Team agg response (`/api/stats/team`) gains a `special_teams_v2` key with the dict from `special_teams_v2()`.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_team_agg_st_v2.py`:
```python
import pytest
from datetime import date
from fastapi.testclient import TestClient
import sys, types
sys.modules["weasyprint"] = sys.modules.get("weasyprint") or types.ModuleType("weasyprint")
sys.modules["weasyprint"].HTML = lambda *a, **k: None  # type: ignore

from app.main import app
from app.database import get_db
from app.models import Game, TeamGameStats, TeamGameStatsInStat


def test_team_agg_includes_special_teams_v2(db_session, monkeypatch):
    # Seed one game with team stats + team instat
    g = Game(date=date(2025, 10, 1), opponent="X", is_home=True,
             season="2025-26", data_source="instat")
    db_session.add(g)
    db_session.commit()
    db_session.add(TeamGameStats(
        game_id=g.id, cf_for_5v5=60, cf_against_5v5=40,
        xgf_5v5=2.5, xga_5v5=2.0,
        total_game_time=60, toi_pp=5, toi_pk=5, other_toi=0,
    ))
    db_session.add(TeamGameStatsInStat(
        game_id=g.id, pp_shots=12, pp_time_seconds_total=600,
        pp_time_seconds_in_oz=360, pk_opp_breakouts=2,
    ))
    db_session.commit()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        resp = client.get("/api/stats/team")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert "special_teams_v2" in body
    st = body["special_teams_v2"]
    assert st["pp_shots_per_min"] == pytest.approx(12 / 10.0)
    assert st["pp_oz_ratio"] == pytest.approx(0.6)
    assert st["games"] == 1
```

- [ ] **Step 2: Verify test fails**

Run: `backend/venv/bin/python -m pytest backend/tests/test_team_agg_st_v2.py -v`
Expected: assertion fails on `"special_teams_v2" in body`.

- [ ] **Step 3: Extend the team-agg endpoint**

Read `backend/app/routers/stats.py`. Find the `/team` endpoint. After it computes the base team aggregate, add:

```python
from .enrichment import load_team_instat_rows
from .tier2_stats import special_teams_v2

team_instat = load_team_instat_rows(db, date_from, date_to)
result["special_teams_v2"] = special_teams_v2(team_instat)
```

Where `result` is the dict returned by `aggregate_team_stats`.

- [ ] **Step 4: Verify test passes**

Run: `backend/venv/bin/python -m pytest backend/tests/test_team_agg_st_v2.py -v`
Expected: 1 test passes.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/stats.py backend/tests/test_team_agg_st_v2.py
git commit -m "feat: attach special_teams_v2 to team aggregate response"
```

---

### Task 10: Frontend types for Tier 2 stats

**Files:**
- Modify: `frontend/src/types.ts`

**Interfaces:**
- Consumes: nothing (pure type additions).
- Produces:
  - Interfaces: `ContestedPuckStats`, `ZoneEntryStats`, `TurnoverRatioStats`, `DangerShareStats`, `ImpactScoreStats`, `SpecialTeamsV2Stats`.
  - Extends `PlayerAggStats` with optional `contested_puck`, `zone_entry`, `turnover_ratio`, `danger_share`, `impact_score` fields.
  - Extends `TeamAggStats` with optional `special_teams_v2` field.

- [ ] **Step 1: Add interfaces**

Append to `frontend/src/types.ts`:
```typescript
export interface ContestedPuckStats {
  overall_pct: number | null
  dz_pct: number | null
  oz_pct: number | null
  nz_pct: number | null
  games: number
}

export interface ZoneEntryStats {
  pass_pct: number | null
  stick_pct: number | null
  dump_pct: number | null
  total_entries: number
  games: number
}

export interface TurnoverRatioStats {
  dz_loss_share: number | null
  oz_recovery_share: number | null
  total_losses: number
  total_recoveries: number
  games: number
}

export interface DangerShareStats {
  share_pct: number | null
  shots_per_60: number | null
  player_sca_shots: number
  team_sca_shots: number
  games: number
}

export interface ImpactScoreComponent {
  z_xg?: number
  z_terr?: number
  z_battle?: number
  z_entry?: number
}

export interface ImpactScorePerGame {
  game_id: number
  impact: number | null
  components: ImpactScoreComponent
  toi_5v5: number
}

export interface ImpactScoreStats {
  score: number | null
  games: number
  components_used: string[]
  clamped: boolean
  per_game: ImpactScorePerGame[]
}

export interface SpecialTeamsV2Stats {
  pp_shots_per_min: number | null
  pp_oz_ratio: number | null
  pk_opp_breakout_rate: number | null
  pp_minutes: number | null
  pk_count: number
  games: number
}
```

- [ ] **Step 2: Extend `PlayerAggStats`**

Find the existing `PlayerAggStats` interface in `types.ts`. Add these optional fields:
```typescript
  contested_puck?: ContestedPuckStats
  zone_entry?: ZoneEntryStats
  turnover_ratio?: TurnoverRatioStats
  danger_share?: DangerShareStats
  impact_score?: ImpactScoreStats
```

- [ ] **Step 3: Extend `TeamAggStats`**

Find `TeamAggStats`. Add:
```typescript
  special_teams_v2?: SpecialTeamsV2Stats
```

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat: add tier2 stat type interfaces"
```

---

### Task 11: `PuckBattleBlock` component

**Files:**
- Create: `frontend/src/components/PuckBattleBlock.tsx`

**Interfaces:**
- Consumes: `ContestedPuckStats` type.
- Produces:
  - Component: `PuckBattleBlock({ data }: { data?: ContestedPuckStats })` — renders four sub-cards (Overall, DZ, OZ, NZ) with percentages. Null values render as "N/A". Wrapped in a labeled section.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/PuckBattleBlock.tsx`:
```tsx
import type { ContestedPuckStats } from '../types'


function fmtPct(v: number | null): string {
  if (v === null) return 'N/A'
  return `${(v * 100).toFixed(1)}%`
}


export default function PuckBattleBlock({ data }: { data?: ContestedPuckStats }) {
  if (!data || data.games === 0) return null
  const cells = [
    { label: 'Overall', val: data.overall_pct },
    { label: 'DZ', val: data.dz_pct },
    { label: 'OZ', val: data.oz_pct },
    { label: 'NZ', val: data.nz_pct },
  ]
  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
        Puck Battles ({data.games} game{data.games !== 1 ? 's' : ''})
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {cells.map(c => (
          <div key={c.label} style={{
            padding: 12,
            border: '1px solid var(--border, #333)',
            borderRadius: 4,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
              {c.label}
            </div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>
              {fmtPct(c.val)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PuckBattleBlock.tsx
git commit -m "feat: add PuckBattleBlock component for tier2 puck battle stats"
```

---

### Task 12: `EntryCompositionBar` component

**Files:**
- Create: `frontend/src/components/EntryCompositionBar.tsx`

**Interfaces:**
- Consumes: `ZoneEntryStats` type.
- Produces:
  - Component: `EntryCompositionBar({ data }: { data?: ZoneEntryStats })` — renders a horizontal stacked bar showing pass/stick/dump percentages with a legend. Returns null when data is missing or `total_entries === 0`.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/EntryCompositionBar.tsx`:
```tsx
import type { ZoneEntryStats } from '../types'


const COLORS = {
  pass: '#4a9eff',
  stick: '#f5a742',
  dump: '#8a8a9a',
}


export default function EntryCompositionBar({ data }: { data?: ZoneEntryStats }) {
  if (!data || data.total_entries === 0) return null
  const p = (data.pass_pct ?? 0) * 100
  const s = (data.stick_pct ?? 0) * 100
  const d = (data.dump_pct ?? 0) * 100
  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
        Zone Entry Composition ({data.total_entries} entries · {data.games} game{data.games !== 1 ? 's' : ''})
      </h3>
      <div style={{ display: 'flex', height: 32, borderRadius: 4, overflow: 'hidden', border: '1px solid var(--border, #333)' }}>
        <div style={{ width: `${p}%`, background: COLORS.pass, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 12 }}>
          {p >= 8 && `${p.toFixed(0)}%`}
        </div>
        <div style={{ width: `${s}%`, background: COLORS.stick, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 12 }}>
          {s >= 8 && `${s.toFixed(0)}%`}
        </div>
        <div style={{ width: `${d}%`, background: COLORS.dump, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 12 }}>
          {d >= 8 && `${d.toFixed(0)}%`}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 12 }}>
        <span><span style={{ display: 'inline-block', width: 12, height: 12, background: COLORS.pass, marginRight: 4, verticalAlign: 'middle' }} />Pass</span>
        <span><span style={{ display: 'inline-block', width: 12, height: 12, background: COLORS.stick, marginRight: 4, verticalAlign: 'middle' }} />Stick</span>
        <span><span style={{ display: 'inline-block', width: 12, height: 12, background: COLORS.dump, marginRight: 4, verticalAlign: 'middle' }} />Dump</span>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EntryCompositionBar.tsx
git commit -m "feat: add EntryCompositionBar stacked-bar component"
```

---

### Task 13: `ImpactScoreCard` component

**Files:**
- Create: `frontend/src/components/ImpactScoreCard.tsx`

**Interfaces:**
- Consumes: `ImpactScoreStats` type.
- Produces:
  - Component: `ImpactScoreCard({ data }: { data?: ImpactScoreStats })` — renders large score with color (+ green, - red) and a tooltip showing the component z-scores aggregated across per_game.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ImpactScoreCard.tsx`:
```tsx
import type { ImpactScoreStats } from '../types'


function scoreColor(score: number | null): string {
  if (score === null) return 'var(--text-secondary)'
  if (score >= 1) return 'var(--color-green, #4ecb71)'
  if (score >= 0) return 'var(--text-primary, #eaeaf0)'
  if (score >= -1) return 'var(--color-orange, #f5a742)'
  return 'var(--color-red, #d63030)'
}


function averageComponents(perGame: ImpactScoreStats['per_game']): Record<string, number | null> {
  const totals: Record<string, { sum: number; count: number }> = {}
  for (const g of perGame) {
    for (const [k, v] of Object.entries(g.components)) {
      if (typeof v !== 'number') continue
      const entry = totals[k] ?? { sum: 0, count: 0 }
      entry.sum += v
      entry.count += 1
      totals[k] = entry
    }
  }
  const out: Record<string, number | null> = {}
  for (const [k, { sum, count }] of Object.entries(totals)) {
    out[k] = count > 0 ? sum / count : null
  }
  return out
}


const LABELS: Record<string, string> = {
  z_xg: 'xG diff (on-ice)',
  z_terr: 'Territory (CF%)',
  z_battle: 'Puck battle W%',
  z_entry: 'Controlled entry %',
}


export default function ImpactScoreCard({ data }: { data?: ImpactScoreStats }) {
  if (!data) return null
  const scoreDisplay = data.score === null ? 'N/A' : data.score.toFixed(2)
  const componentAvgs = averageComponents(data.per_game)
  const tooltip = Object.entries(componentAvgs)
    .map(([k, v]) => `${LABELS[k] ?? k}: ${v === null ? 'N/A' : v.toFixed(2)}σ`)
    .join('\n')

  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
        Impact Score
      </h3>
      <div
        title={tooltip || 'No component data'}
        style={{
          padding: 24,
          border: '1px solid var(--border, #333)',
          borderRadius: 4,
          textAlign: 'center',
          cursor: tooltip ? 'help' : 'default',
        }}
      >
        <div style={{ fontSize: 40, fontWeight: 700, color: scoreColor(data.score) }}>
          {scoreDisplay}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
          {data.games} game{data.games !== 1 ? 's' : ''} · {data.components_used.length} component{data.components_used.length !== 1 ? 's' : ''}
          {data.clamped && ' · clamped'}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ImpactScoreCard.tsx
git commit -m "feat: add ImpactScoreCard component with component tooltip"
```

---

### Task 14: Wire Tier 2 stats into `ReportsPage.tsx`

**Files:**
- Modify: `frontend/src/pages/ReportsPage.tsx`

**Interfaces:**
- Consumes: `PuckBattleBlock`, `EntryCompositionBar`, `ImpactScoreCard` components; `StatCard` (existing).
- Produces:
  - Player report gains 5 new blocks: Contested Puck, Zone Entry, Turnover Ratio (2 StatCards), Danger Share (2 StatCards), Impact Score.
  - Team report gains 3 new StatCards: PP Shots/min, PP OZ Ratio, PK Opp-Breakout Rate.

- [ ] **Step 1: Extend player report section**

Read the current `frontend/src/pages/ReportsPage.tsx`. Find the section where player stats are rendered (search for `agg.flags` or `StatCard`). Add the new blocks below existing stats:

```tsx
import PuckBattleBlock from '../components/PuckBattleBlock'
import EntryCompositionBar from '../components/EntryCompositionBar'
import ImpactScoreCard from '../components/ImpactScoreCard'

// Inside the player-report render, after existing stat blocks:
<ImpactScoreCard data={agg.impact_score} />
<PuckBattleBlock data={agg.contested_puck} />
<EntryCompositionBar data={agg.zone_entry} />

{agg.turnover_ratio && agg.turnover_ratio.games > 0 && (
  <div style={{ marginTop: 16 }}>
    <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
      Turnover Location
    </h3>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
      <StatCard
        label="DZ Loss Share"
        primary={agg.turnover_ratio.dz_loss_share === null ? '—' : `${(agg.turnover_ratio.dz_loss_share * 100).toFixed(1)}%`}
      />
      <StatCard
        label="OZ Recovery Share"
        primary={agg.turnover_ratio.oz_recovery_share === null ? '—' : `${(agg.turnover_ratio.oz_recovery_share * 100).toFixed(1)}%`}
      />
    </div>
  </div>
)}

{agg.danger_share && agg.danger_share.games > 0 && (
  <div style={{ marginTop: 16 }}>
    <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
      Danger-Zone Shot Share
    </h3>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
      <StatCard
        label="Share of Team HD Shots"
        primary={agg.danger_share.share_pct === null ? '—' : `${(agg.danger_share.share_pct * 100).toFixed(1)}%`}
      />
      <StatCard
        label="HD Shots/60"
        primary={agg.danger_share.shots_per_60 === null ? '—' : agg.danger_share.shots_per_60.toFixed(2)}
      />
    </div>
  </div>
)}
```

Preserve existing StatCard, ComparisonRow, FlagPanel usage.

- [ ] **Step 2: Extend team report section**

Find where team stats render. Add:

```tsx
{teamAgg.special_teams_v2 && teamAgg.special_teams_v2.games > 0 && (
  <div style={{ marginTop: 16 }}>
    <h3 style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-secondary)' }}>
      Special Teams (Advanced)
    </h3>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
      <StatCard
        label="PP Shots/min"
        primary={teamAgg.special_teams_v2.pp_shots_per_min === null ? '—' : teamAgg.special_teams_v2.pp_shots_per_min.toFixed(2)}
      />
      <StatCard
        label="PP OZ Ratio"
        primary={teamAgg.special_teams_v2.pp_oz_ratio === null ? '—' : `${(teamAgg.special_teams_v2.pp_oz_ratio * 100).toFixed(1)}%`}
      />
      <StatCard
        label="PK Opp-Breakout Rate"
        primary={teamAgg.special_teams_v2.pk_opp_breakout_rate === null ? '—' : teamAgg.special_teams_v2.pk_opp_breakout_rate.toFixed(2)}
      />
    </div>
  </div>
)}
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ReportsPage.tsx
git commit -m "feat: render tier2 stat blocks on player and team reports"
```

---

### Task 15: Methodology page — remove "🚧 Coming Soon" pills

**Files:**
- Modify: `frontend/src/pages/MethodologyPage.tsx`

**Interfaces:**
- Consumes: nothing.
- Produces: 6 methodology entries lose their `status: 'planned'` marker.

Entries to un-plan (Tier 2 stats now shipped):
- "Special Teams (Advanced)" (~line 49)
- "Impact Score" (~line 102)
- "Contested Puck Win % (Overall / DZ / OZ / NZ)" (~line 118)
- "Zone Entry Composition (Pass / Stick / Dump %)" (~line 131)
- "Turnover Location Ratio (DZ Loss Share / OZ Recovery Share)" (~line 143)
- "Danger-Zone Shot Share" (~line 155)

Leave planned:
- Defensive Disruption Index (Phase 4 / Tier 3)
- Shot Threat by Scenario (Phase 4 / Tier 3)
- Goalie Stats (Phase 4 / Tier 3)
- Position-Aware Comparison, TOI Trend Flag, Auto-Flag Engine (already shipped in Phase 1 — but if their status is still 'planned', un-plan them too as a bonus cleanup; verify by reading the current file first)

- [ ] **Step 1: Read the current file**

Read `frontend/src/pages/MethodologyPage.tsx` in full. Find each of the 6 target entries by their `name:` field. Confirm they currently have `status: 'planned'`.

- [ ] **Step 2: Remove the `status: 'planned'` line from each of the 6 target entries**

Delete only the `status: 'planned',` line from each of the 6 entries. Leave `sourceNote:`, `limitations:`, `whyNotGoals:`, etc. intact.

For any Phase 1 entry (Position-Aware Comparison, TOI Trend Flag, Auto-Flag Engine) that still has `status: 'planned'`, remove it as well — those were already shipped in Phase 1.

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/MethodologyPage.tsx
git commit -m "chore: remove Coming Soon pills from tier2 stats now shipped in Phase 3"
```

---

### Task 16: End-to-end integration test

**Files:**
- Create: `backend/tests/test_tier2_end_to_end.py`

**Interfaces:**
- Consumes: `/api/stats/player/{id}` endpoint with seeded InStat + PlayerGameStats data.
- Produces: one test that verifies the enriched player agg contains all 5 Tier 2 stat blocks with expected shape.

- [ ] **Step 1: Write the test**

Create `backend/tests/test_tier2_end_to_end.py`:
```python
import sys, types
sys.modules["weasyprint"] = sys.modules.get("weasyprint") or types.ModuleType("weasyprint")
sys.modules["weasyprint"].HTML = lambda *a, **k: None  # type: ignore

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.models import (
    Player, Game, PlayerGameStats, PlayerGameStatsInStat, TeamGameStatsInStat,
)


@pytest.fixture
def seeded_full(db_session):
    # 3 forwards for a real cohort
    players = [
        Player(name=f"F{i}", number=str(i), position="F", is_center=False, active=True)
        for i in range(1, 4)
    ]
    for p in players:
        db_session.add(p)
    db_session.commit()

    # 5 InStat games
    games = []
    for i in range(5):
        g = Game(date=date(2025, 10, 1) + timedelta(days=i * 3),
                 opponent=f"O{i}", is_home=True, season="2025-26",
                 data_source="instat")
        db_session.add(g)
        games.append(g)
    db_session.commit()

    # Populate PGS + InStat + Team InStat for each game and each player
    for g in games:
        db_session.add(TeamGameStatsInStat(
            game_id=g.id, pp_shots=12, pp_time_seconds_total=600,
            pp_time_seconds_in_oz=360, pk_opp_breakouts=2,
            scoring_chance_shots=30,
        ))
        for p in players:
            db_session.add(PlayerGameStats(
                player_id=p.id, game_id=g.id,
                toi_5v5=15.0, cf60=50.0, ca60=40.0,
                xgf60=2.5, xga60=2.0,
                ff60=40.0, fa60=30.0, sf60=25.0, sa60=20.0,
            ))
            db_session.add(PlayerGameStatsInStat(
                player_id=p.id, game_id=g.id,
                shots=5, pb_won_dz=3, pb_total_dz=5,
                pb_won_oz=2, pb_total_oz=4, pb_won_nz=1, pb_total_nz=2,
                entries_pass=2, entries_stick=3, entries_dump=1,
                puck_losses=6, puck_losses_dz=2, puck_recoveries=8, puck_recoveries_oz=3,
            ))
    db_session.commit()
    return players[0]


def test_player_agg_returns_all_tier2_blocks(db_session, seeded_full):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        resp = client.get(f"/api/stats/player/{seeded_full.id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    for k in ("contested_puck", "zone_entry", "turnover_ratio",
              "danger_share", "impact_score"):
        assert k in body, f"missing {k}"
    assert body["contested_puck"]["games"] == 5
    assert body["zone_entry"]["total_entries"] == 5 * 6
    assert body["impact_score"]["games"] >= 1


def test_team_agg_returns_special_teams_v2(db_session, seeded_full):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        resp = client.get("/api/stats/team")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert "special_teams_v2" in body
    assert body["special_teams_v2"]["games"] == 5
```

- [ ] **Step 2: Run test**

Run: `backend/venv/bin/python -m pytest backend/tests/test_tier2_end_to_end.py -v`
Expected: 2 tests pass.

Also run the fast slice: `backend/venv/bin/python -m pytest backend/tests/ --ignore=backend/tests/test_ingest_router.py --ignore=backend/tests/test_ingest_end_to_end.py --ignore=backend/tests/test_orchestrator.py -q`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_tier2_end_to_end.py
git commit -m "test: end-to-end integration test for tier2 stats in player+team agg"
```

---

## Final verification

- [ ] **Full backend suite passes.** Fast slice + full run. Expect ~130 baseline + ~40 Phase 3 additions.

- [ ] **Frontend typecheck passes:** `cd frontend && npx tsc --noEmit` → no errors.

- [ ] **Manual smoke test:** the coach opens a player's report with the InStat fixture game ingested and sees Impact Score, Puck Battles, Zone Entry, Turnover Location, Danger Share blocks. Team report shows Special Teams (Advanced) block. Methodology page shows the 6 Tier 2 stats without "🚧 Coming Soon" pills.

- [ ] **Ledger deferred / follow-ups:**
  - Impact Score cohort computation happens per-request; consider caching per date range for performance if the roster grows past ~30 players.
  - Danger-Zone Shot Share uses `PlayerGameStatsInStat.shots` as a proxy for scoring-chance shots — Phase 4's shots-log parser will supply true SCA counts, at which point `danger_zone_shot_share` should be revisited.
  - `pk_opp_breakout_rate` denominator is "games with PK data" (proxy for PK count); if a per-game PK count column is ever added to `TeamGameStatsInStat`, use that instead.
  - Impact Score's `per_game` list ships in the response but the frontend `ImpactScoreCard` only surfaces averaged components in the tooltip; a per-game sparkline could be a nice enhancement.
