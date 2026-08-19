import pytest
from datetime import date
from app.models import Player, Game, PlayerGameStatsInStat


@pytest.fixture
def sample_player_and_game(db_session):
    p = Player(name="Sample", number="10", position="F", is_center=True, active=True)
    g = Game(date=date(2025, 10, 1), opponent="Yale", is_home=True, season="2025-26",
             data_source="instat")
    db_session.add(p)
    db_session.add(g)
    db_session.commit()
    return p, g


class TestPlayerGameStatsInStat:
    def test_can_create_row(self, db_session, sample_player_and_game):
        p, g = sample_player_and_game
        row = PlayerGameStatsInStat(
            player_id=p.id, game_id=g.id,
            shots=8, shots_on_goal=5, blocked_shots=1,
            corsi_plus=15, corsi_minus=10,
            hits_delivered=2, hits_received=1,
            pb_won_dz=6, pb_total_dz=10,
            pb_won_oz=3, pb_total_oz=7,
            pb_won_nz=2, pb_total_nz=4,
            puck_losses=5, puck_losses_dz=1,
            puck_recoveries=8, puck_recoveries_oz=2,
            entries_pass=3, entries_stick=4, entries_dump=1,
        )
        db_session.add(row)
        db_session.commit()
        assert row.id is not None

    def test_all_fields_default_none(self, db_session, sample_player_and_game):
        p, g = sample_player_and_game
        row = PlayerGameStatsInStat(player_id=p.id, game_id=g.id)
        db_session.add(row)
        db_session.commit()
        assert row.shots is None
        assert row.pb_won_dz is None
        assert row.entries_pass is None

    def test_unique_player_game(self, db_session, sample_player_and_game):
        from sqlalchemy.exc import IntegrityError
        p, g = sample_player_and_game
        db_session.add(PlayerGameStatsInStat(player_id=p.id, game_id=g.id))
        db_session.commit()
        db_session.add(PlayerGameStatsInStat(player_id=p.id, game_id=g.id))
        with pytest.raises(IntegrityError):
            db_session.commit()
