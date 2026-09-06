import sys, types
sys.modules["weasyprint"] = sys.modules.get("weasyprint") or types.ModuleType("weasyprint")
sys.modules["weasyprint"].HTML = lambda *a, **k: None  # type: ignore

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.models import (
    Player, Game, PlayerGameStats, PlayerGameStatsInStat, TeamGameStatsInStat,
)


def _make_client_and_session():
    """Create an isolated in-memory SQLite DB with cross-thread support for TestClient."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client, Session


def _seed_full(session):
    """Seed 3 forwards + 5 InStat games so Impact Score has a real cohort."""
    players = [
        Player(name=f"F{i}", number=str(i), position="F", is_center=False, active=True)
        for i in range(1, 4)
    ]
    for p in players:
        session.add(p)
    session.commit()

    games = []
    for i in range(5):
        g = Game(
            date=date(2025, 10, 1) + timedelta(days=i * 3),
            opponent=f"O{i}", is_home=True, season="2025-26",
            data_source="instat",
        )
        session.add(g)
        games.append(g)
    session.commit()

    for g in games:
        session.add(TeamGameStatsInStat(
            game_id=g.id, pp_shots=12, pp_time_seconds_total=600,
            pp_time_seconds_in_oz=360, pk_opp_breakouts=2,
            scoring_chance_shots=30,
        ))
        for p in players:
            session.add(PlayerGameStats(
                player_id=p.id, game_id=g.id,
                toi_5v5=15.0, cf60=50.0, ca60=40.0,
                xgf60=2.5, xga60=2.0,
                ff60=40.0, fa60=30.0, sf60=25.0, sa60=20.0,
            ))
            session.add(PlayerGameStatsInStat(
                player_id=p.id, game_id=g.id,
                shots=5, pb_won_dz=3, pb_total_dz=5,
                pb_won_oz=2, pb_total_oz=4, pb_won_nz=1, pb_total_nz=2,
                entries_pass=2, entries_stick=3, entries_dump=1,
                puck_losses=6, puck_losses_dz=2, puck_recoveries=8, puck_recoveries_oz=3,
            ))
    session.commit()
    return players[0]


def test_player_agg_returns_all_tier2_blocks():
    client, Session = _make_client_and_session()
    try:
        s = Session()
        try:
            first_player = _seed_full(s)
            player_id = first_player.id
        finally:
            s.close()

        resp = client.get(f"/api/stats/player/{player_id}")
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


def test_team_agg_returns_special_teams_v2():
    client, Session = _make_client_and_session()
    try:
        s = Session()
        try:
            _seed_full(s)
        finally:
            s.close()

        resp = client.get("/api/stats/team")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert "special_teams_v2" in body
    assert body["special_teams_v2"]["games"] == 5
