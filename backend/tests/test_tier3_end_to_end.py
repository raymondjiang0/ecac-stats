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
                                         toi_5v5=15.0,
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
