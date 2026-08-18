# Phase 1: Tier 1 Quick Wins — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship position-aware stat comparisons, TOI trend flagging, and a generalized auto-flag engine on the existing 49ing-only schema — before the InStat schema migration or the ingest pipeline. Delivers coach-visible value in ~1 week without any migration risk.

**Architecture:** Backend adds three focused helper modules (`cohorts.py`, `comparisons.py`, `flags.py`) plus a config file (`flag_rules.py`). The player stats endpoint extends its response with two new blocks: `comparisons` (per-stat team + position deltas with a colored indicator) and `flags` (list of triggered flags for the aggregation window + per-game outlier flags). Frontend consumes both, rendering a top-of-page flag summary panel, per-stat comparison rows, and per-game TOI badges. PDF report is updated to mirror the in-app additions.

**Tech Stack:** FastAPI · SQLAlchemy · SQLite (existing). Adds `pytest` + `pytest-cov` for backend tests. Frontend is React + TypeScript + Vite; no test framework added — verified via dev server + manual inspection. PDF via WeasyPrint + Jinja2 templates.

**Spec:** `docs/superpowers/specs/2026-08-18-ecac-stats-expansion-design.md` (sections 5 and 9.7–9.8, 9.12)

## Global Constraints

- All computation runs on the existing `PlayerGameStats` / `TeamGameStats` tables — **no schema migration in this phase**.
- Position group taxonomy: `F` (all forwards), `C` (centers, subset of F), `W` (wingers, subset of F), `D` (defenders), `G` (goalies). Determined from `Player.position` and `Player.is_center`.
- Flag trend threshold defaults: TOI L3-vs-L10 = **±10%**. Per-game outlier = **<50%** or **>150%** of L10 mean. Auto-flag engine z-score = **|z| > 1.0** default per rule.
- Per-60 rate stats use **TOI-weighted** means/stddevs (matches existing `aggregate_player_stats()` convention).
- Games with `toi_5v5 < 5` minutes are **excluded** from all baselines and flag evaluations.
- No flags fire for a rule unless the player has ≥ `baseline` games of qualifying history (default 10).
- Frontend colors: **green** = better than both team and position baselines; **yellow** = better than one; **red** = below both. Neutral (no comparison) = existing style.
- Flag badge cap on player report = **3 max** (highest |z| wins ties).
- Commits use conventional-commit style (`feat:`, `test:`, `refactor:`).

---

### Task 1: Backend test infrastructure

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_smoke.py`
- Modify: `backend/requirements.txt` (add `pytest>=8.0`, `pytest-cov>=5.0`)
- Create: `backend/pytest.ini`

**Interfaces:**
- Consumes: nothing (foundation task)
- Produces:
  - Pytest fixture `db_session` (function-scoped, in-memory SQLite, auto-creates all tables from `app.models.Base.metadata`, rolls back after test)
  - Pytest fixture `seed_roster(db_session) -> list[Player]` (returns 6 canonical players: 1 C, 2 W, 2 D, 1 G with predictable jersey numbers)
  - Pytest fixture `seed_games(db_session, n=10) -> list[Game]` (returns `n` games with sequential dates starting 2025-10-01, alternating home/away)

- [ ] **Step 1: Add pytest deps and install**

Modify `backend/requirements.txt` — append these two lines:
```
pytest>=8.0
pytest-cov>=5.0
```

Run: `backend/venv/bin/pip install pytest pytest-cov`
Expected: successful install of pytest 8.x.

- [ ] **Step 2: Create pytest config**

Create `backend/pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

- [ ] **Step 3: Create conftest with in-memory DB fixture**

Create `backend/tests/__init__.py` (empty file).

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

- [ ] **Step 4: Write a smoke test to verify fixtures work**

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
    all_players = db_session.query(Player).order_by(Player.name).all()
    assert len(all_players) == 6
    positions = sorted([p.position for p in all_players])
    assert positions == ["D", "D", "F", "F", "F", "G"]


def test_seed_games_default_is_ten(db_session, seed_games):
    from app.models import Game
    games = seed_games()
    assert len(games) == 10
    assert db_session.query(Game).count() == 10
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd backend && venv/bin/pytest tests/test_smoke.py -v`
Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/pytest.ini backend/tests/
git commit -m "test: add pytest infrastructure with in-memory db fixtures"
```

---

### Task 2: Position cohort logic

**Files:**
- Create: `backend/app/cohorts.py`
- Create: `backend/tests/test_cohorts.py`

**Interfaces:**
- Consumes: `app.models.Player`
- Produces:
  - `position_group(player: Player) -> str` — returns one of `"F"`, `"C"`, `"W"`, `"D"`, `"G"`
  - `cohort_matches(player: Player, cohort: str) -> bool` — cohort is one of `"F"`, `"C"`, `"W"`, `"D"`, `"G"`; F matches all forwards (C and W included)
  - `cohort_baseline(values: list[float], weights: list[float] | None = None) -> dict` — returns `{"mean": float | None, "std": float | None, "n": int}`; weighted variants use TOI weights; `None` returned when `n < 2` or all values zero

- [ ] **Step 1: Write failing tests for position_group**

Create `backend/tests/test_cohorts.py`:
```python
import pytest
from app.models import Player
from app.cohorts import position_group, cohort_matches, cohort_baseline


class TestPositionGroup:
    def test_forward_non_center_returns_F(self):
        p = Player(name="x", position="F", is_center=False)
        assert position_group(p) == "W"

    def test_forward_center_returns_C(self):
        p = Player(name="x", position="F", is_center=True)
        assert position_group(p) == "C"

    def test_defender_returns_D(self):
        p = Player(name="x", position="D", is_center=False)
        assert position_group(p) == "D"

    def test_goalie_returns_G(self):
        p = Player(name="x", position="G", is_center=False)
        assert position_group(p) == "G"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_cohorts.py::TestPositionGroup -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.cohorts'`

- [ ] **Step 3: Create cohorts.py with position_group**

Create `backend/app/cohorts.py`:
```python
from typing import Optional
from statistics import mean, pstdev
from .models import Player


def position_group(player: Player) -> str:
    """Return the primary position group for a player.

    F is used as an umbrella (see cohort_matches); position_group returns
    the most specific label: C (center forward), W (winger), D, G.
    """
    if player.position == "D":
        return "D"
    if player.position == "G":
        return "G"
    if player.position == "F":
        return "C" if player.is_center else "W"
    raise ValueError(f"Unknown position: {player.position!r}")


def cohort_matches(player: Player, cohort: str) -> bool:
    """True if player belongs in the requested cohort.

    F matches all forwards (both C and W). C, W, D, G match exactly.
    """
    pg = position_group(player)
    if cohort == "F":
        return pg in ("C", "W")
    return pg == cohort


def cohort_baseline(
    values: list[float],
    weights: Optional[list[float]] = None,
) -> dict:
    """Compute mean and population stddev; TOI-weighted if weights given.

    Returns {"mean": float | None, "std": float | None, "n": int}.
    None returned when n < 2 or total weight is zero.
    """
    filtered = [
        (v, (weights[i] if weights else 1.0))
        for i, v in enumerate(values)
        if v is not None
    ]
    n = len(filtered)
    if n < 2:
        return {"mean": None, "std": None, "n": n}
    total_w = sum(w for _, w in filtered)
    if total_w <= 0:
        return {"mean": None, "std": None, "n": n}
    m = sum(v * w for v, w in filtered) / total_w
    var = sum(w * (v - m) ** 2 for v, w in filtered) / total_w
    return {"mean": m, "std": var ** 0.5, "n": n}
```

- [ ] **Step 4: Run position_group tests to verify pass**

Run: `cd backend && venv/bin/pytest tests/test_cohorts.py::TestPositionGroup -v`
Expected: 4 tests pass.

- [ ] **Step 5: Write failing tests for cohort_matches**

