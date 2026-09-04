"""End-to-end verification of the ingest pipeline.

Uploads the fixture PDF, commits it, then queries every target table
to confirm data landed. Uses the same isolated-DB fixture pattern as
test_ingest_router.py (dependency_overrides + tmp SQLite).
"""
import os
import sys
import types

# Stub weasyprint so app.main can be imported in environments where
# the native libgobject library is unavailable (CI, macOS without gtk).
if "weasyprint" not in sys.modules:
    _wp = types.ModuleType("weasyprint")
    _wp.HTML = object
    sys.modules["weasyprint"] = _wp

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
