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
