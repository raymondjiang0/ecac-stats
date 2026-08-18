import sys
import types

# Stub weasyprint so app.main can be imported in environments where
# the native libgobject library is unavailable (CI, macOS without gtk).
if "weasyprint" not in sys.modules:
    _wp = types.ModuleType("weasyprint")
    _wp.HTML = object
    sys.modules["weasyprint"] = _wp

from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.models import Player, Game, PlayerGameStats


def _client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
        center_id = players[0].id
        s.close()

        resp = client.get(f"/api/stats/player/{center_id}")
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