Append to `backend/tests/test_cohorts.py`:
```python
class TestCohortMatches:
    def test_F_matches_center(self):
        p = Player(name="x", position="F", is_center=True)
        assert cohort_matches(p, "F") is True

    def test_F_matches_winger(self):
        p = Player(name="x", position="F", is_center=False)
        assert cohort_matches(p, "F") is True

    def test_F_does_not_match_defender(self):
        p = Player(name="x", position="D", is_center=False)
        assert cohort_matches(p, "F") is False

    def test_C_matches_only_center(self):
        c = Player(name="x", position="F", is_center=True)
        w = Player(name="y", position="F", is_center=False)
        assert cohort_matches(c, "C") is True
        assert cohort_matches(w, "C") is False

    def test_D_matches_only_defender(self):
        f = Player(name="x", position="F", is_center=False)
        d = Player(name="y", position="D", is_center=False)
        assert cohort_matches(d, "D") is True
        assert cohort_matches(f, "D") is False
```

- [ ] **Step 6: Verify tests pass**

Run: `cd backend && venv/bin/pytest tests/test_cohorts.py::TestCohortMatches -v`
Expected: 5 tests pass.

- [ ] **Step 7: Write failing tests for cohort_baseline**

Append to `backend/tests/test_cohorts.py`:
```python
class TestCohortBaseline:
    def test_returns_none_for_empty(self):
        b = cohort_baseline([])
        assert b == {"mean": None, "std": None, "n": 0}

    def test_returns_none_for_single_value(self):
        b = cohort_baseline([0.5])
        assert b["mean"] is None
        assert b["std"] is None
        assert b["n"] == 1

    def test_unweighted_mean_and_std(self):
        b = cohort_baseline([0.4, 0.5, 0.6])
        assert b["mean"] == pytest.approx(0.5, abs=1e-9)
        assert b["std"] == pytest.approx(0.0816496, abs=1e-4)
        assert b["n"] == 3

    def test_weighted_mean(self):
        b = cohort_baseline([1.0, 3.0], weights=[1.0, 3.0])
        # weighted mean = (1*1 + 3*3) / 4 = 2.5
        assert b["mean"] == pytest.approx(2.5, abs=1e-9)

    def test_ignores_none_values(self):
        b = cohort_baseline([0.4, None, 0.6, None])
        assert b["mean"] == pytest.approx(0.5, abs=1e-9)
        assert b["n"] == 2

    def test_zero_total_weight_returns_none(self):
        b = cohort_baseline([1.0, 2.0], weights=[0.0, 0.0])
        assert b["mean"] is None
        assert b["std"] is None
```

- [ ] **Step 8: Verify all cohort tests pass**

Run: `cd backend && venv/bin/pytest tests/test_cohorts.py -v`
Expected: 15 tests total pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/cohorts.py backend/tests/test_cohorts.py
git commit -m "feat: add position cohorts and baseline computation"
```

---

### Task 3: Comparison overlay for player stats

**Files:**
- Create: `backend/app/comparisons.py`
- Create: `backend/tests/test_comparisons.py`

**Interfaces:**
- Consumes: `app.cohorts.cohort_matches`, `app.cohorts.cohort_baseline`, aggregated player-stat dicts from `aggregate_player_stats`
- Produces:
  - `COMPARISON_COHORTS: dict[str, str]` — maps stat_key → cohort (default `"F"` for forward stats, `"C"` for faceoff-related, `"D"` for defense-relative, `"G"` for goalie-only)
  - `HIGHER_IS_BETTER: dict[str, bool]` — direction of "good" per stat (e.g., `cf60=True`, `ca60=False`)
  - `build_comparisons(target_player, target_aggs, all_player_aggs) -> dict[str, dict]` — for each stat_key present in `target_aggs`, return `{"value": float, "team_baseline": {"mean","std","n"}, "position_baseline": {"mean","std","n"}, "team_delta": float | None, "position_delta": float | None, "indicator": "green"|"yellow"|"red"|"neutral"}`
    - `all_player_aggs` is `list[tuple[Player, dict]]` where each dict is the output of `aggregate_player_stats` for one player over the same window

- [ ] **Step 1: Write failing test for basic comparison shape**

Create `backend/tests/test_comparisons.py`:
```python
import pytest
from app.models import Player
from app.comparisons import build_comparisons, COMPARISON_COHORTS, HIGHER_IS_BETTER


def _mk_player(name, pos, is_center=False):
    return Player(name=name, position=pos, is_center=is_center, active=True)


def _mk_agg(cf60=None, ca60=None, xfsh_pct=None, personal_fo_pct=None, toi=100.0):
    return {
        "toi_5v5": toi,
        "cf60": cf60,
        "ca60": ca60,
        "xfsh_pct": xfsh_pct,
        "personal_fo_pct": personal_fo_pct,
    }


