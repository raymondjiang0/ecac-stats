import os
import sys
import types
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Stub weasyprint so app.main can be imported in environments where
# the native libgobject library is unavailable (CI, macOS without gtk).
if "weasyprint" not in sys.modules:
    _wp = types.ModuleType("weasyprint")
    _wp.HTML = object
    sys.modules["weasyprint"] = _wp

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
        assert "warnings" in body

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

    def test_delete_committed_run_returns_400(self, client, clean_db):
        game = clean_db.query(Game).first()
        with open(FIXTURE, "rb") as f:
            up = client.post(
                "/api/ingest/upload",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"game_id": str(game.id)},
            )
        run_id = up.json()["ingest_run_id"]
        resp = client.post(f"/api/ingest/{run_id}/commit")
        assert resp.status_code == 200
        resp = client.delete(f"/api/ingest/{run_id}")
        assert resp.status_code == 400


class TestUploadValidation:
    def test_upload_rejects_non_pdf_content_type(self, client, clean_db):
        game = clean_db.query(Game).first()
        resp = client.post(
            "/api/ingest/upload",
            files={"file": ("not_a_pdf.txt", b"hello world", "text/plain")},
            data={"game_id": str(game.id)},
        )
        assert resp.status_code == 415

    def test_upload_rejects_oversized_payload(self, client, clean_db, monkeypatch):
        game = clean_db.query(Game).first()
        # 51 MB of zeros — over the 50 MB cap
        big_blob = b"\x00" * (51 * 1024 * 1024)
        resp = client.post(
            "/api/ingest/upload",
            files={"file": ("big.pdf", big_blob, "application/pdf")},
            data={"game_id": str(game.id)},
        )
        assert resp.status_code != 200
