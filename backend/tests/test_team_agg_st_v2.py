import pytest
from datetime import date
import sys, types
sys.modules["weasyprint"] = sys.modules.get("weasyprint") or types.ModuleType("weasyprint")
sys.modules["weasyprint"].HTML = lambda *a, **k: None  # type: ignore

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models import Game, TeamGameStats, TeamGameStatsInStat


@pytest.fixture
def test_db(tmp_path):
    """Isolated SQLite file per test — bypasses the app's real DB."""
    db_url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    yield session, Session
    session.close()


def test_team_agg_includes_special_teams_v2(test_db):
    session, Session = test_db

    # Seed one game with team stats + team instat
    g = Game(date=date(2025, 10, 1), opponent="X", is_home=True,
             season="2025-26", data_source="instat")
    session.add(g)
    session.commit()
    session.add(TeamGameStats(
        game_id=g.id, cf_for_5v5=60, cf_against_5v5=40,
        xgf_5v5=2.5, xga_5v5=2.0,
        total_game_time=60, toi_pp=5, toi_pk=5, other_toi=0,
    ))
    session.add(TeamGameStatsInStat(
        game_id=g.id, pp_shots=12, pp_time_seconds_total=600,
        pp_time_seconds_in_oz=360, pk_opp_breakouts=2,
    ))
    session.commit()

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

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