class TestBuildComparisons:
    def test_returns_dict_keyed_by_stat_name(self):
        target = _mk_player("target", "F")
        other = _mk_player("other", "F")
        target_agg = _mk_agg(cf60=60.0)
        result = build_comparisons(
            target, target_agg, [(target, target_agg), (other, _mk_agg(cf60=50.0))]
        )
        assert "cf60" in result

    def test_team_delta_computed_from_all_players(self):
        target = _mk_player("target", "F")
        p2 = _mk_player("p2", "F")
        p3 = _mk_player("p3", "D")
        aggs = [
            (target, _mk_agg(cf60=60.0)),
            (p2, _mk_agg(cf60=40.0)),
            (p3, _mk_agg(cf60=50.0)),
        ]
        result = build_comparisons(target, _mk_agg(cf60=60.0), aggs)
        # team mean = 50, delta = 10
        assert result["cf60"]["team_delta"] == pytest.approx(10.0, abs=1e-9)

    def test_position_delta_uses_cohort_from_config(self):
        target = _mk_player("target", "F")
        p2 = _mk_player("p2", "F")
        d1 = _mk_player("d1", "D")
        d2 = _mk_player("d2", "D")
        aggs = [
            (target, _mk_agg(cf60=60.0)),
            (p2, _mk_agg(cf60=40.0)),
            (d1, _mk_agg(cf60=30.0)),
            (d2, _mk_agg(cf60=30.0)),
        ]
        # cf60 cohort is "F" — position mean = (60+40)/2 = 50, delta = 10
        result = build_comparisons(target, _mk_agg(cf60=60.0), aggs)
        assert result["cf60"]["position_delta"] == pytest.approx(10.0, abs=1e-9)

    def test_higher_is_better_gives_green_when_above_both(self):
        target = _mk_player("target", "F")
        p2 = _mk_player("p2", "F")
        d1 = _mk_player("d1", "D")
        aggs = [
            (target, _mk_agg(cf60=70.0)),
            (p2, _mk_agg(cf60=40.0)),
            (d1, _mk_agg(cf60=30.0)),
        ]
        result = build_comparisons(target, _mk_agg(cf60=70.0), aggs)
        assert result["cf60"]["indicator"] == "green"

    def test_lower_is_better_gives_green_when_below_both(self):
        # ca60 = lower is better
        target = _mk_player("target", "F")
        p2 = _mk_player("p2", "F")
        aggs = [
            (target, _mk_agg(ca60=20.0)),
            (p2, _mk_agg(ca60=40.0)),
        ]
        result = build_comparisons(target, _mk_agg(ca60=20.0), aggs)
        assert result["ca60"]["indicator"] == "green"

    def test_faceoff_stat_compares_to_centers_only(self):
        center = _mk_player("c", "F", is_center=True)
        winger = _mk_player("w", "F", is_center=False)
        aggs = [
            (center, _mk_agg(personal_fo_pct=0.60)),
            (winger, _mk_agg(personal_fo_pct=0.40)),
        ]
        # personal_fo_pct cohort = "C" → position baseline uses only centers
        # only one center → position_baseline mean/std should be None (n<2)
        result = build_comparisons(center, _mk_agg(personal_fo_pct=0.60), aggs)
        assert result["personal_fo_pct"]["position_baseline"]["n"] == 1
        assert result["personal_fo_pct"]["position_baseline"]["mean"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/pytest tests/test_comparisons.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.comparisons'`

- [ ] **Step 3: Implement comparisons.py**

Create `backend/app/comparisons.py`:
```python
from typing import Optional
from .models import Player
from .cohorts import cohort_matches, cohort_baseline


COMPARISON_COHORTS: dict[str, str] = {
    "toi_5v5": "F",
    "on_ice_cf_pct": "F",
    "on_ice_xgf_pct": "F",
    "on_ice_sf_pct": "F",
    "cf60": "F",
    "ca60": "F",
    "ff60": "F",
    "fa60": "F",
    "sf60": "F",
    "sa60": "F",
    "xfsh_pct": "F",
    "xfsv_pct": "F",
    "icf": "F",
    "isf": "F",
    "median_shift_seconds": "F",
    "personal_fo_pct": "C",
    "on_ice_fo_pct": "C",
}

# Per-cohort override: defenders compared to defenders for these stats
DEFENDER_STATS = {
    "on_ice_cf_pct", "on_ice_xgf_pct", "on_ice_sf_pct",
    "cf60", "ca60", "ff60", "fa60", "sf60", "sa60",
    "xfsh_pct", "xfsv_pct", "toi_5v5", "median_shift_seconds",
}

# Direction: True = higher is better
HIGHER_IS_BETTER: dict[str, bool] = {
    "toi_5v5": True,
    "on_ice_cf_pct": True,
    "on_ice_xgf_pct": True,
    "on_ice_sf_pct": True,
    "cf60": True,
    "ca60": False,
    "ff60": True,
    "fa60": False,
    "sf60": True,
    "sa60": False,
    "xfsh_pct": True,
    "xfsv_pct": True,
    "icf": True,
    "isf": True,
    "median_shift_seconds": True,
    "personal_fo_pct": True,
    "on_ice_fo_pct": True,
}


def _cohort_for(target: Player, stat: str) -> str:
    """Choose comparison cohort for target player's stat.

    Defenders always compare to D. Faceoff stats use C. Otherwise F.
    """
    if target.position == "D" and stat in DEFENDER_STATS:
        return "D"
    if target.position == "G":
        return "G"
    return COMPARISON_COHORTS.get(stat, "F")


def _delta(target_val: float, baseline_mean: Optional[float]) -> Optional[float]:
    if target_val is None or baseline_mean is None:
        return None
    return target_val - baseline_mean


def _indicator(
    target_val: Optional[float],
    team_mean: Optional[float],
    position_mean: Optional[float],
    higher_is_better: bool,
) -> str:
    """Green if above both baselines (or below both for lower-is-better)."""
    if target_val is None:
        return "neutral"
    beats_team = _beats(target_val, team_mean, higher_is_better)
    beats_pos = _beats(target_val, position_mean, higher_is_better)
    trues = sum(1 for x in (beats_team, beats_pos) if x is True)
    falses = sum(1 for x in (beats_team, beats_pos) if x is False)
    if beats_team is None and beats_pos is None:
        return "neutral"
    if trues == 2:
        return "green"
    if trues == 1:
        return "yellow"
    if falses >= 1:
        return "red"
    return "neutral"


def _beats(val: Optional[float], baseline: Optional[float], higher_is_better: bool) -> Optional[bool]:
    if val is None or baseline is None:
        return None
    return (val > baseline) if higher_is_better else (val < baseline)


def build_comparisons(
    target: Player,
    target_aggs: dict,
    all_player_aggs: list[tuple[Player, dict]],
) -> dict:
    """For each stat in target_aggs, compute team + position baselines and colored indicator."""
    result: dict = {}
    for stat_key in COMPARISON_COHORTS:
        target_val = target_aggs.get(stat_key)
        # team baseline: everyone with a value for this stat, TOI-weighted where applicable
        team_values = [agg.get(stat_key) for _, agg in all_player_aggs]
        team_weights = [agg.get("toi_5v5") or 0 for _, agg in all_player_aggs]
        team = cohort_baseline(team_values, team_weights)

        cohort = _cohort_for(target, stat_key)
        pos_values = [
            agg.get(stat_key)
            for p, agg in all_player_aggs
            if cohort_matches(p, cohort)
        ]
        pos_weights = [
            agg.get("toi_5v5") or 0
            for p, agg in all_player_aggs
            if cohort_matches(p, cohort)
        ]
        position = cohort_baseline(pos_values, pos_weights)

        higher_better = HIGHER_IS_BETTER.get(stat_key, True)
        result[stat_key] = {
            "value": target_val,
            "cohort": cohort,
            "team_baseline": team,
            "position_baseline": position,
            "team_delta": _delta(target_val, team["mean"]),
            "position_delta": _delta(target_val, position["mean"]),
            "indicator": _indicator(target_val, team["mean"], position["mean"], higher_better),
        }
    return result
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && venv/bin/pytest tests/test_comparisons.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/comparisons.py backend/tests/test_comparisons.py
git commit -m "feat: add position-aware comparison overlay for player stats"
```

---

### Task 4: Flag rule engine

**Files:**
- Create: `backend/app/flags.py`
- Create: `backend/tests/test_flags.py`

**Interfaces:**
- Consumes: player trend list (list of per-game dicts with `date`, `toi_5v5`, and per-60 stat fields — the same shape `aggregate_player_stats` produces in its `trend` field)
- Produces:
  - `@dataclass Rule(stat_key: str, window: int, baseline: int, z_threshold: float, label: str)`
  - `@dataclass Flag(kind: str, label: str, direction: str, z_score: float | None, window_value: float | None, baseline_value: float | None, game_id: int | None = None)` — `kind` is `"trend"` for rolling flags, `"outlier"` for per-game outliers
  - `evaluate_rule(rule: Rule, trend: list[dict]) -> Optional[Flag]` — returns a Flag when |z| exceeds threshold, else None
  - `toi_weighted_stats(trend: list[dict], stat_key: str) -> dict` — returns `{"mean": float | None, "std": float | None, "n": int}`; uses only games where `toi_5v5 >= 5`

- [ ] **Step 1: Write failing test for Rule dataclass and toi_weighted_stats**

Create `backend/tests/test_flags.py`:
```python
import pytest
from app.flags import Rule, Flag, evaluate_rule, toi_weighted_stats


def _trend(*points):
    """Helper: each arg is (date_iso, toi, stat_value) → dict."""
    return [
        {"game_id": i + 1, "date": d, "toi_5v5": toi, "cf60": v}
        for i, (d, toi, v) in enumerate(points)
    ]


class TestToiWeightedStats:
    def test_empty_returns_zero_n(self):
        b = toi_weighted_stats([], "cf60")
        assert b == {"mean": None, "std": None, "n": 0}

    def test_ignores_games_under_5_min_toi(self):
        t = _trend(
            ("2025-10-01", 20.0, 60.0),
            ("2025-10-05", 3.0, 100.0),  # excluded, TOI < 5
            ("2025-10-09", 15.0, 40.0),
        )
        b = toi_weighted_stats(t, "cf60")
        assert b["n"] == 2

    def test_computes_toi_weighted_mean(self):
        t = _trend(
            ("2025-10-01", 20.0, 60.0),
            ("2025-10-05", 10.0, 30.0),
        )
        # weighted = (60*20 + 30*10) / 30 = 50
        b = toi_weighted_stats(t, "cf60")
        assert b["mean"] == pytest.approx(50.0, abs=1e-9)

    def test_ignores_none_values(self):
        t = _trend(
            ("2025-10-01", 20.0, 60.0),
            ("2025-10-05", 15.0, None),
            ("2025-10-09", 10.0, 40.0),
        )
        b = toi_weighted_stats(t, "cf60")
        assert b["n"] == 2
```

- [ ] **Step 2: Verify test fails**

Run: `cd backend && venv/bin/pytest tests/test_flags.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.flags'`

- [ ] **Step 3: Implement Rule/Flag/toi_weighted_stats**

Create `backend/app/flags.py`:
```python
from dataclasses import dataclass, field
from typing import Optional


MIN_TOI_MINUTES = 5.0  # games below this are excluded from all flag computation


@dataclass(frozen=True)
class Rule:
    stat_key: str
    window: int
    baseline: int
    z_threshold: float
    label: str


@dataclass
class Flag:
    kind: str          # "trend" or "outlier"
    label: str
    direction: str     # "up" or "down"
    z_score: Optional[float]
    window_value: Optional[float]
    baseline_value: Optional[float]
    game_id: Optional[int] = None


def toi_weighted_stats(trend: list[dict], stat_key: str) -> dict:
    """Return TOI-weighted mean and stddev of stat_key across trend.

    Games with toi_5v5 < MIN_TOI_MINUTES or None values are excluded.
    Returns {"mean": None, "std": None, "n": 0} for empty or single-value sets.
    """
    values = []
    weights = []
    for pt in trend:
        toi = pt.get("toi_5v5")
        val = pt.get(stat_key)
        if toi is None or toi < MIN_TOI_MINUTES:
            continue
        if val is None:
            continue
        values.append(val)
        weights.append(toi)
    n = len(values)
    if n < 2:
        return {"mean": None, "std": None, "n": n}
    total_w = sum(weights)
    if total_w <= 0:
        return {"mean": None, "std": None, "n": n}
    mean = sum(v * w for v, w in zip(values, weights)) / total_w
    var = sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / total_w
    return {"mean": mean, "std": var ** 0.5, "n": n}
```

- [ ] **Step 4: Verify toi_weighted_stats tests pass**

Run: `cd backend && venv/bin/pytest tests/test_flags.py::TestToiWeightedStats -v`
Expected: 4 tests pass.

- [ ] **Step 5: Write failing tests for evaluate_rule**

Append to `backend/tests/test_flags.py`:
```python
class TestEvaluateRule:
    def _mk_trend(self, cf60_values):
        return [
            {"game_id": i + 1, "date": f"2025-10-{i+1:02d}", "toi_5v5": 15.0, "cf60": v}
            for i, v in enumerate(cf60_values)
        ]

    def test_returns_none_when_baseline_history_insufficient(self):
        rule = Rule("cf60", window=3, baseline=10, z_threshold=1.0, label="test")
        trend = self._mk_trend([50.0, 55.0, 60.0])  # only 3 games
        assert evaluate_rule(rule, trend) is None

    def test_returns_none_when_z_below_threshold(self):
        rule = Rule("cf60", window=3, baseline=10, z_threshold=1.0, label="test")
        # baseline all 50, window all 50 → z = 0
        trend = self._mk_trend([50.0] * 10)
        assert evaluate_rule(rule, trend) is None

    def test_returns_flag_when_window_much_higher(self):
        rule = Rule("cf60", window=3, baseline=10, z_threshold=1.0, label="Corsi shift")
        # baseline ~50 with variance, window jumps to 80
        trend = self._mk_trend([45.0, 55.0, 48.0, 52.0, 47.0, 53.0, 50.0, 80.0, 80.0, 80.0])
        flag = evaluate_rule(rule, trend)
        assert flag is not None
        assert flag.direction == "up"
        assert flag.z_score > 1.0
        assert flag.label == "Corsi shift"

    def test_returns_flag_when_window_much_lower(self):
        rule = Rule("cf60", window=3, baseline=10, z_threshold=1.0, label="Corsi shift")
        trend = self._mk_trend([50.0, 55.0, 48.0, 52.0, 47.0, 53.0, 51.0, 20.0, 20.0, 20.0])
        flag = evaluate_rule(rule, trend)
        assert flag is not None
        assert flag.direction == "down"
        assert flag.z_score < -1.0

    def test_baseline_uses_last_N_games_not_all(self):
        rule = Rule("cf60", window=3, baseline=5, z_threshold=1.0, label="test")
        # 8 games total; baseline should use last 5 (not include the first 3 wild values)
        trend = self._mk_trend([100.0, 100.0, 100.0, 50.0, 50.0, 50.0, 50.0, 50.0])
        # last 5 all 50 → std = 0 → cannot compute z → None
        assert evaluate_rule(rule, trend) is None
```

- [ ] **Step 6: Extend flags.py with evaluate_rule**

Append to `backend/app/flags.py`:
```python
def evaluate_rule(rule: Rule, trend: list[dict]) -> Optional[Flag]:
    """Evaluate a rolling-window flag rule against a player's trend."""
    qualifying = [
        pt for pt in trend
        if pt.get("toi_5v5") is not None
        and pt["toi_5v5"] >= MIN_TOI_MINUTES
        and pt.get(rule.stat_key) is not None
    ]
    if len(qualifying) < rule.baseline:
        return None

    baseline_trend = qualifying[-rule.baseline:]
    window_trend = qualifying[-rule.window:]

    base = toi_weighted_stats(baseline_trend, rule.stat_key)
    win = toi_weighted_stats(window_trend, rule.stat_key)

    if base["mean"] is None or base["std"] is None or base["std"] == 0:
        return None
    if win["mean"] is None:
        return None

    z = (win["mean"] - base["mean"]) / base["std"]
    if abs(z) < rule.z_threshold:
        return None

    return Flag(
        kind="trend",
        label=rule.label,
        direction="up" if z > 0 else "down",
        z_score=z,
        window_value=win["mean"],
        baseline_value=base["mean"],
    )
```

- [ ] **Step 7: Verify all flag tests pass**

Run: `cd backend && venv/bin/pytest tests/test_flags.py -v`
Expected: 9 tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/flags.py backend/tests/test_flags.py
git commit -m "feat: add z-score based flag rule engine"
```

---

### Task 5: TOI trend flag + single-game outlier

**Files:**
- Modify: `backend/app/flags.py`
- Modify: `backend/tests/test_flags.py`

**Interfaces:**
- Consumes: player trend list (same shape as Task 4)
- Produces:
  - `evaluate_toi_trend(trend: list[dict]) -> Optional[Flag]` — flag with `kind="trend"`, `label="TOI shift"`, fires when `|(toi_L3 - toi_L10) / toi_L10| > 0.10`; requires ≥ 10 qualifying games
  - `evaluate_toi_outliers(trend: list[dict]) -> list[Flag]` — one Flag per outlier game with `kind="outlier"`, `label="reduced role"` or `"expanded role"`, `game_id` populated; `game_toi / toi_L10 < 0.50` → reduced; `> 1.50` → expanded

- [ ] **Step 1: Write failing tests for evaluate_toi_trend**

Append to `backend/tests/test_flags.py`:
```python
from app.flags import evaluate_toi_trend, evaluate_toi_outliers


def _toi_trend(toi_values):
    return [
        {"game_id": i + 1, "date": f"2025-10-{i+1:02d}", "toi_5v5": v, "cf60": 50.0}
        for i, v in enumerate(toi_values)
    ]


class TestEvaluateToiTrend:
    def test_returns_none_when_under_10_games(self):
        assert evaluate_toi_trend(_toi_trend([15.0] * 5)) is None

    def test_returns_none_when_trend_within_10_pct(self):
        # all 15 min TOI → no shift
        assert evaluate_toi_trend(_toi_trend([15.0] * 10)) is None

    def test_flags_trending_up(self):
        # L10 mean = ~15, L3 mean = 20 → +33%
        trend = _toi_trend([15, 15, 15, 15, 15, 15, 15, 20, 20, 20])
        flag = evaluate_toi_trend(trend)
        assert flag is not None
        assert flag.direction == "up"
        assert flag.label == "TOI shift"

    def test_flags_trending_down(self):
        trend = _toi_trend([15, 15, 15, 15, 15, 15, 15, 8, 8, 8])
        flag = evaluate_toi_trend(trend)
        assert flag is not None
        assert flag.direction == "down"

    def test_does_not_flag_9_pct_shift(self):
        # L10 mean = ~15.4, L3 = 16.7 → +8.4%
        trend = _toi_trend([15, 15, 15, 15, 15, 15, 15, 17, 16, 17])
        assert evaluate_toi_trend(trend) is None


class TestEvaluateToiOutliers:
    def test_returns_empty_when_under_10_games(self):
        assert evaluate_toi_outliers(_toi_trend([15.0] * 5)) == []

    def test_flags_reduced_role_game(self):
        # L10 (games 1-10) mean = 15; game 11 = 5 (33%) → reduced role
        trend = _toi_trend([15.0] * 10 + [5.0])
        flags = evaluate_toi_outliers(trend)
        # first 10 games have no L10 baseline for themselves, but game 11 does
        reduced = [f for f in flags if f.label == "reduced role"]
        assert len(reduced) == 1
        assert reduced[0].game_id == 11

    def test_flags_expanded_role_game(self):
        trend = _toi_trend([12.0] * 10 + [22.0])
        # game 11: 22 / 12 = 1.83 > 1.5
        flags = evaluate_toi_outliers(trend)
        expanded = [f for f in flags if f.label == "expanded role"]
        assert len(expanded) == 1
        assert expanded[0].game_id == 11

    def test_does_not_flag_normal_game(self):
        trend = _toi_trend([15.0] * 10 + [14.0])  # 93% of L10
        flags = evaluate_toi_outliers(trend)
        assert flags == []
```

- [ ] **Step 2: Verify tests fail**

Run: `cd backend && venv/bin/pytest tests/test_flags.py::TestEvaluateToiTrend -v`
Expected: FAIL with `ImportError: cannot import name 'evaluate_toi_trend'`

- [ ] **Step 3: Implement TOI-specific evaluators**

Append to `backend/app/flags.py`:
```python
TOI_TREND_THRESHOLD = 0.10  # ±10%
TOI_OUTLIER_LOW = 0.50
TOI_OUTLIER_HIGH = 1.50


def _mean_toi(trend_slice: list[dict]) -> Optional[float]:
    tois = [pt["toi_5v5"] for pt in trend_slice
            if pt.get("toi_5v5") is not None and pt["toi_5v5"] >= MIN_TOI_MINUTES]
    if not tois:
        return None
    return sum(tois) / len(tois)


def evaluate_toi_trend(trend: list[dict]) -> Optional[Flag]:
    """L3-vs-L10 TOI shift flag. Requires ≥10 qualifying games."""
    qualifying = [pt for pt in trend
                  if pt.get("toi_5v5") is not None and pt["toi_5v5"] >= MIN_TOI_MINUTES]
    if len(qualifying) < 10:
        return None
    l10_mean = _mean_toi(qualifying[-10:])
    l3_mean = _mean_toi(qualifying[-3:])
    if l10_mean is None or l3_mean is None or l10_mean == 0:
        return None
    pct_shift = (l3_mean - l10_mean) / l10_mean
    if abs(pct_shift) < TOI_TREND_THRESHOLD:
        return None
    return Flag(
        kind="trend",
        label="TOI shift",
        direction="up" if pct_shift > 0 else "down",
        z_score=None,
        window_value=l3_mean,
        baseline_value=l10_mean,
    )


def evaluate_toi_outliers(trend: list[dict]) -> list[Flag]:
    """Per-game outlier flags. Requires ≥10 qualifying prior games for each check."""
    qualifying = [pt for pt in trend
                  if pt.get("toi_5v5") is not None and pt["toi_5v5"] >= MIN_TOI_MINUTES]
    if len(qualifying) < 10:
        return []
    # Sort by game order preserved by trend list order (aggregate_player_stats sorts by date)
    flags: list[Flag] = []
    # Only games at position >= 10 (index) have a prior L10 baseline
    for i in range(10, len(qualifying)):
        prior_10 = qualifying[i - 10:i]
        baseline = _mean_toi(prior_10)
        game = qualifying[i]
        toi = game["toi_5v5"]
        if baseline is None or baseline == 0 or toi is None:
            continue
        ratio = toi / baseline
        if ratio < TOI_OUTLIER_LOW:
            flags.append(Flag(
                kind="outlier",
                label="reduced role",
                direction="down",
                z_score=None,
                window_value=toi,
                baseline_value=baseline,
                game_id=game["game_id"],
            ))
        elif ratio > TOI_OUTLIER_HIGH:
            flags.append(Flag(
                kind="outlier",
                label="expanded role",
                direction="up",
                z_score=None,
                window_value=toi,
                baseline_value=baseline,
                game_id=game["game_id"],
            ))
    return flags
```

- [ ] **Step 4: Verify TOI tests pass**

Run: `cd backend && venv/bin/pytest tests/test_flags.py -v`
Expected: 18 tests pass (9 from Task 4 + 9 new).

- [ ] **Step 5: Commit**

```bash
git add backend/app/flags.py backend/tests/test_flags.py
git commit -m "feat: add TOI trend and per-game outlier flag evaluators"
```

---

### Task 6: Flag rules config + enrichment helper + endpoint integration

**Files:**
- Create: `backend/app/flag_rules.py`
- Create: `backend/app/enrichment.py`
- Modify: `backend/app/routers/stats.py`
- Modify: `backend/app/calculations.py` (add helper to trim `top_n` flags by |z|)
- Create: `backend/tests/test_flag_selection.py`
- Create: `backend/tests/test_stats_endpoint.py`

**Interfaces:**
- Consumes: `app.flags.Rule/Flag/evaluate_rule/evaluate_toi_trend/evaluate_toi_outliers`; `app.comparisons.build_comparisons`
- Produces:
  - `DEFAULT_FLAG_RULES: list[Rule]` — the three spec-defined rules
  - `top_flags(flags: list[Flag], n: int = 3) -> list[Flag]` — sorts by descending |z_score| (None z sorts to bottom) and returns top n
  - `enrich_player_agg(player, agg, all_aggs) -> dict` — mutates & returns `agg` with three new keys:
    - `"comparisons": {stat_key: comparison_dict}` (from Task 3)
    - `"flags": [flag_dict]` (rolling-window trend flags, top 3 by |z|, `Flag` dataclass converted via `dataclasses.asdict`)
    - `"game_flags": {game_id: [flag_dict]}` (per-game outlier flags, keyed by int game id)
  - Modified GET `/api/stats/player/{player_id}` response now includes the three keys above (reuses `enrich_player_agg`)

- [ ] **Step 1: Write failing tests for top_flags helper**

Create `backend/tests/test_flag_selection.py`:
```python
from app.flags import Flag
from app.calculations import top_flags


def _flag(z, label="test"):
    return Flag(kind="trend", label=label, direction="up",
                z_score=z, window_value=None, baseline_value=None)


class TestTopFlags:
    def test_returns_all_when_fewer_than_n(self):
        flags = [_flag(1.5), _flag(-2.0)]
        assert len(top_flags(flags, n=3)) == 2

    def test_sorts_by_absolute_z_descending(self):
        flags = [_flag(1.5, "small"), _flag(-3.0, "big"), _flag(2.0, "mid")]
        result = top_flags(flags, n=3)
        assert [f.label for f in result] == ["big", "mid", "small"]

    def test_caps_at_n(self):
        flags = [_flag(z) for z in [1.5, -2.0, 3.0, -1.8, 2.5]]
        assert len(top_flags(flags, n=3)) == 3

    def test_none_z_scores_go_last(self):
        f_none = Flag(kind="trend", label="none-z", direction="up",
                      z_score=None, window_value=None, baseline_value=None)
        flags = [_flag(1.5), f_none, _flag(2.5)]
        result = top_flags(flags, n=3)
        assert result[-1].label == "none-z"
```

- [ ] **Step 2: Verify tests fail**

Run: `cd backend && venv/bin/pytest tests/test_flag_selection.py -v`
Expected: FAIL with `ImportError: cannot import name 'top_flags'`

- [ ] **Step 3: Add top_flags to calculations.py**

Append to `backend/app/calculations.py`:
```python
def top_flags(flags: list, n: int = 3) -> list:
    """Return top n flags sorted by |z_score| descending, None z_scores last."""
    def sort_key(f):
        z = getattr(f, "z_score", None)
        return (0 if z is None else 1, abs(z) if z is not None else 0)
    return sorted(flags, key=sort_key, reverse=True)[:n]
```

- [ ] **Step 4: Verify top_flags tests pass**

Run: `cd backend && venv/bin/pytest tests/test_flag_selection.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Create flag rules config**

Create `backend/app/flag_rules.py`:
```python
"""Default auto-flag rule set. See spec §5.3 and §9.7."""
from .flags import Rule


DEFAULT_FLAG_RULES: list[Rule] = [
    Rule(stat_key="cf60",           window=3, baseline=10, z_threshold=1.0, label="Corsi shift"),
    Rule(stat_key="on_ice_xgf_pct", window=3, baseline=10, z_threshold=1.0, label="xG% shift"),
    Rule(stat_key="xfsh_pct",       window=5, baseline=15, z_threshold=1.2, label="shot quality shift"),
]
```

Note: TOI trend + outlier flags are evaluated separately (not through DEFAULT_FLAG_RULES) because they use percentage thresholds, not z-scores.

- [ ] **Step 6: Create enrichment helper**

Create `backend/app/enrichment.py`:
```python
"""Shared helper for enriching a player's aggregate stats with
comparisons, flags, and per-game flags. Used by both the stats API
and the PDF report generator so behavior stays consistent."""
from dataclasses import asdict
from .models import Player
from .comparisons import build_comparisons
from .flags import evaluate_rule, evaluate_toi_trend, evaluate_toi_outliers
from .flag_rules import DEFAULT_FLAG_RULES
from .calculations import top_flags


def enrich_player_agg(
    player: Player,
    agg: dict,
    all_aggs: list[tuple[Player, dict]],
) -> dict:
    """Attach comparisons/flags/game_flags to a player aggregate in-place.
    Returns the same dict for chaining."""
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

    return agg
```

- [ ] **Step 7: Write failing integration test for endpoint**

Create `backend/tests/test_stats_endpoint.py`:
```python
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models import Player, Game, PlayerGameStats


def _client_with_db():
    engine = create_engine("sqlite:///:memory:", future=True,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, future=True)

    def _override():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app), TestingSession


def _seed_full_season(session):
    players = [
        Player(name="Center", number="10", position="F", is_center=True,  active=True),
        Player(name="Wing1",  number="7",  position="F", is_center=False, active=True),
        Player(name="Wing2",  number="8",  position="F", is_center=False, active=True),
        Player(name="Def1",   number="2",  position="D", is_center=False, active=True),
        Player(name="Def2",   number="4",  position="D", is_center=False, active=True),
    ]
    for p in players:
        session.add(p)
    session.commit()
    games = []
    for i in range(12):
        g = Game(date=date(2025, 10, 1) + timedelta(days=i * 4),
                 opponent=f"O{i}", is_home=(i % 2 == 0), season="2025-26")
        session.add(g)
        games.append(g)
    session.commit()
    # give the Center 12 games of stable ~50 CF60, then last 3 games at 80 CF60
    for i, g in enumerate(games):
        pgs = PlayerGameStats(
            player_id=players[0].id, game_id=g.id,
            toi_5v5=15.0,
            cf60=(80.0 if i >= 9 else 50.0),
            ca60=40.0, ff60=40.0, fa60=30.0, sf60=30.0, sa60=25.0,
            xgf60=2.5, xga60=2.0,
        )
        session.add(pgs)
    session.commit()
    return players


def test_player_endpoint_includes_comparisons_and_flags():
    client, TestingSession = _client_with_db()
    try:
        s = TestingSession()
        players = _seed_full_season(s)
        s.close()

        resp = client.get(f"/api/stats/player/{players[0].id}")
        assert resp.status_code == 200
        body = resp.json()
        assert "comparisons" in body
        assert "flags" in body
        assert "game_flags" in body
        # cf60 shifted from ~50 to 80 in the last 3 games → Corsi shift flag
        labels = [f["label"] for f in body["flags"]]
        assert "Corsi shift" in labels
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 8: Verify test fails (comparisons/flags keys absent)**

Run: `cd backend && venv/bin/pytest tests/test_stats_endpoint.py -v`
Expected: FAIL — response body does not contain `"comparisons"` / `"flags"`.

- [ ] **Step 9: Modify the stats router**

Update the imports at the top of `backend/app/routers/stats.py`:
```python
from ..enrichment import enrich_player_agg
```

Replace the `player_stats` function body:
```python
@router.get("/player/{player_id}")
def player_stats(
    player_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(404, "Player not found")
    games = _filter_games(db, date_from, date_to)
    game_ids = {g.id for g in games}
    pgs_rows = _pgs_for_player_games(db, player_id, game_ids)
    agg = aggregate_player_stats(player, pgs_rows, games)

    # Build cohort baselines from all active players over the same window
    all_players = db.query(Player).filter_by(active=True).all()
    all_aggs = []
    for other in all_players:
        other_pgs = _pgs_for_player_games(db, other.id, game_ids)
        other_agg = aggregate_player_stats(other, other_pgs, games)
        all_aggs.append((other, other_agg))

    return enrich_player_agg(player, agg, all_aggs)
```

- [ ] **Step 10: Verify endpoint test passes**

Run: `cd backend && venv/bin/pytest tests/test_stats_endpoint.py -v`
Expected: pass.

- [ ] **Step 11: Run full test suite**

Run: `cd backend && venv/bin/pytest -v`
Expected: 47 tests pass (3 smoke + 15 cohorts + 6 comparisons + 4 flag selection + 18 flags + 1 endpoint).

- [ ] **Step 12: Commit**

```bash
git add backend/app/flag_rules.py backend/app/enrichment.py backend/app/routers/stats.py backend/app/calculations.py backend/tests/test_flag_selection.py backend/tests/test_stats_endpoint.py
git commit -m "feat: expose comparisons and flags on player stats endpoint"
```

---

### Task 7: Frontend types

**Files:**
- Modify: `frontend/src/types.ts`

**Interfaces:**
- Consumes: JSON response shape from `/api/stats/player/{id}` (defined in Task 6)
- Produces:
  - Exported interfaces: `Baseline`, `StatComparison`, `PlayerFlag`, extended `PlayerAggStats` with `comparisons?`, `flags?`, `game_flags?`

- [ ] **Step 1: Extend types.ts**

Append to `frontend/src/types.ts`:
```typescript
export interface Baseline {
  mean: number | null
  std: number | null
  n: number
}

export interface StatComparison {
  value: number | null
  cohort: string
  team_baseline: Baseline
  position_baseline: Baseline
  team_delta: number | null
  position_delta: number | null
  indicator: 'green' | 'yellow' | 'red' | 'neutral'
}

export interface PlayerFlag {
  kind: 'trend' | 'outlier'
  label: string
  direction: 'up' | 'down'
  z_score: number | null
  window_value: number | null
  baseline_value: number | null
  game_id: number | null
}
```

Modify the `PlayerAggStats` interface to add three optional fields at the end:
```typescript
export interface PlayerAggStats {
  // ... existing fields ...
  trend: PlayerTrendPoint[]
  comparisons?: Record<string, StatComparison>
  flags?: PlayerFlag[]
  game_flags?: Record<number, PlayerFlag[]>
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat: add StatComparison and PlayerFlag types"
```

---

### Task 8: Frontend FlagPanel component

**Files:**
- Create: `frontend/src/components/FlagPanel.tsx`

**Interfaces:**
- Consumes: `PlayerFlag` from types.ts
- Produces:
  - `<FlagPanel flags={PlayerFlag[]} onClickFlag={(f) => void} />` React component; renders 0–3 badges; each badge shows label + direction arrow; when `flags.length === 0`, renders a subtle "No flags this window" line

- [ ] **Step 1: Create the component**

Create `frontend/src/components/FlagPanel.tsx`:
```tsx
import type { PlayerFlag } from '../types'

interface Props {
  flags: PlayerFlag[]
  onClickFlag?: (flag: PlayerFlag) => void
}

const COLOR_FOR_DIRECTION = {
  up:   { bg: 'rgba(120, 200, 130, 0.12)', border: 'rgba(120, 200, 130, 0.5)', text: '#7dbf88' },
  down: { bg: 'rgba(200, 100, 100, 0.12)', border: 'rgba(200, 100, 100, 0.5)', text: '#c07272' },
}

export default function FlagPanel({ flags, onClickFlag }: Props) {
  if (!flags || flags.length === 0) {
    return (
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: 20 }}>
        No flags this window.
      </div>
    )
  }
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-secondary)', alignSelf: 'center' }}>
        Flags this window:
      </div>
      {flags.map((f, i) => {
        const colors = COLOR_FOR_DIRECTION[f.direction] ?? COLOR_FOR_DIRECTION.up
        const arrow = f.direction === 'up' ? '⬆' : '⬇'
        return (
          <button
            key={i}
            onClick={() => onClickFlag?.(f)}
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: colors.text,
              background: colors.bg,
              border: `1px solid ${colors.border}`,
              borderRadius: 12,
              padding: '4px 10px',
              cursor: onClickFlag ? 'pointer' : 'default',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span>{arrow}</span>
            <span>{f.label}</span>
          </button>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/FlagPanel.tsx
git commit -m "feat: add FlagPanel component for player flag badges"
```

---

### Task 9: ComparisonRow component + integrate into player report view

**Files:**
- Create: `frontend/src/components/ComparisonRow.tsx`
- Modify: `frontend/src/pages/ReportsPage.tsx`
- Modify: `frontend/src/api/client.ts` (add `getPlayerAggStats` for single-player fetch if not present)

**Interfaces:**
- Consumes: `StatComparison`, `PlayerFlag`
- Produces:
  - `<ComparisonRow label={string} comparison={StatComparison} unit={'%' | 'per60' | 'min' | 'sec' | 'count'} />` React component; renders the raw value, team delta and position delta side-by-side, colored dot indicator on the right
  - A "detailed player view" mode in ReportsPage that appears when a player is clicked (or a new detail panel); shows FlagPanel + per-stat ComparisonRow list

- [ ] **Step 1: Ensure single-player fetch exists**

Read `frontend/src/api/client.ts` to see if there's already a `getPlayerAggStats(id, from?, to?)` function. If not, add it:

```typescript
export async function getPlayerAggStats(playerId: number, from?: string, to?: string) {
  const params = new URLSearchParams()
  if (from) params.set('date_from', from)
  if (to)   params.set('date_to', to)
  const qs = params.toString() ? `?${params.toString()}` : ''
  const r = await fetch(`${API_BASE}/api/stats/player/${playerId}${qs}`)
  if (!r.ok) throw new Error(`getPlayerAggStats failed: ${r.status}`)
  return r.json()
}
```

(Import `API_BASE` following the same pattern as the other functions in the file.)

- [ ] **Step 2: Create ComparisonRow component**

Create `frontend/src/components/ComparisonRow.tsx`:
```tsx
import type { StatComparison } from '../types'

interface Props {
  label: string
  comparison: StatComparison
  unit?: 'pct' | 'per60' | 'min' | 'sec' | 'count'
}

const DOT_COLOR = {
  green:   '#7dbf88',
  yellow:  '#c8a84b',
  red:     '#c07272',
  neutral: '#6f7784',
}

function fmtVal(v: number | null, unit: Props['unit']): string {
  if (v === null || v === undefined) return '—'
  if (unit === 'pct')    return (v * 100).toFixed(1) + '%'
  if (unit === 'per60')  return v.toFixed(2)
  if (unit === 'min')    return v.toFixed(1) + ' min'
  if (unit === 'sec')    return v.toFixed(0) + ' s'
  return v.toFixed(0)
}

function fmtDelta(v: number | null, unit: Props['unit']): string {
  if (v === null || v === undefined) return '—'
  const prefix = v >= 0 ? '+' : ''
  if (unit === 'pct')    return prefix + (v * 100).toFixed(1) + '%'
  if (unit === 'per60')  return prefix + v.toFixed(2)
  return prefix + v.toFixed(1)
}

export default function ComparisonRow({ label, comparison, unit = 'per60' }: Props) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto auto', gap: 12, alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', minWidth: 70, textAlign: 'right' }}>
        {fmtVal(comparison.value, unit)}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', minWidth: 90, textAlign: 'right' }}>
        vs team: <span style={{ color: 'var(--text)' }}>{fmtDelta(comparison.team_delta, unit)}</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', minWidth: 100, textAlign: 'right' }}>
        vs {comparison.cohort}: <span style={{ color: 'var(--text)' }}>{fmtDelta(comparison.position_delta, unit)}</span>
      </div>
      <div style={{ width: 12, height: 12, borderRadius: 6, background: DOT_COLOR[comparison.indicator] }} />
    </div>
  )
}
```

- [ ] **Step 3: Integrate FlagPanel + ComparisonRow into ReportsPage**

The existing `ReportsPage.tsx` shows a list of players with download buttons. Add an "expand" button on each row that reveals a detail panel showing:
- Player's flags (via `FlagPanel`)
- Key stat comparisons (via `ComparisonRow`) for TOI, CF60, CA60, xGF%, xFSh%, FO%

Read `ReportsPage.tsx` before editing to understand the row structure. Add local state `expandedPlayerId: number | null` and, on expand, fetch full stats via `getPlayerAggStats(id, dateFrom, dateTo)`. Below the row, render:

```tsx
{expandedPlayerId === p.id && detailAggs[p.id] && (
  <div style={{ padding: '16px 20px', background: 'var(--surface)', borderRadius: 8, marginTop: 8 }}>
    <FlagPanel flags={detailAggs[p.id].flags ?? []} />
    <div style={{ marginTop: 12 }}>
      {detailAggs[p.id].comparisons && Object.entries({
        toi_5v5:        { label: 'TOI',        unit: 'min' as const },
        cf60:           { label: 'CF60',       unit: 'per60' as const },
        ca60:           { label: 'CA60',       unit: 'per60' as const },
        on_ice_xgf_pct: { label: 'xGF%',       unit: 'pct' as const },
        xfsh_pct:       { label: 'xFSh%',      unit: 'pct' as const },
        personal_fo_pct:{ label: 'Personal FO%', unit: 'pct' as const },
      }).map(([key, meta]) => {
        const cmp = detailAggs[p.id].comparisons?.[key]
        if (!cmp) return null
        return <ComparisonRow key={key} label={meta.label} comparison={cmp} unit={meta.unit} />
      })}
    </div>
  </div>
)}
```

Add the `getPlayerAggStats` import and state:
```tsx
const [expandedPlayerId, setExpandedPlayerId] = useState<number | null>(null)
const [detailAggs, setDetailAggs] = useState<Record<number, PlayerAggStats>>({})
```

Add a click handler that fetches on demand and toggles expansion.

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Manual verification via dev server**

Run in one terminal: `cd backend && venv/bin/uvicorn app.main:app --reload --port 8000`
Run in another: `cd frontend && npm run dev`

Open `http://localhost:5173/reports`. For a player with ≥10 games in the current database:
- Click the expand control on their row.
- Verify a FlagPanel appears (either badges or "No flags this window").
- Verify 6 comparison rows appear with values, team delta, position delta, colored dot.

If the current DB has no player with 10+ games, add a note to the commit message that manual verification is deferred until real data is present.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ComparisonRow.tsx frontend/src/api/client.ts frontend/src/pages/ReportsPage.tsx
git commit -m "feat: expandable player detail with flags and position-aware comparisons"
```

---

### Task 10: Per-game TOI badges in game log view

**Files:**
- Modify: `frontend/src/pages/ReportsPage.tsx` (extend the expanded detail panel with a per-game log)
- Create: `frontend/src/components/GameFlagBadge.tsx`

**Interfaces:**
- Consumes: `PlayerFlag`, `game_flags` map from PlayerAggStats
- Produces:
  - `<GameFlagBadge flag={PlayerFlag} />` — small pill; red for "reduced role", blue for "expanded role"

- [ ] **Step 1: Create GameFlagBadge**

Create `frontend/src/components/GameFlagBadge.tsx`:
```tsx
import type { PlayerFlag } from '../types'

interface Props {
  flag: PlayerFlag
}

const STYLE_FOR_LABEL: Record<string, { bg: string; border: string; text: string }> = {
  'reduced role':  { bg: 'rgba(200, 100, 100, 0.12)', border: 'rgba(200, 100, 100, 0.5)', text: '#c07272' },
  'expanded role': { bg: 'rgba(120, 160, 200, 0.12)', border: 'rgba(120, 160, 200, 0.5)', text: '#7ba1c8' },
}

export default function GameFlagBadge({ flag }: Props) {
  const s = STYLE_FOR_LABEL[flag.label] ?? { bg: 'transparent', border: 'var(--border)', text: 'var(--text-secondary)' }
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
      color: s.text, background: s.bg, border: `1px solid ${s.border}`,
      borderRadius: 4, padding: '2px 6px', marginLeft: 8,
    }}>
      {flag.label}
    </span>
  )
}
```

- [ ] **Step 2: Add game log to expanded player detail**

Extend the expanded detail panel inside `ReportsPage.tsx` (from Task 9) — below the ComparisonRows, add:

```tsx
<div style={{ marginTop: 24 }}>
  <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 10 }}>
    Game Log
  </div>
  {detailAggs[p.id].trend.map(g => {
    const gameFlags = detailAggs[p.id].game_flags?.[g.game_id] ?? []
    return (
      <div key={g.game_id} style={{ display: 'flex', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
        <div style={{ minWidth: 90, color: 'var(--text-secondary)' }}>{g.date}</div>
        <div style={{ minWidth: 90 }}>{g.opponent}</div>
        <div style={{ minWidth: 60 }}>{g.toi_5v5 !== null ? g.toi_5v5.toFixed(1) + ' min' : '—'}</div>
        {gameFlags.map((f, i) => <GameFlagBadge key={i} flag={f} />)}
      </div>
    )
  })}
</div>
```

Import `GameFlagBadge` at the top.

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Manual verify via dev server**

With backend + frontend running, expand a player with ≥11 games in DB. Verify:
- Game log renders below comparisons.
- Games with unusual TOI (relative to their L10) show the badge.
- Normal games show no badge.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/GameFlagBadge.tsx frontend/src/pages/ReportsPage.tsx
git commit -m "feat: per-game TOI outlier badges in expanded player game log"
```

---

### Task 11: PDF report — flag summary and comparison indicators

**Files:**
- Modify: `backend/app/routers/reports.py`
- Modify: `backend/templates/player_report.html`

**Interfaces:**
- Consumes: `enrich_player_agg` (from Task 6); `PlayerAggStats` dict from `aggregate_player_stats`
- Produces: PDF report includes a "Flags this report window" block at the top and per-stat colored indicators next to each stat value

- [ ] **Step 1: Wire enrichment into the reports router**

The router currently builds `agg` and passes it straight to `generate_player_report`. Extend the `player_report` handler in `backend/app/routers/reports.py` to also build `all_aggs` and call `enrich_player_agg` before rendering. Full replacement:

```python
from ..enrichment import enrich_player_agg  # add to imports at top


@router.get("/player/{player_id}")
def player_report(
    player_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    player = db.query(Player).get(player_id)
    if not player:
        raise HTTPException(404, "Player not found")

    games = _filter_games(db, date_from, date_to)
    game_ids = {g.id for g in games}

    pgs_rows = (
        db.query(PlayerGameStats)
        .filter(PlayerGameStats.player_id == player_id,
                PlayerGameStats.game_id.in_(game_ids))
        .all()
    )
    agg = aggregate_player_stats(player, pgs_rows, games)

    # Build all_aggs so enrichment can compute cohort baselines
    all_players = db.query(Player).filter_by(active=True).all()
    all_aggs = []
    for other in all_players:
        other_pgs = (
            db.query(PlayerGameStats)
            .filter(PlayerGameStats.player_id == other.id,
                    PlayerGameStats.game_id.in_(game_ids))
            .all()
        )
        other_agg = aggregate_player_stats(other, other_pgs, games)
        all_aggs.append((other, other_agg))
    agg = enrich_player_agg(player, agg, all_aggs)

    tgs_rows = db.query(TeamGameStats).filter(TeamGameStats.game_id.in_(game_ids)).all()
    team_agg = aggregate_team_stats(tgs_rows, games)

    pdf_bytes = generate_player_report(player, agg, team_agg)
    safe_name = player.name.replace(" ", "_")
    date_suffix = f"_{date_from}_to_{date_to}" if date_from or date_to else ""
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="player_{safe_name}{date_suffix}_report.pdf"'},
    )
```

No changes needed to `generate_player_report` — it already receives `agg` and forwards it to the Jinja context as `agg`, so `agg.comparisons`, `agg.flags`, `agg.game_flags` are already accessible in the template.

- [ ] **Step 2: Add flag block to player_report.html**

Read `backend/templates/player_report.html`. Find the top of the report body (just after the header/name/dates block). Insert:

```html
{% if agg.flags %}
<div style="margin: 12px 0 20px 0; padding: 10px 14px; background: #fafafa; border-left: 3px solid #a30000; border-radius: 4px;">
  <div style="font-size: 9px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #666; margin-bottom: 6px;">
    Flags this window
  </div>
  {% for f in agg.flags %}
    <span style="display: inline-block; margin: 2px 6px 2px 0; padding: 3px 9px; border-radius: 10px; font-size: 10px; font-weight: 600;
                 color: {% if f.direction == 'up' %}#3a7d43{% else %}#8a2c2c{% endif %};
                 background: {% if f.direction == 'up' %}rgba(120,200,130,0.12){% else %}rgba(200,100,100,0.12){% endif %};
                 border: 1px solid {% if f.direction == 'up' %}rgba(120,200,130,0.5){% else %}rgba(200,100,100,0.5){% endif %};">
      {% if f.direction == 'up' %}⬆{% else %}⬇{% endif %} {{ f.label }}
    </span>
  {% endfor %}
</div>
{% endif %}
```

- [ ] **Step 3: Add colored indicator next to each stat**

Read the player_report.html sections that render individual stats. For each stat with a comparison, add an inline indicator dot. Create a Jinja macro at the top of the file:

```html
{% macro indicator(stat_key) %}
  {% if agg.comparisons and stat_key in agg.comparisons %}
    {% set c = agg.comparisons[stat_key].indicator %}
    <span style="display: inline-block; width: 8px; height: 8px; border-radius: 4px; vertical-align: middle; margin-left: 6px;
                 background:
                   {% if c == 'green' %}#7dbf88
                   {% elif c == 'yellow' %}#c8a84b
                   {% elif c == 'red' %}#c07272
                   {% else %}#cccccc{% endif %};"></span>
  {% endif %}
{% endmacro %}
```

Then wherever a stat value is rendered, e.g.:
```html
<td>CF60</td>
<td>{{ agg.cf60|round(2) }} {{ indicator('cf60') }}</td>
```

Do this for at least: `cf60`, `ca60`, `on_ice_cf_pct`, `on_ice_xgf_pct`, `xfsh_pct`, `personal_fo_pct`, `toi_5v5`. Skim the template and add wherever these values already appear.

- [ ] **Step 4: Add outlier badges to per-game trend rows in PDF**

If the player template already includes a per-game trend / game log section, add TOI outlier badges next to matching game rows:
```html
{% for g in agg.trend %}
  <tr>
    <td>{{ g.date }}</td>
    <td>{{ g.opponent }}</td>
    <td>
      {{ '%.1f'|format(g.toi_5v5) if g.toi_5v5 else '—' }}
      {% if agg.game_flags and g.game_id|string in agg.game_flags %}
        {% for f in agg.game_flags[g.game_id|string] %}
          <span style="margin-left: 6px; padding: 1px 6px; border-radius: 3px; font-size: 8px; font-weight: 700; text-transform: uppercase;
                       color: {% if f.label == 'reduced role' %}#8a2c2c{% else %}#3a5f8a{% endif %};
                       background: {% if f.label == 'reduced role' %}rgba(200,100,100,0.12){% else %}rgba(120,160,200,0.12){% endif %};
                       border: 1px solid {% if f.label == 'reduced role' %}rgba(200,100,100,0.5){% else %}rgba(120,160,200,0.5){% endif %};">
            {{ f.label }}
          </span>
        {% endfor %}
      {% endif %}
    </td>
  </tr>
{% endfor %}
```

(Note the `|string` conversion because JSON-serialized dict keys can arrive as strings; verify with a live render — if keys are already ints in the Jinja context, omit `|string`.)

- [ ] **Step 5: Manual PDF render check**

Start the backend: `cd backend && venv/bin/uvicorn app.main:app --reload --port 8000`

From ReportsPage in the browser, download a PDF for a player with ≥10 games. Verify:
- Flag block appears if the player has flags (otherwise nothing rendered — no empty block).
- Colored dots appear next to CF60 / xGF% / etc. values.
- Per-game rows with unusual TOI show badges.

If manual data doesn't produce any flags, use the same seed-full-season logic from Task 6's test to populate the local DB temporarily (or note that verification is deferred).

- [ ] **Step 6: Commit**

```bash
git add backend/templates/player_report.html backend/app/routers/reports.py
git commit -m "feat: player PDF report includes flag summary and comparison indicators"
```

---

## Final verification

- [ ] **Run full backend test suite:** `cd backend && venv/bin/pytest -v` → all tests pass
- [ ] **Typecheck frontend:** `cd frontend && npx tsc --noEmit` → no errors
- [ ] **Manual end-to-end:** Start backend + frontend, expand a real player in the ReportsPage, download PDF, spot-check both against expectations
- [ ] **Update spec if any threshold tuning happened during implementation** (e.g., if the 10% TOI threshold produced too much noise on real data, update spec §5.2 with the new value and note the reasoning)
